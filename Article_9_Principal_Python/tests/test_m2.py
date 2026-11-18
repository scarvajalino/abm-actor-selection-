"""M2 behavioral tests with manual temporal oracles and preserved M1 regression."""
from dataclasses import replace
import json
import math
import os
from pathlib import Path
from types import SimpleNamespace
import networkx as nx
import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
from article9.attributes import ATTRIBUTES, assign_attributes
from article9.behavior import (adoption_probability, credible_signal, experience_satisfaction,
                              communication_capacity, send_probability)
from article9.config import Config
from article9.diffusion import simulate
from article9.event_random import EventRandom
from article9.export import export_run, sha256, write_csv
from article9.m2_config import DiffusionConfig
from article9.m2_export import export_diffusion
from article9.model import Population, initialize, run_policies
from article9.randomness import Streams
from article9.scores import compute_scores
from article9.selection import POLICIES


class FixedDraws:
    """Deterministic boundary fixture; never used for exported verification campaigns."""
    def __init__(self, reject_seeds=(), reject_wom=()):
        self.reject_seeds = set(reject_seeds)
        self.reject_wom = set(reject_wom)

    def uniform(self, event, month, actor_id, other_id=-1):
        if event == "seed_adoption" and actor_id in self.reject_seeds:
            return .999999
        if event == "wom_adoption" and actor_id in self.reject_wom:
            return .999999
        return 0.0


def fixture_population(edges=None, n=4):
    base = Config(n_agents=n, n_communities=2, mean_degree=1, k=1)
    graph = nx.Graph()
    graph.add_nodes_from((i, {"community_id": i // (n // 2)}) for i in range(n))
    graph.add_edges_from(edges if edges is not None else [(0, 1), (1, 2), (2, 3)])
    nodes, latent = assign_attributes(graph, base, Streams(base.master_seed, 0))
    nodes[list(ATTRIBUTES)] = 1.0
    nodes = compute_scores(graph, nodes, base)
    return base, Population(graph, nodes, latent, 0)


def selection(*ids):
    return SimpleNamespace(actor_ids=list(ids), policy="fixture")


def guaranteed(**changes):
    return replace(DiffusionConfig(horizon_months=6, product_quality=1,
                                   adoption_intercept=1000), **changes)


def assert_invariants(result, population, selected_ids, horizon):
    ids, chosen = set(population.nodes.actor_id), set(selected_ids)
    periods, events = result.periods, result.events
    final = result.final_states.set_index("actor_id")
    assert len(periods) == horizon + 1 and periods.month.tolist() == list(range(horizon + 1))
    assert len(result.state_history) == len(ids) * (horizon + 1)
    assert (periods.awareness_count.diff().dropna() >= 0).all()
    assert (periods.adoption_count.diff().dropna() >= 0).all()
    assert (periods.adoption_count <= periods.awareness_count).all()
    assert (periods.awareness_count <= len(ids)).all()
    assert (periods.wom_messages_cumulative == periods.wom_unique_reach + periods.repeated_wom_exposures).all()
    assert not events.duplicated(["sender", "receiver"]).any()
    assert len(events) <= 2 * population.graph.number_of_edges()
    assert all(population.graph.has_edge(int(row.sender), int(row.receiver)) for row in events.itertuples())
    assert (events.sender_adoption_month < events.month).all()
    assert int(events.first_wom_exposure.sum()) == result.summary["wom_unique_reach"]
    assert int(events.new_awareness.sum()) + len(chosen) == result.summary["awareness_count"]
    assert int(events.conversion_credit.sum()) == result.summary["wom_source_adoptions"]
    assert int(final.adopted.sum()) == result.summary["adoption_count"]
    assert (final.loc[final.adopted, "adoption_month"] >= final.loc[final.adopted, "awareness_month"]).all()
    successes = result.evaluations.loc[result.evaluations.adopted]
    assert successes.actor_id.nunique() == len(successes) == result.summary["adoption_count"]
    assert result.cascades.cascade_adopters_including_root.sum() == final.adopted.sum()
    for i, row in final.loc[final.adopted].iterrows():
        assert row.root_seed in chosen
        if row.acquisition_source == "seed":
            assert row.root_seed == i and row.cascade_depth == 0 and pd.isna(row.parent_id)
        else:
            parent = final.loc[int(row.parent_id)]
            assert parent.adopted and parent.adoption_month < row.adoption_month
            assert parent.root_seed == row.root_seed
            assert parent.cascade_depth + 1 == row.cascade_depth


def test_U01_m2_configuration(evidence):
    invalid = [dict(horizon_months=0), dict(horizon_months=True), dict(base_contact_capacity=-1),
               dict(base_contact_capacity=1.5), dict(product_quality=1.1), dict(product_complexity=-.1),
               dict(satisfaction_threshold=float("nan")), dict(satisfaction_quality_weight=2),
               dict(need_effect=-1), dict(adoption_intercept=float("inf")), dict(social_proof_saturation=0)]
    for values in invalid:
        with pytest.raises((ValueError, TypeError)):
            DiffusionConfig(**values)
    assert DiffusionConfig(base_contact_capacity=0).base_contact_capacity == 0
    evidence(invalid_cases=len(invalid), zero_capacity_control_supported=True)


def test_U02_manual_equations(evidence):
    actor = {"need": .5, "product_fit": .5, "expertise": .5, "expertise_fit": .5,
             "credibility": .8, "activity": .7, "recommendation_propensity": .4}
    config = DiffusionConfig()
    # Risk=.5*(1-.25)=.375; seed logit=-2+1+1+.75-.375=.375.
    expected_seed = 1 / (1 + math.exp(-.375))
    signal = .8 * (.5 + .5 * .25)
    expected_wom = 1 / (1 + math.exp(-(.375 + 2 * signal + .5 * 2 / 3)))
    assert adoption_probability(actor, config) == pytest.approx(expected_seed)
    assert credible_signal(actor, config) == pytest.approx(.5)
    assert adoption_probability(actor, config, signal, 2, "wom") == pytest.approx(expected_wom)
    assert experience_satisfaction(actor, config) == pytest.approx(.65)
    assert send_probability(actor, .65) == pytest.approx(.26)
    assert communication_capacity(actor, config) == 2
    evidence(seed_probability=expected_seed, wom_probability=expected_wom, satisfaction=.65, send_probability=.26, capacity=2)


def test_U03_credibility_and_complexity(evidence):
    config = DiffusionConfig()
    expert = dict(credibility=.8, expertise=1, expertise_fit=1)
    novice = dict(credibility=.8, expertise=0, expertise_fit=1)
    assert credible_signal(expert, replace(config, product_complexity=0)) == credible_signal(novice, replace(config, product_complexity=0))
    low_gap = credible_signal(expert, replace(config, product_complexity=.2)) - credible_signal(novice, replace(config, product_complexity=.2))
    high_gap = credible_signal(expert, replace(config, product_complexity=.8)) - credible_signal(novice, replace(config, product_complexity=.8))
    assert high_gap > low_gap
    expert["credibility"] = 0
    assert credible_signal(expert, config) == 0
    receiver = dict(need=.5, product_fit=.5, expertise=.5, expertise_fit=.5)
    assert adoption_probability(receiver, config, 0, 0, "wom") == adoption_probability(receiver, config, source="seed")
    evidence(expertise_gap_low=low_gap, expertise_gap_high=high_gap, zero_credibility_signal=0)


def test_U04_need_and_fit_gates(evidence):
    base, pop = fixture_population()
    for field in ["need", "product_fit"]:
        altered = Population(pop.graph, pop.nodes.copy(), pop.latent, 0)
        altered.nodes[field] = 0
        result = simulate(altered, selection(0), base, guaranteed(), event_random=FixedDraws())
        assert result.summary["adoption_count"] == 0
        assert result.summary["awareness_count"] == 1
        assert result.events.empty
    evidence(zero_need_or_zero_fit_blocks_adoption=True, automatic_wom=False)


def test_U05_unsatisfied_adopters(evidence):
    base, pop = fixture_population()
    config = guaranteed(product_quality=0, satisfaction_threshold=.6)
    result = simulate(pop, selection(0), base, config, event_random=FixedDraws())
    actor = result.final_states.set_index("actor_id").loc[0]
    assert actor.adopted and not actor.satisfied
    assert actor.satisfaction == pytest.approx(.4)
    assert result.events.empty and result.summary["adoption_count"] == 1
    assert set(result.sender_log.reason) == {"unsatisfied"}
    evidence(adopter_unsatisfied=True, wom_events=0)


def test_U06_zero_communication_controls(evidence):
    base, original = fixture_population()
    cases = [("activity", 0, 4), ("recommendation_propensity", 0, 4), ("activity", .1, 4), ("activity", 1, 0)]
    for field, value, capacity in cases:
        pop = Population(original.graph, original.nodes.copy(), original.latent, 0)
        pop.nodes[field] = value
        result = simulate(pop, selection(0), base, guaranteed(base_contact_capacity=capacity), event_random=FixedDraws())
        assert result.summary["adoption_count"] == 1 and result.events.empty
        assert result.summary["eligible_senders_next_month"] == 0
    evidence(controls=len(cases), all_wom_counts_zero=True)


def test_U07_synchronous_chain(evidence):
    base, pop = fixture_population()
    result = simulate(pop, selection(0), base, guaranteed(), event_random=FixedDraws())
    assert result.final_states.adoption_month.tolist() == [1, 2, 3, 4]
    assert result.final_states.cascade_depth.tolist() == [0, 1, 2, 3]
    assert result.events.month.tolist() == [2, 3, 4]
    assert result.periods.loc[result.periods.month == 0, "awareness_count"].iloc[0] == 0
    assert result.periods.loc[result.periods.month == 1, "wom_messages_new"].iloc[0] == 0
    assert_invariants(result, pop, [0], 6)
    evidence(adoption_months=[1, 2, 3, 4], depths=[0, 1, 2, 3], seed_first_wom_month=2)


def test_U08_no_repeated_contact_or_spontaneous_retry(evidence):
    base, pop = fixture_population(edges=[(0, 1)])
    config = DiffusionConfig(horizon_months=10, product_quality=1)
    result = simulate(pop, selection(0), base, config, event_random=FixedDraws(reject_wom=[1]))
    assert len(result.events) == 1
    assert result.events[["sender", "receiver"]].values.tolist() == [[0, 1]]
    assert len(result.evaluations.loc[result.evaluations.source == "wom"]) == 1
    assert not result.final_states.set_index("actor_id").loc[1, "adopted"]
    assert result.summary["awareness_count"] == 2
    evidence(lifetime_pair_messages=1, reevaluations_without_new_messages=0)


def test_U09_simultaneous_recommendations(evidence):
    base, pop = fixture_population(edges=[(0, 2), (1, 2), (2, 3)])
    pop.nodes.loc[0, "credibility"] = .1
    result = simulate(pop, selection(0, 1), base, guaranteed(), event_random=FixedDraws())
    at_two = result.events.loc[result.events.month == 2]
    assert len(at_two) == 2
    assert at_two.first_wom_exposure.sum() == 1
    assert at_two.repeated_wom_exposure.sum() == 1
    assert at_two.conversion_credit.sum() == 1
    evaluations = result.evaluations.query("actor_id == 2 and month == 2")
    assert len(evaluations) == 1
    final = result.final_states.set_index("actor_id")
    assert final.loc[2, "parent_id"] == 1 and final.loc[2, "root_seed"] == 1
    assert final.loc[3, "parent_id"] == 2 and final.loc[3, "adoption_month"] == 3
    assert_invariants(result, pop, [0, 1], 6)
    evidence(simultaneous_messages=2, receiver_evaluations=1, attributed_adoptions=1, parent=1)


def test_U10_selected_rejecter_can_adopt_via_wom(evidence):
    base, pop = fixture_population()
    config = DiffusionConfig(horizon_months=6, product_quality=1)
    result = simulate(pop, selection(0, 1), base, config, event_random=FixedDraws(reject_seeds=[1]))
    final = result.final_states.set_index("actor_id")
    assert final.loc[1, "selected"] and final.loc[1, "seed_evaluated"]
    assert final.loc[1, "acquisition_source"] == "wom" and final.loc[1, "root_seed"] == 0
    assert result.cascades.set_index("root_seed").loc[1, "cascade_adopters_including_root"] == 0
    event = result.events.loc[result.events.receiver == 1].iloc[0]
    assert event.first_wom_exposure and not event.new_awareness
    assert result.summary["seed_source_adoptions"] == 1
    assert_invariants(result, pop, [0, 1], 6)
    evidence(selected_rejecter_can_reconsider=True, inherited_root=0, own_cascade_size=0)


def test_U11_capacity_and_audience_exhaustion(evidence):
    base, pop = fixture_population(edges=[(0, 1), (0, 2), (0, 3)])
    pop.nodes.loc[[1, 2, 3], "need"] = 0
    result = simulate(pop, selection(0), base, guaranteed(base_contact_capacity=1), event_random=FixedDraws())
    assert result.events.month.tolist() == [2, 3, 4]
    assert result.events.receiver.tolist() == [1, 2, 3]
    assert result.sender_log.messages_sent.max() == 1
    assert set(result.sender_log.loc[result.sender_log.month >= 5, "reason"]) == {"audience_exhausted"}
    assert result.summary["wom_unique_reach"] == 3
    assert result.summary["eligible_senders_next_month"] == 0
    evidence(capacity=1, messages=3, unique_neighbors=3, exhausted_from_month=5)


def test_U12_accounting_identities(evidence):
    base, pop = fixture_population(edges=[(0, 2), (1, 2), (2, 3)])
    result = simulate(pop, selection(0, 1), base, guaranteed(), event_random=FixedDraws())
    assert_invariants(result, pop, [0, 1], 6)
    assert result.summary["adoption_count"] == 4
    assert result.summary["wom_messages_cumulative"] == 3
    assert result.summary["wom_unique_reach"] == 2
    assert result.summary["repeated_wom_exposures"] == 1
    assert result.summary["wom_redundancy"] == pytest.approx(1 / 3)
    assert result.summary["communities_aware"] == 2
    assert result.summary["month_to_50pct_adoption"] == 1
    evidence(adopters=4, messages=3, unique_wom_reach=2, repeated_exposures=1)


def test_U13_cascade_ancestry(evidence):
    base, pop = fixture_population(edges=[(0, 1), (1, 2), (2, 3), (3, 0)])
    result = simulate(pop, selection(0), base, guaranteed(base_contact_capacity=1), event_random=FixedDraws())
    assert_invariants(result, pop, [0], 6)
    final = result.final_states.set_index("actor_id")
    for i, row in final.loc[final.adopted].iterrows():
        visited = set()
        current = i
        while not pd.isna(final.loc[current, "parent_id"]):
            assert current not in visited
            visited.add(current)
            current = int(final.loc[current, "parent_id"])
        assert current == 0
    assert set(result.events.root_seed) == {0}
    evidence(ancestry_acyclic=True, unique_root=0, chronological_parents=True)


def test_U14_iteration_order(evidence):
    base = Config(n_agents=24, n_communities=3, mean_degree=3, k=5)
    pop = initialize(base, 0)
    targets, _ = run_policies(pop, base)
    config = DiffusionConfig(horizon_months=15)
    forward = simulate(pop, targets["hybrid"], base, config)
    shuffled = Population(pop.graph, pop.nodes.sample(frac=1, random_state=2), pop.latent, 0)
    reverse = simulate(shuffled, targets["hybrid"], base, config, actor_order=list(reversed(sorted(pop.graph.nodes))))
    for field in ["events", "evaluations", "sender_log", "state_history", "periods", "cascades"]:
        assert_frame_equal(getattr(forward, field), getattr(reverse, field))
    evidence(node_row_order_independent=True, sender_iteration_order_independent=True)


def test_U15_policy_order(evidence):
    base = Config(n_agents=24, n_communities=3, mean_degree=3, k=5)
    pop = initialize(base, 1)
    original = pop.nodes.copy(deep=True)
    targets, _ = run_policies(pop, base)
    config = DiffusionConfig(horizon_months=8)
    forward = {p: simulate(pop, targets[p], base, config) for p in POLICIES}
    reverse = {p: simulate(pop, targets[p], base, config) for p in reversed(POLICIES)}
    for policy in POLICIES:
        assert_frame_equal(forward[policy].state_history, reverse[policy].state_history)
        assert_frame_equal(forward[policy].events, reverse[policy].events)
    assert_frame_equal(original, pop.nodes)
    evidence(policies=7, results_independent_of_policy_order=True, population_unchanged=True)


def test_U16_event_reproducibility(tmp_path, evidence):
    field = EventRandom(20260925, 0)
    value = field.uniform("wom_adoption", 8, 9)
    assert value == EventRandom(20260925, 0).uniform("wom_adoption", 8, 9)
    field.uniform("contact_priority", 40, 7, 9)
    assert field.uniform("wom_adoption", 8, 9) == value
    assert 0 <= value < 1
    assert value != EventRandom(20260925, 1).uniform("wom_adoption", 8, 9)
    base, pop = fixture_population()
    config = DiffusionConfig(horizon_months=6)
    hashes = []
    for folder in ["first", "second"]:
        result = simulate(pop, selection(0), base, config)
        out = export_diffusion(tmp_path / folder, result, base, config)
        hashes.append({p.name: sha256(p) for p in out.iterdir()})
    assert hashes[0] == hashes[1]
    evidence(event_value=value, policy_not_in_key=True, identical_export_files=len(hashes[0]))


def test_U17_scores_and_latent_values_do_not_drive_behavior(evidence):
    base, pop = fixture_population()
    config = DiffusionConfig(horizon_months=8)
    reference = simulate(pop, selection(0), base, config)
    changed = Population(pop.graph, pop.nodes.copy(), pop.latent.copy(), 0)
    changed.latent["latent_purchase_value"] = 1e12
    for name in ["hub_score", "opinion_score", "predicted_revenue_score", "predicted_economic_potential"]:
        changed.nodes[name] = 0
    alternate = simulate(changed, selection(0), base, config)
    assert_frame_equal(reference.state_history, alternate.state_history)
    assert_frame_equal(reference.events, alternate.events)
    evidence(fixed_selection_behavior_unchanged=True, no_hidden_revenue_or_score_in_behavior=True)


def test_U18_empty_complete_and_zero_seeds(evidence):
    base, empty = fixture_population(edges=[])
    result = simulate(empty, selection(0), base, guaranteed(), event_random=FixedDraws())
    assert result.events.empty and result.summary["adoption_count"] == 1
    assert result.summary["month_to_50pct_adoption"] is None
    base, complete = fixture_population(edges=list(nx.complete_graph(4).edges))
    no_seeds = simulate(complete, selection(), base, guaranteed(), event_random=FixedDraws())
    assert no_seeds.events.empty and no_seeds.summary["awareness_count"] == 0
    assert no_seeds.evaluations.empty and no_seeds.cascades.empty
    all_seeds = simulate(complete, selection(0, 1, 2, 3), base, guaranteed(), event_random=FixedDraws())
    assert all_seeds.summary["adoption_count"] == 4 and all_seeds.events.empty
    one_seed = simulate(complete, selection(0), base, guaranteed(), event_random=FixedDraws())
    assert one_seed.final_states.adoption_month.tolist() == [1, 2, 2, 2]
    assert_invariants(one_seed, complete, [0], 6)
    evidence(empty_network_wom=0, zero_seed_awareness=0, complete_graph_adoption_months=[1, 2, 2, 2])


def test_U19_eligibility_zero_probability_and_input_validation(evidence):
    base, pop = fixture_population()
    config = guaranteed(product_quality=0, satisfaction_quality_weight=1, satisfaction_threshold=0)
    result = simulate(pop, selection(0), base, config, event_random=FixedDraws())
    assert result.final_states.set_index("actor_id").loc[0, "satisfied"]
    assert result.events.empty and result.summary["eligible_senders_next_month"] == 0
    assert set(result.sender_log.reason) == {"zero_send_probability"}
    with pytest.raises(ValueError):
        simulate(pop, selection(0, 0), base, config)
    with pytest.raises(ValueError):
        simulate(pop, selection(7), base, config)
    with pytest.raises(ValueError):
        simulate(pop, selection(0), base, config, actor_order=[0, 1])
    corrupt = Population(pop.graph, pop.nodes.copy(), pop.latent, 0)
    corrupt.nodes.loc[0, "activity"] = float("nan")
    with pytest.raises(ValueError):
        simulate(corrupt, selection(0), base, config)
    evidence(zero_send_probability_inactive=True, invalid_inputs_rejected=4)


def test_U20_export_contract(tmp_path, evidence):
    base, pop = fixture_population(edges=[(0, 2), (1, 2), (2, 3)])
    config = guaranteed()
    result = simulate(pop, selection(0, 1), base, config, event_random=FixedDraws())
    output = export_diffusion(tmp_path / "campaign", result, base, config)
    manifest = json.loads((output / "manifest.json").read_text())
    for name, digest in manifest["data_sha256"].items():
        assert sha256(output / name) == digest
    for path in output.glob("*.csv"):
        frame = pd.read_csv(path)
        assert "policy" in frame and "repetition" in frame
    events = pd.read_csv(output / "wom_events.csv")
    final = pd.read_csv(output / "final_states.csv")
    assert set(events.sender) <= set(final.actor_id) and set(events.receiver) <= set(final.actor_id)
    assert pd.api.types.is_bool_dtype(events.conversion_credit)
    assert pd.api.types.is_bool_dtype(final.adopted)
    assert len(pd.read_csv(output / "state_history.csv")) == 28
    assert not {"revenue", "profit"} & set(json.loads((output / "summary.json").read_text()))
    with pytest.raises(FileExistsError):
        export_diffusion(output, result, base, config)
    zero = simulate(pop, selection(), base, config)
    empty = export_diffusion(tmp_path / "no_seeds", zero, base, config)
    assert pd.read_csv(empty / "wom_events.csv").empty
    evidence(files_verified=len(manifest["data_sha256"]), reference_integrity=True, no_fabricated_economic_outcomes=True)


def test_U21_integrated_demonstrations(tmp_path, evidence):
    destination = Path(os.environ.get("M2_ACCEPTANCE_OUTPUT", str(tmp_path / "integration")))
    base, config = Config(), DiffusionConfig()
    summaries = []
    for repetition in range(3):
        pop = initialize(base, repetition)
        targets, states = run_policies(pop, base)
        directory = destination / f"rep_{repetition:03d}"
        export_run(directory / "population", pop, base, targets, states)
        for policy in POLICIES:
            result = simulate(pop, targets[policy], base, config)
            assert_invariants(result, pop, targets[policy].actor_ids, 60)
            assert (result.final_states.selected.sum()) == 20
            assert result.evaluations.loc[result.evaluations.source == "seed"].shape[0] == 20
            export_diffusion(directory / policy, result, base, config, population_reference="../population")
            summaries.append(result.summary)
    table = pd.DataFrame(summaries).sort_values(["repetition", "policy"])
    write_csv(destination / "summary_all.csv", table)
    assert len(table) == 21
    evidence(repetitions=3, policies=7, verification_campaigns=21, periods_per_campaign=60,
             people_per_campaign=600, total_wom_events=int(table.wom_messages_cumulative.sum()),
             adoption_range=[int(table.adoption_count.min()), int(table.adoption_count.max())],
             awareness_range=[int(table.awareness_count.min()), int(table.awareness_count.max())])


def test_U22_thresholds_and_finite_horizon(evidence):
    base, pop = fixture_population()
    actor = pop.nodes.loc[0].to_dict()
    config = guaranteed(horizon_months=1)
    result = simulate(pop, selection(0), base, config, event_random=FixedDraws())
    assert len(result.periods) == 2
    assert result.summary["adoption_count"] == 1 and result.events.empty
    assert result.summary["month_to_25pct_awareness"] == 1
    assert result.summary["month_to_50pct_awareness"] is None
    # A satisfied adopter at the horizon can still be eligible for future WOM.
    assert result.summary["eligible_senders_next_month"] == 1
    threshold = experience_satisfaction(actor, replace(config, product_quality=.5))
    at_boundary = simulate(pop, selection(0), base, replace(config, product_quality=.5, satisfaction_threshold=threshold), event_random=FixedDraws())
    above = simulate(pop, selection(0), base, replace(config, product_quality=.5, satisfaction_threshold=threshold + .01), event_random=FixedDraws())
    assert at_boundary.final_states.loc[0, "satisfied"]
    assert not above.final_states.loc[0, "satisfied"]
    evidence(horizon_months=1, unmet_thresholds_null=True, satisfaction_threshold_inclusive=True)
