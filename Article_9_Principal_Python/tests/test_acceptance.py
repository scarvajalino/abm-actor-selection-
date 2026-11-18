"""T01--T19: specification-based acceptance tests, including manual oracles."""
from dataclasses import replace
import inspect
import json
import os
from pathlib import Path
import networkx as nx
import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal
from article9.attributes import ATTRIBUTES, BASE_COLUMNS, assign_attributes, initial_states
from article9.config import Config
from article9.diagnostics import (attribute_correlations, audience_diagnostics,
                                 network_diagnostics, policy_overlap)
from article9.export import export_run, sha256, write_csv
from article9.model import Population, initialize, run_policies
from article9.network import build_network, edge_table, structural_table
from article9.randomness import STREAM_IDS, Streams
from article9.scores import PURE_SCORES, SCORE_COLUMNS, compute_scores
from article9.selection import POLICIES, select_actors


def small_config(**changes):
    return replace(Config(n_agents=4, n_communities=2, mean_degree=1, k=2), **changes)


def manual_case():
    config = small_config()
    graph = nx.Graph()
    graph.add_nodes_from((i, {"community_id": i // 2}) for i in range(4))
    graph.add_edges_from([(0, 2), (0, 3), (1, 2)])
    nodes = structural_table(graph)
    for name in ATTRIBUTES:
        nodes[name] = .5
    nodes["activity"] = [.2, .9, .4, .5]
    nodes["credibility"] = [.8, .9, .5, .5]
    nodes["expertise"] = [.5, 1, .5, .5]
    nodes["expertise_fit"] = [.5, 1, .5, .5]
    nodes["need"] = [.5, .5, .5, 1]
    nodes["product_fit"] = [.5, .5, 1, .5]
    nodes["predicted_economic_potential"] = [.1, .2, .6, .8]
    nodes["predicted_purchase_value"] = 50 + 150 * nodes.predicted_economic_potential
    nodes["activation_cost"] = 1.0
    nodes["tie_rank"] = [2, 3, 0, 1]
    return config, graph, nodes


def test_T01_configuration(evidence):
    invalid = [dict(n_agents=601), dict(n_communities=1), dict(n_agents=6, n_communities=6),
               dict(k=-1), dict(k=601), dict(mean_degree=-1), dict(mean_degree=1000),
               dict(mixing_fraction=1.2), dict(mixing_fraction=float("nan")),
               dict(value_noise_sigma=-1), dict(activation_cost=0), dict(beta_alpha=0),
               dict(revenue_weights=(.2, .2)), dict(combined_weights=(.5, .5, .5, .5)),
               dict(hybrid_weights=(-.1, .3, .4, .4)), dict(master_seed=True),
               dict(k=1.5), dict(n_agents=True), dict(mean_degree=float("inf")),
               dict(mixing_fraction=1), dict(require_modular="yes")]
    for values in invalid:
        with pytest.raises((ValueError, TypeError)):
            Config(**values)
    for mu in [.05, .2, .5]:
        config = Config(mixing_fraction=mu)
        pin, pout = config.edge_probabilities()
        assert pin * 99 + pout * 500 == pytest.approx(12)
    with pytest.raises(ValueError):
        Streams(20260925, -1)
    evidence(invalid_cases_rejected=len(invalid), expected_degree=12)


def test_T02_network_integrity(baseline, evidence):
    config, pop = baseline
    graph = pop.graph
    assert set(graph) == set(range(600))
    assert not graph.is_directed() and not graph.is_multigraph()
    assert nx.number_of_selfloops(graph) == 0
    assert pop.nodes.groupby("community_id").size().tolist() == [100] * 6
    assert all(graph.has_edge(j, i) for i, j in graph.edges)
    table = edge_table(graph)
    assert (table.source < table.target).all()
    assert not table.duplicated(["source", "target"]).any()
    assert len(table) == graph.number_of_edges()
    # No policy dependence, no regeneration to improve connectivity.
    again = build_network(config, Streams(config.master_seed, 0))
    assert_frame_equal(table, edge_table(again))
    evidence(people=600, community_sizes=[100] * 6, edges=len(table))


def test_T03_manual_structure(evidence):
    _, graph, nodes = manual_case()
    assert nodes.degree.tolist() == [2, 1, 2, 1]
    assert nodes.structural_reach.tolist() == [1, .5, 1, .5]
    assert nodes.community_reach.tolist() == [.5, .5, .5, .5]
    metrics = network_diagnostics(graph)
    assert metrics["density"] == .5
    assert metrics["degree_mean"] == 1.5
    assert metrics["degree_sd_population"] == .5
    assert metrics["n_components"] == 1
    assert metrics["average_clustering"] == 0
    assert metrics["modularity"] == pytest.approx(-.5)
    assert metrics["external_edge_fraction"] == 1
    evidence(manual_degrees=[2, 1, 2, 1], manual_modularity=-.5)


def test_T04_attribute_bounds(baseline, evidence):
    config, pop = baseline
    assert ((pop.nodes[list(ATTRIBUTES)] >= 0) & (pop.nodes[list(ATTRIBUTES)] <= 1)).all().all()
    assert (pop.latent.latent_purchase_value > 0).all()
    assert (pop.nodes.activation_cost == 1).all()
    assert sorted(pop.nodes.tie_rank) == list(range(600))
    assert not np.array_equal(pop.nodes.predicted_purchase_value, pop.latent.latent_purchase_value)
    clean, hidden = assign_attributes(pop.graph, replace(config, value_noise_sigma=0), Streams(config.master_seed, 0))
    np.testing.assert_array_equal(clean.predicted_purchase_value, hidden.latent_purchase_value)
    cfg, graph, nodes = manual_case()
    for boundary in [0.0, 1.0]:
        bounded = nodes.copy()
        bounded[list(ATTRIBUTES)] = boundary
        calculated = compute_scores(graph, bounded, cfg)
        assert np.isfinite(calculated[list(SCORE_COLUMNS)].to_numpy()).all()
        assert calculated.opinion_score.tolist() == [boundary] * 4
    nodes.loc[0, "activity"] = 1.1
    with pytest.raises(ValueError):
        compute_scores(graph, nodes, cfg)
    evidence(range_checked=[0, 1], zero_noise_exact=True)


def test_T05_ex_ante_separation(baseline, evidence):
    config, pop = baseline
    original, _ = run_policies(pop, config)
    modified = Population(pop.graph, pop.nodes.copy(), pop.latent.copy(), pop.repetition)
    modified.latent["latent_purchase_value"] = 1e12
    for name in ["realized_revenue", "adopted", "satisfaction", "cascade_rank", "latent_purchase_value"]:
        modified.nodes[name] = np.arange(config.n_agents)[::-1]
    scores = compute_scores(modified.graph, modified.nodes, config)
    assert_frame_equal(scores, pop.nodes)
    changed, _ = run_policies(modified, config)
    for policy in POLICIES:
        assert_frame_equal(original[policy].selected, changed[policy].selected)
    signature = set(inspect.signature(select_actors).parameters)
    assert signature == {"nodes", "policy", "k", "streams", "config"}
    assert not {"latent_purchase_value", "realized_revenue"} & set(scores.columns)
    evidence(policies_unchanged=7, hidden_and_future_fields_excluded=True)


def test_T06_manual_scores(evidence):
    config, graph, nodes = manual_case()
    scored = compute_scores(graph, nodes, config)
    row = scored.loc[0]
    expected = {"hub_score": 1, "influencer_score": .2, "opinion_score": .2,
                "neighbor_potential": .7, "neighbor_fit": .5, "conversion_proxy": .1,
                "predicted_revenue_score": .42, "combined_score": .455}
    for name, value in expected.items():
        assert row[name] == pytest.approx(value)
    assert sum(config.revenue_weights) == pytest.approx(1)
    assert sum(config.combined_weights) == pytest.approx(1)
    evidence(actor_0_expected=expected)


def test_T07_distinct_rankings(evidence):
    config, graph, nodes = manual_case()
    scored = compute_scores(graph, nodes, config)
    selected = {policy: select_actors(scored, policy, 1, Streams(25, 0), config).actor_ids
                for policy in PURE_SCORES}
    assert selected["hubs"] == [2]
    assert selected["influencers"] == [1]
    assert selected["opinion_leaders"] == [1]
    assert nodes.loc[2, "degree"] > nodes.loc[1, "degree"]
    assert nodes.loc[2, "activity"] < nodes.loc[1, "activity"]
    evidence(selected=selected)


def test_T08_exact_selection(baseline, evidence):
    config, pop = baseline
    results, _ = run_policies(pop, config)
    for result in results.values():
        assert len(result.actor_ids) == len(set(result.actor_ids)) == 20
        assert set(result.actor_ids) <= set(pop.nodes.actor_id)
        assert result.selected.activation_cost.sum() == 20
        assert result.selected.selection_order.tolist() == list(range(1, 21))
    for policy, score in PURE_SCORES.items():
        chosen = set(results[policy].actor_ids)
        assert pop.nodes.loc[list(chosen), score].min() >= pop.nodes.loc[~pop.nodes.index.isin(chosen), score].max()
    with pytest.raises(ValueError):
        select_actors(pop.nodes, "unknown", 20, Streams(25, 0), config)
    with pytest.raises(ValueError):
        select_actors(pop.nodes, "hubs", 601, Streams(25, 0), config)
    evidence(policies=7, actors_per_policy=20, cost_per_policy=20)


def test_T09_random_selection(baseline, evidence):
    config, pop = baseline
    streams = Streams(config.master_seed, 0)
    first = select_actors(pop.nodes, "random", 20, streams, config)
    second = select_actors(pop.nodes.sample(frac=1, random_state=4), "random", 20, streams, config)
    assert first.actor_ids == second.actor_ids
    full = select_actors(pop.nodes, "random", 600, streams, config)
    assert set(full.actor_ids) == set(range(600))
    evidence(reproducible=True, full_population_count=len(full.actor_ids))


def test_T10_diversification(baseline, evidence):
    config, pop = baseline
    result = select_actors(pop.nodes, "community_diversified", 20, Streams(config.master_seed, 0), config)
    actual = result.selected.groupby("community_id").size().to_dict()
    assert actual == result.quotas
    assert sorted(actual.values()) == [3, 3, 3, 3, 4, 4]
    assert len(actual) == 6
    for group in actual:
        members = pop.nodes.loc[pop.nodes.community_id == group]
        selected_ids = set(result.selected.loc[result.selected.community_id == group, "actor_id"])
        assert members.loc[list(selected_ids), "combined_score"].min() >= members.loc[~members.index.isin(selected_ids), "combined_score"].max()
    evidence(quotas={str(k): int(v) for k, v in actual.items()})


def test_T11_hybrid_duplicates(baseline, evidence):
    config, pop = baseline
    coincident = pop.nodes.copy()
    for score in PURE_SCORES.values():
        coincident[score] = 1.0  # Identical ranking for all four components.
    result = select_actors(coincident, "hybrid", 20, Streams(config.master_seed, 0), config)
    assert result.selected.groupby("component").size().to_dict() == dict.fromkeys(PURE_SCORES, 5)
    assert len(set(result.actor_ids)) == 20
    expected = set(coincident.sort_values("tie_rank").head(20).actor_id)
    assert set(result.actor_ids) == expected
    skipped = int((result.audit.reason == "duplicate_skipped").sum())
    assert skipped > 0
    # For k not divisible by four, allocation still sums to k.
    uneven = select_actors(coincident, "hybrid", 7, Streams(config.master_seed, 0), config)
    assert sorted(uneven.quotas.values()) == [1, 2, 2, 2]
    assert len(set(uneven.actor_ids)) == 7
    evidence(quotas=result.quotas, duplicate_skips=skipped, all_rankings_identical=True)


def test_T12_ties(baseline, evidence):
    config, pop = baseline
    nodes = pop.nodes.copy()
    for score in [*PURE_SCORES.values(), "combined_score"]:
        nodes[score] = 0.0
    expected = nodes.sort_values("tie_rank").head(20).actor_id.tolist()
    tied = Population(pop.graph, nodes, pop.latent, 0)
    forward, _ = run_policies(tied, config)
    reverse, _ = run_policies(tied, config, reversed(POLICIES))
    for policy in PURE_SCORES:
        assert forward[policy].actor_ids == expected
    for policy in POLICIES:
        assert forward[policy].actor_ids == reverse[policy].actor_ids
    evidence(common_tie_order=True, order_independent=True)


def test_T13_initial_states(baseline, evidence):
    config, pop = baseline
    original = initial_states(pop.nodes.actor_id)
    results, states = run_policies(pop, config)
    assert not original.selected.any()
    for policy in POLICIES:
        state = states[policy]
        assert state.selected.sum() == 20
        assert set(state.loc[state.selected, "actor_id"]) == set(results[policy].actor_ids)
        assert not state[["aware", "adopted", "wom_active"]].any().any()
        assert state.satisfaction.isna().all()
        assert (state[["exposures", "revenue"]] == 0).all().all()
    states["random"].loc[0, "aware"] = True
    assert not states["hubs"].aware.any()
    evidence(no_automatic_adoption_or_wom=True, independent_state_copies=True)


def test_T14_shared_audience(evidence):
    _, graph, _ = manual_case()
    observed = audience_diagnostics(graph, [0, 1])
    assert observed["potential_unique_neighbors"] == 2
    assert observed["potential_contact_incidences"] == 3
    assert observed["potential_redundancy"] == pytest.approx(1 / 3)
    assert observed["shared_audience_fraction"] == .5
    assert observed["selected_communities"] == 1
    assert observed["potential_audience_communities"] == 1
    # Selecting adjacent nodes excludes selected actors from external audience.
    adjacent = audience_diagnostics(graph, [0, 2])
    assert adjacent["potential_unique_neighbors"] == 2
    assert adjacent["potential_contact_incidences"] == 2
    assert adjacent["potential_redundancy"] == 0
    evidence(shared_case=observed, selected_neighbors_excluded=True)


def test_T15_edge_cases(evidence):
    config = small_config(mean_degree=0, require_modular=False)
    empty = initialize(config, 0)
    assert empty.graph.number_of_edges() == 0
    metrics = network_diagnostics(empty.graph)
    assert metrics["modularity"] is None and metrics["modularity_reason"] == "no_edges"
    assert metrics["n_components"] == 4 and metrics["isolated_nodes"] == 4
    assert metrics["warning"] == "largest_component_below_95_percent"
    assert (empty.nodes.neighbor_potential == 0).all()
    assert (empty.nodes.structural_reach == 0).all()
    corr = attribute_correlations(empty.nodes)
    assert corr.loc[corr.variable_a == "degree", "spearman"].isna().all()
    assert (corr.loc[corr.variable_a == "degree", "reason"] == "constant_variable").all()
    graph = nx.complete_graph(4)
    nx.set_node_attributes(graph, {i: i // 2 for i in graph}, "community_id")
    nodes, latent = assign_attributes(graph, config, Streams(25, 0))
    complete = Population(graph, compute_scores(graph, nodes, config), latent, 0)
    assert network_diagnostics(graph)["average_clustering"] == 1.0
    for pop in [empty, complete]:
        for k in [0, 1, 4]:
            results, _ = run_policies(pop, replace(config, k=k))
            for result in results.values():
                assert len(set(result.actor_ids)) == k
                if k in [0, 4]:
                    metrics = audience_diagnostics(pop.graph, result.actor_ids)
                    assert metrics["potential_unique_neighbors"] == 0
                    assert metrics["potential_redundancy"] == 0
            if k == 0:
                assert (policy_overlap(results).jaccard == 1).all()
            if k == 1:
                assert len(results["community_diversified"].selected.community_id.unique()) == 1
    evidence(k_values=[0, 1, 4], network_controls=["empty", "complete"])


def test_T16_reproduction(tmp_path, evidence):
    config = Config(n_agents=24, n_communities=3, mean_degree=3, k=5)
    hashes = []
    for name in ["first", "second"]:
        pop = initialize(config, 4)
        results, states = run_policies(pop, config)
        destination = export_run(tmp_path / name, pop, config, results, states)
        hashes.append({p.name: sha256(p) for p in destination.iterdir()})
    assert hashes[0] == hashes[1]
    other = initialize(config, 5)
    assert not np.array_equal(pop.nodes.activity.to_numpy(), other.nodes.activity.to_numpy())
    # Changing economic noise leaves network and all ex-ante indicators unchanged.
    changed_noise = initialize(replace(config, value_noise_sigma=.9), 4)
    assert_frame_equal(pop.nodes, changed_noise.nodes)
    assert_frame_equal(edge_table(pop.graph), edge_table(changed_noise.graph))
    evidence(identical_artifacts=len(hashes[0]), isolated_noise_stream=True)


def test_T17_execution_order(tmp_path, baseline, evidence):
    config, pop = baseline
    before_nodes = pop.nodes.copy(deep=True)
    before_edges = edge_table(pop.graph)
    forward, state_a = run_policies(pop, config)
    reverse, state_b = run_policies(pop, config, reversed(POLICIES))
    for policy in POLICIES:
        assert_frame_equal(forward[policy].selected, reverse[policy].selected)
        assert_frame_equal(forward[policy].audit, reverse[policy].audit)
        assert_frame_equal(state_a[policy], state_b[policy])
    subset, _ = run_policies(pop, config, ["hubs"])
    assert_frame_equal(subset["hubs"].selected, forward["hubs"].selected)
    assert_frame_equal(before_nodes, pop.nodes)
    assert_frame_equal(before_edges, edge_table(pop.graph))
    for folder, results, states in [("a", forward, state_a), ("b", reverse, state_b)]:
        export_run(tmp_path / folder, pop, config, results, states)
    assert {p.name: sha256(p) for p in (tmp_path / "a").iterdir()} == {p.name: sha256(p) for p in (tmp_path / "b").iterdir()}
    # Modularity scenarios share population, membership and per-pair uniform draws.
    higher_mix = initialize(replace(config, mixing_fraction=.5), 0)
    assert_frame_equal(pop.nodes[list(ATTRIBUTES)], higher_mix.nodes[list(ATTRIBUTES)])
    assert np.array_equal(pop.nodes.community_id, higher_mix.nodes.community_id)
    base_inside = {tuple(sorted((i, j))) for i, j in pop.graph.edges if pop.graph.nodes[i]["community_id"] == pop.graph.nodes[j]["community_id"]}
    mixed_inside = {tuple(sorted((i, j))) for i, j in higher_mix.graph.edges if higher_mix.graph.nodes[i]["community_id"] == higher_mix.graph.nodes[j]["community_id"]}
    assert mixed_inside <= base_inside
    base_outside = {tuple(sorted((i, j))) for i, j in pop.graph.edges} - base_inside
    mixed_outside = {tuple(sorted((i, j))) for i, j in higher_mix.graph.edges} - mixed_inside
    assert base_outside <= mixed_outside
    evidence(policy_orders_identical=True, population_unchanged=True, paired_mixing_scenarios=True)


def test_T18_export_contract(tmp_path, baseline, evidence):
    config, pop = baseline
    results, states = run_policies(pop, config)
    destination = export_run(tmp_path / "export", pop, config, results, states)
    required = {"config.json", "nodes_ex_ante.csv", "edges.csv", "latent_values.csv", "selection.csv",
                "selection_audit.csv", "initial_states.csv", "network_diagnostics.csv",
                "attribute_correlations.csv", "policy_diagnostics.csv", "policy_overlap.csv", "manifest.json"}
    assert {p.name for p in destination.iterdir()} == required
    for path in destination.glob("*.json"):
        json.loads(path.read_text())
    manifest = json.loads((destination / "manifest.json").read_text())
    for name, digest in manifest["data_sha256"].items():
        assert sha256(destination / name) == digest
    nodes = pd.read_csv(destination / "nodes_ex_ante.csv", float_precision="round_trip")
    edges = pd.read_csv(destination / "edges.csv")
    selection = pd.read_csv(destination / "selection.csv")
    latent = pd.read_csv(destination / "latent_values.csv")
    state = pd.read_csv(destination / "initial_states.csv")
    assert len(nodes) == len(latent) == 600 and len(selection) == 140 and len(state) == 4200
    ids = set(nodes.actor_id)
    assert set(selection.actor_id) <= ids and set(edges.source) <= ids and set(edges.target) <= ids
    assert set(latent.actor_id) == ids
    assert pd.api.types.is_integer_dtype(selection.actor_id)
    assert pd.api.types.is_bool_dtype(state.selected)
    assert "latent_purchase_value" not in nodes
    assert not {"revenue", "adopted", "satisfaction"} & set(nodes.columns)
    for path in destination.glob("*.csv"):
        pd.read_csv(path)
    with pytest.raises(FileExistsError):
        export_run(destination, pop, config, results, states)
    # Verify zero selections can also be exported and recovered, with headers.
    zero_config = replace(config, k=0)
    zero_results, zero_states = run_policies(pop, zero_config)
    zero = export_run(tmp_path / "zero", pop, zero_config, zero_results, zero_states)
    assert pd.read_csv(zero / "selection.csv").empty
    evidence(files=len(required), selection_rows=140, referential_integrity=True, zero_selection_export=True)


def test_T19_ten_populations(tmp_path, evidence):
    destination = Path(os.environ.get("M1_ACCEPTANCE_OUTPUT", str(tmp_path / "ten_populations")))
    config = Config()
    all_networks, all_policies = [], []
    for repetition in range(10):
        pop = initialize(config, repetition)
        results, states = run_policies(pop, config)
        assert len(pop.nodes) == 600 and len(pop.latent) == 600
        assert pop.nodes.groupby("community_id").size().tolist() == [100] * 6
        assert nx.number_of_selfloops(pop.graph) == 0
        assert ((pop.nodes[list(ATTRIBUTES)] >= 0) & (pop.nodes[list(ATTRIBUTES)] <= 1)).all().all()
        assert (pop.latent.latent_purchase_value > 0).all()
        for policy, result in results.items():
            assert len(set(result.actor_ids)) == 20 and len(result.actor_ids) == 20
            assert result.selected.activation_cost.sum() == 20
            assert not states[policy].adopted.any() and not states[policy].wom_active.any()
        diversified = results["community_diversified"].selected.groupby("community_id").size()
        assert sorted(diversified.tolist()) == [3, 3, 3, 3, 4, 4]
        assert results["hybrid"].selected.groupby("component").size().to_dict() == dict.fromkeys(PURE_SCORES, 5)
        run_dir = export_run(destination / f"rep_{repetition:03d}", pop, config, results, states)
        all_networks.append(pd.read_csv(run_dir / "network_diagnostics.csv"))
        all_policies.append(pd.read_csv(run_dir / "policy_diagnostics.csv"))
    networks = pd.concat(all_networks, ignore_index=True)
    policies = pd.concat(all_policies, ignore_index=True)
    assert len(networks) == 10 and len(policies) == 70
    write_csv(destination / "network_diagnostics_all.csv", networks)
    write_csv(destination / "policy_diagnostics_all.csv", policies)
    evidence(populations=10, people_per_population=600, policy_selections=70,
             selection_rows=1400, diffusion_campaigns=0,
             warnings=int(networks.warning.notna().sum()),
             mean_degree_range=[float(networks.degree_mean.min()), float(networks.degree_mean.max())],
             modularity_range=[float(networks.modularity.min()), float(networks.modularity.max())])
