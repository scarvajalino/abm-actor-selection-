"""M3 tests use manual ledgers and adversarial cases, plus paired full campaigns."""
from copy import deepcopy
from dataclasses import replace
import json
import math
import os
from pathlib import Path
import pandas as pd
from pandas.testing import assert_frame_equal
import pytest
from test_m2 import fixture_population, selection, guaranteed, FixedDraws
from article9.config import Config
from article9.diffusion import simulate
from article9.economics import account_campaign
from article9.economic_random import EconomicRandom
from article9.export import write_csv, sha256
from article9.m2_config import DiffusionConfig
from article9.m3_config import EconomicConfig
from article9.m3_export import export_economics, input_hashes
from article9.model import initialize, run_policies
from article9.prediction import evaluate_seed_prediction
from article9.selection import POLICIES


def chain(*seeds, horizon=4, draws=None):
    base, pop = fixture_population()
    pop.latent["latent_purchase_value"] = [100., 200., 300., 400.]
    pop.nodes["predicted_purchase_value"] = [90., 190., 290., 390.]
    target = selection(*(seeds or (0,)))
    diff = simulate(pop, target, base, guaranteed(horizon_months=horizon, adoption_intercept=0), event_random=draws or FixedDraws())
    return base, pop, target, diff


class LowDraws:
    def uniform(self, month, actor_id):
        return 0.0


def assert_accounts(result, diffusion):
    tx, a, s = result.transactions, result.actor_accounts, result.summary
    assert tx.transaction_id.is_unique
    assert not tx.duplicated(["month", "actor_id"]).any()
    assert tx.loc[tx.kind == "initial"].actor_id.nunique() == diffusion.summary["adoption_count"]
    assert len(tx.loc[tx.kind == "initial"]) == diffusion.summary["adoption_count"]
    assert (tx.month >= tx.adoption_month).all()
    assert (tx.loc[tx.kind == "repurchase", "month"] > tx.loc[tx.kind == "repurchase", "adoption_month"]).all()
    assert math.fsum(tx.revenue) == pytest.approx(s["revenue"])
    assert s["initial_revenue"] + s["repurchase_revenue"] == pytest.approx(s["revenue"])
    assert s["revenue"] - s["service_cost"] - s["activation_cost"] == pytest.approx(s["profit"])
    for prefix in ("own", "immediate", "root", "attributed"):
        assert math.fsum(a[f"{prefix}_revenue"]) == pytest.approx(s["revenue"])
        assert math.fsum(a[f"{prefix}_service_cost"]) == pytest.approx(s["service_cost"])
        assert math.fsum(a[f"{prefix}_profit"]) == pytest.approx(s["profit"])
    assert math.fsum(result.seed_accounts.root_revenue) == pytest.approx(s["revenue"])
    assert math.fsum(result.seed_accounts.root_profit) == pytest.approx(s["profit"])
    credits = result.attribution_credits
    assert set(credits.transaction_id) == set(tx.transaction_id)
    if len(tx):
        grouped = credits.groupby("transaction_id").agg({"weight":"sum", "revenue":"sum", "service_cost":"sum"})
        for row in tx.itertuples():
            assert grouped.loc[row.transaction_id, "weight"] == pytest.approx(1)
            assert grouped.loc[row.transaction_id, "revenue"] == pytest.approx(row.revenue)
            assert grouped.loc[row.transaction_id, "service_cost"] == pytest.approx(row.service_cost)
    assert result.periods.cumulative_revenue.iloc[-1] == pytest.approx(s["revenue"])
    assert result.periods.cumulative_profit.iloc[-1] == pytest.approx(s["profit"])
    assert result.periods.profit.sum() == pytest.approx(s["profit"])


def test_V01_config_bounds(evidence):
    for kwargs in [dict(service_cost_rate=1.01), dict(service_cost_fixed=-1), dict(service_cost_fixed=True),
                   dict(repurchase_probability=-.1), dict(repurchase_probability=2), dict(repurchase_value_factor=0),
                   dict(repurchase_value_factor=float("inf")), dict(attribution_alpha=-1),
                   dict(leader_fraction=0), dict(leader_fraction=1.1), dict(leader_fraction=float("nan"))]:
        with pytest.raises(ValueError):
            EconomicConfig(**kwargs)
    assert EconomicConfig().repurchase_probability == 0
    evidence(invalid_configs_rejected=11, base_repurchase_disabled=True)


def test_V02_manual_chain_initial_ledger(evidence):
    base, pop, target, diff = chain(0)
    result = account_campaign(pop, target, diff, base, EconomicConfig())
    assert result.transactions.revenue.tolist() == [100, 200, 300, 400]
    assert result.transactions.month.tolist() == [1, 2, 3, 4]
    assert result.summary["revenue"] == 1000
    assert result.summary["service_cost"] == 200
    assert result.summary["profit"] == 799
    assert result.summary["purchase_value_mae_among_adopters"] == 10
    assert result.periods.profit.tolist() == [-1, 80, 160, 240, 320]
    assert_accounts(result, diff)
    evidence(manual_revenue=1000, manual_service_cost=200, manual_profit=799)


def test_V03_failed_seed_still_costs(evidence):
    base, pop, target, diff = chain(0, draws=FixedDraws(reject_seeds=[0]))
    result = account_campaign(pop, target, diff, base, EconomicConfig())
    assert result.transactions.empty and result.summary["profit"] == -1
    assert result.summary["revenue_per_adopter"] is None
    assert result.summary["purchase_value_mae_among_adopters"] is None
    assert result.prediction_metrics["precision"] == 0
    assert result.prediction_metrics["recall"] is None
    assert result.prediction_metrics["spearman"] is None
    assert_accounts(result, diff)
    evidence(no_purchases=True, failed_selection_profit=-1, no_zero_revenue_leaders=True)


def test_V04_selected_rejects_then_adopts_under_other_root(evidence):
    base, pop, target, diff = chain(0, 2, draws=FixedDraws(reject_seeds=[2]))
    result = account_campaign(pop, target, diff, base, EconomicConfig())
    seeds = result.seed_accounts.set_index("actor_id")
    assert seeds.loc[0, "root_revenue"] == 1000
    assert seeds.loc[2, "root_revenue"] == 0
    assert seeds.loc[2, "own_revenue"] == 300
    assert seeds.loc[2, "root_profit"] == -1
    assert result.summary["profit"] == 798
    assert_accounts(result, diff)
    evidence(rejected_seed_own_purchase=300, rejected_seed_root_revenue=0, total_profit=798)


def test_V05_attribution_alpha_manual_endpoints(evidence):
    base, pop, target, diff = chain(0)
    expected = {0: [300, 300, 400, 0], .25: [475, 225, 300, 0], 1: [1000, 0, 0, 0]}
    for alpha, revenue in expected.items():
        result = account_campaign(pop, target, diff, base, EconomicConfig(attribution_alpha=alpha))
        assert result.actor_accounts.attributed_revenue.tolist() == revenue
        assert result.actor_accounts.own_revenue.tolist() == [100, 200, 300, 400]
        assert result.actor_accounts.immediate_revenue.tolist() == [300, 300, 400, 0]
        assert result.actor_accounts.direct_referral_revenue.tolist() == [200, 300, 400, 0]
        assert result.summary["profit"] == 799
        assert_accounts(result, diff)
    evidence(alpha_values=[0, .25, 1], manual_attributions=expected, firm_invariant=True)


def test_V06_repurchase_timing_and_horizon(evidence):
    base, pop, target, diff = chain(0)
    result = account_campaign(pop, target, diff, base,
        EconomicConfig(repurchase_probability=1, repurchase_value_factor=.5), event_random=LowDraws())
    assert result.summary["repurchases"] == 6
    assert result.summary["repurchase_revenue"] == 500
    assert result.summary["revenue"] == 1500
    assert result.summary["profit"] == 1199
    assert set(result.transactions.loc[result.transactions.actor_id == 3, "kind"]) == {"initial"}
    assert result.repurchase_trials.probability.eq(1).all()
    assert_accounts(result, diff)
    evidence(initial=1000, repurchase=500, count=6, profit=1199, no_same_month_repeat=True)


def test_V07_unsatisfied_initial_purchase_no_repeat(evidence):
    base, pop = fixture_population()
    target = selection(0)
    diff = simulate(pop, target, base, guaranteed(product_quality=0, satisfaction_threshold=.9), event_random=FixedDraws())
    result = account_campaign(pop, target, diff, base, EconomicConfig(repurchase_probability=1), event_random=LowDraws())
    assert len(result.transactions) == 1
    assert result.repurchase_trials.reason.eq("unsatisfied").all()
    assert result.repurchase_trials.draw.isna().all()
    assert_accounts(result, diff)
    evidence(initial_purchase_despite_dissatisfaction=True, repurchases=0)


def test_V08_optional_repurchase_uses_satisfaction(evidence):
    base, pop, target, diff = chain(0, horizon=2)
    diff.final_states.loc[diff.final_states.actor_id == 0, "satisfaction"] = .8
    class ThresholdDraw:
        def uniform(self, month, actor_id): return .4
    result = account_campaign(pop, target, diff, base, EconomicConfig(repurchase_probability=.5), event_random=ThresholdDraw())
    assert result.repurchase_trials.probability.tolist() == [.4]
    assert not result.repurchase_trials.purchased.any()  # Strict draw < probability.
    evidence(probability=.4, draw=.4, purchase=False)


def test_V09_service_costs_can_produce_losses(evidence):
    base, pop, target, diff = chain(0)
    result = account_campaign(pop, target, diff, base, EconomicConfig(service_cost_rate=1, service_cost_fixed=50))
    assert result.summary["service_cost"] == 1200 and result.summary["profit"] == -201
    free = account_campaign(pop, target, diff, base, EconomicConfig(service_cost_rate=0))
    assert free.summary["profit"] == 999
    assert_accounts(result, diff)
    evidence(negative_profit=-201, zero_service_profit=999)


def test_V10_no_seeds_and_all_seeds(evidence):
    base, pop, _, _ = chain(0)
    for target in [selection(), selection(0, 1, 2, 3)]:
        diff = simulate(pop, target, base, guaranteed(), event_random=FixedDraws())
        result = account_campaign(pop, target, diff, base, EconomicConfig())
        assert_accounts(result, diff)
        if not target.actor_ids:
            assert result.summary["profit"] == 0
            assert result.prediction_ranking.empty
            assert result.prediction_metrics["precision"] is None
        else:
            assert len(result.transactions) == 4 and result.summary["profit"] == 796
    evidence(k_zero_profit=0, k_n_profit=796)


def test_V11_reproducible_draws_and_order(evidence):
    base, pop, target, diff = chain(0)
    config = EconomicConfig(repurchase_probability=.6, attribution_alpha=.5)
    first = account_campaign(pop, target, diff, base, config)
    shuffled = deepcopy(pop)
    shuffled.nodes = pop.nodes.sample(frac=1, random_state=3)
    shuffled.latent = pop.latent.sample(frac=1, random_state=4)
    changed = deepcopy(diff)
    changed.final_states = changed.final_states.sample(frac=1, random_state=5)
    second = account_campaign(shuffled, target, changed, base, config)
    for name in ("transactions", "repurchase_trials", "actor_accounts", "attribution_credits", "prediction_ranking"):
        assert_frame_equal(getattr(first, name), getattr(second, name))
    rng = EconomicRandom(123, 0)
    values = [rng.uniform(m, i) for m, i in [(3, 0), (5, 1), (2, 2)]]
    assert values == [rng.uniform(m, i) for m, i in [(3, 0), (5, 1), (2, 2)]]
    assert all(0 <= x < 1 for x in values)
    assert values[0] != EconomicRandom(123, 1).uniform(3, 0)
    evidence(row_order_invariant=True, keyed_draws_reproducible=True)


def test_V12_economics_never_mutates_diffusion(evidence):
    base, pop, target, diff = chain(0)
    before = deepcopy(diff)
    population_before = deepcopy(pop)
    for config in [EconomicConfig(), EconomicConfig(repurchase_probability=1, service_cost_fixed=900, attribution_alpha=0)]:
        account_campaign(pop, target, diff, base, config)
    for name in ("periods", "events", "evaluations", "sender_log", "state_history", "final_states", "cascades"):
        assert_frame_equal(getattr(diff, name), getattr(before, name))
    assert_frame_equal(pop.nodes, population_before.nodes)
    assert_frame_equal(pop.latent, population_before.latent)
    assert diff.summary == before.summary
    evidence(m2_frames_unchanged=7, population_unchanged=True)


def test_V13_hidden_value_changes_money_not_behavior(evidence):
    base, pop, target, diff = chain(0)
    first = account_campaign(pop, target, diff, base, EconomicConfig())
    pop.latent.latent_purchase_value *= 2
    again = simulate(pop, target, base, guaranteed(horizon_months=4, adoption_intercept=0), event_random=FixedDraws())
    assert_frame_equal(diff.final_states, again.final_states)
    second = account_campaign(pop, target, again, base, EconomicConfig())
    assert second.summary["revenue"] == 2 * first.summary["revenue"]
    assert second.summary["profit"] == 1599
    evidence(value_multiplier=2, revenue_multiplier=2, behavior_unchanged=True)


def test_V14_prediction_manual_ranks(evidence):
    nodes = pd.DataFrame({"actor_id": [0, 1, 2, 3, 4], "predicted_revenue_score": [.9, .8, .7, .6, 1], "tie_rank": range(5)})
    seeds = pd.DataFrame({"actor_id": [0, 1, 2, 3], "root_revenue": [10, 40, 30, 20]})
    ranks, m = evaluate_seed_prediction(nodes, seeds, .5)
    assert m["universe_size"] == 4 and 4 not in ranks.actor_id.tolist()
    assert m["precision"] == m["recall"] == .5
    assert m["spearman"] == pytest.approx(-.2)
    assert m["mean_absolute_rank_error"] == 1.5 and m["normalized_rank_mae"] == .5
    assert m["monetary_error_of_leadership_index"] is None
    evidence(precision=.5, recall=.5, spearman=-.2, rank_mae=1.5, unselected_excluded=True)


def test_V15_prediction_ties_and_zero_revenue(evidence):
    nodes = pd.DataFrame({"actor_id": range(4), "predicted_revenue_score": [1, 1, 1, 1], "tie_rank": [3, 2, 1, 0]})
    seeds = pd.DataFrame({"actor_id": range(4), "root_revenue": [10, 10, 10, 0]})
    ranks, m = evaluate_seed_prediction(nodes, seeds, .5)
    assert m["realized_leader_count"] == 3 and m["precision"] == .5 and m["recall"] == pytest.approx(1 / 3)
    assert m["spearman"] is None
    assert ranks.loc[ranks.predicted_leader, "actor_id"].tolist() == [2, 3]
    seeds.root_revenue = 0
    _, zero = evaluate_seed_prediction(nodes, seeds, .5)
    assert zero["realized_leader_count"] == 0 and zero["recall"] is None
    evidence(boundary_ties_included=3, constant_rank_spearman_null=True, no_artificial_zero_leader=True)


def test_V16_reject_corrupt_inputs(evidence):
    base, pop, target, diff = chain(0)
    bad_cases = []
    for field, value in [("root_seed", 3), ("parent_id", 2), ("adoption_month", 0), ("cascade_depth", 7)]:
        d = deepcopy(diff); d.final_states.loc[d.final_states.actor_id == 1, field] = value
        bad_cases.append((pop, d))
    p = deepcopy(pop); p.latent.loc[0, "latent_purchase_value"] = float("nan"); bad_cases.append((p, diff))
    p = deepcopy(pop); p.latent = pd.concat([p.latent, p.latent.iloc[:1]]); bad_cases.append((p, diff))
    p = deepcopy(pop); p.nodes.loc[0, "activation_cost"] = -1; bad_cases.append((p, diff))
    d = deepcopy(diff); d.policy = "wrong"; bad_cases.append((pop, d))
    for p, d in bad_cases:
        with pytest.raises(ValueError):
            account_campaign(p, target, d, base, EconomicConfig())
    evidence(corrupt_inputs_rejected=len(bad_cases))


def test_V17_simultaneous_exposure_one_purchase(evidence):
    base, pop = fixture_population(edges=[(0, 1), (0, 2), (1, 3), (2, 3)])
    pop.latent.latent_purchase_value = [100., 200., 300., 400.]
    target = selection(0)
    diff = simulate(pop, target, base, guaranteed(), event_random=FixedDraws())
    assert len(diff.events.loc[diff.events.receiver == 3]) == 2
    result = account_campaign(pop, target, diff, base, EconomicConfig(attribution_alpha=.3))
    assert len(result.transactions.loc[result.transactions.actor_id == 3]) == 1
    assert result.summary["revenue"] == 1000
    assert_accounts(result, diff)
    evidence(simultaneous_messages=2, receiver_purchases=1, revenue=1000)


def test_V18_export_contract_and_no_overwrite(tmp_path, evidence):
    base, pop, target, diff = chain(0)
    config = EconomicConfig(repurchase_probability=.3)
    result = account_campaign(pop, target, diff, base, config)
    hashes = input_hashes(pop, target, diff)
    first = export_economics(tmp_path / "first", result, base, config, inputs=hashes)
    second = export_economics(tmp_path / "second", result, base, config, inputs=hashes)
    manifest = json.loads((first / "manifest.json").read_text())
    for name, digest in manifest["data_sha256"].items():
        assert sha256(first / name) == digest == sha256(second / name)
    assert len(manifest["data_sha256"]) == 12
    with pytest.raises(FileExistsError):
        export_economics(first, result, base, config, inputs=hashes)
    no = selection()
    emptydiff = simulate(pop, no, base, guaranteed())
    empty = account_campaign(pop, no, emptydiff, base, EconomicConfig())
    directory = export_economics(tmp_path / "empty", empty, base, EconomicConfig(), inputs=input_hashes(pop, no, emptydiff))
    assert pd.read_csv(directory / "transactions.csv").empty
    evidence(export_files=13, byte_reproducible=True, overwrite_refused=True, empty_csv_headers=True)


def test_V19_activation_costs_are_actor_specific(evidence):
    base, pop, target, diff = chain(0, 3)
    pop.nodes["activation_cost"] = [10., 900., 800., 30.]
    result = account_campaign(pop, target, diff, base, EconomicConfig())
    assert result.summary["activation_cost"] == 40
    assert result.summary["profit"] == 760
    assert result.activation_costs.actor_id.tolist() == [0, 3]
    assert result.activation_costs.month.eq(0).all()
    assert_accounts(result, diff)
    evidence(selected_cost=40, unselected_cost_ignored=True, profit=760)


def test_V20_one_month_horizon_and_overflow(evidence):
    base, pop, target, diff = chain(0, horizon=1)
    result = account_campaign(pop, target, diff, base, EconomicConfig(repurchase_probability=1))
    assert len(result.transactions) == 1 and result.repurchase_trials.empty
    assert result.summary["revenue"] == 100 and result.summary["profit"] == 79
    base, pop, target, diff = chain(0)
    with pytest.raises(ValueError, match="overflow"):
        account_campaign(pop, target, diff, base, EconomicConfig(repurchase_probability=1, repurchase_value_factor=1e308), event_random=LowDraws())
    evidence(horizon_one_revenue=100, no_post_horizon_repurchase=True, overflow_rejected=True)


def test_V21_paired_integrated_campaigns(tmp_path, evidence):
    destination = Path(os.environ.get("M3_ACCEPTANCE_OUTPUT", str(tmp_path / "m3_demonstrations")))
    m2_path = Path(os.environ["M2_ACCEPTANCE_OUTPUT"]) if "M2_ACCEPTANCE_OUTPUT" in os.environ else None
    base, dc, ec = Config(), DiffusionConfig(), EconomicConfig()
    summaries, reference_count = [], 0
    for rep in range(3):
        pop = initialize(base, rep)
        targets, _ = run_policies(pop, base)
        for policy in POLICIES:
            target = targets[policy]
            diff = simulate(pop, target, base, dc)
            result = account_campaign(pop, target, diff, base, ec)
            assert_accounts(result, diff)
            assert result.summary["activation_cost"] == 20 and result.summary["repurchases"] == 0
            assert result.prediction_metrics["universe_size"] == 20
            inputs = input_hashes(pop, target, diff)
            directory = destination / f"rep_{rep:03d}" / policy
            p_ref = d_ref = ""
            if m2_path is not None:
                p_ref = os.path.relpath(m2_path / f"rep_{rep:03d}" / "population", directory)
                d_ref = os.path.relpath(m2_path / f"rep_{rep:03d}" / policy, directory)
                for name in ["nodes_ex_ante.csv", "latent_values.csv"]:
                    assert inputs[name] == sha256(m2_path / f"rep_{rep:03d}" / "population" / name)
                for name in ["final_states.csv", "wom_events.csv"]:
                    assert inputs[name] == sha256(m2_path / f"rep_{rep:03d}" / policy / name)
                reference_count += 4
            export_economics(directory, result, base, ec, inputs=inputs, population_reference=p_ref, diffusion_reference=d_ref)
            summaries.append(result.summary)
    table = pd.DataFrame(summaries).sort_values(["repetition", "policy"])
    write_csv(destination / "summary_all.csv", table)
    assert len(table) == 21
    evidence(campaigns=21, repetitions=3, policies=7, actors=600, selected=20, horizon=60,
             total_initial_purchases=int(table.initial_purchases.sum()), total_revenue=float(table.revenue.sum()),
             m1_m2_input_hashes_verified=reference_count,
             revenue_range=[float(table.revenue.min()), float(table.revenue.max())],
             adoption_range=[int(table.adoption_count.min()), int(table.adoption_count.max())])


def test_V22_repurchase_and_alpha_on_full_population(tmp_path, evidence):
    base = Config()
    pop = initialize(base, 0)
    targets, _ = run_policies(pop, base, ["random", "predicted_revenue"])
    outcomes = []
    for policy in reversed(list(targets)):
        target = targets[policy]
        diff = simulate(pop, target, base, DiffusionConfig())
        results = []
        for alpha in (0, .5, 1):
            config = EconomicConfig(repurchase_probability=.05, attribution_alpha=alpha)
            result = account_campaign(pop, target, diff, base, config)
            assert_accounts(result, diff)
            assert result.summary["repurchases"] > 0
            results.append(result)
            if "M3_ACCEPTANCE_OUTPUT" in os.environ:
                directory = Path(os.environ["M3_ACCEPTANCE_OUTPUT"]).parent / "m3_supplementary" / policy / f"alpha_{alpha:g}"
                m2 = Path(os.environ["M2_ACCEPTANCE_OUTPUT"]) / "rep_000"
                export_economics(directory, result, base, config, inputs=input_hashes(pop, target, diff),
                    population_reference=os.path.relpath(m2 / "population", directory),
                    diffusion_reference=os.path.relpath(m2 / policy, directory))
        for result in results[1:]:
            assert_frame_equal(result.transactions, results[0].transactions)
            assert_frame_equal(result.periods, results[0].periods)
            assert result.prediction_metrics == results[0].prediction_metrics
        outcomes.append({"policy": policy, "repurchases": results[0].summary["repurchases"], "revenue": results[0].summary["revenue"]})
    evidence(supplementary_campaigns=6, repurchase_probability=.05, alpha_values=[0, .5, 1],
             firm_and_prediction_invariant_to_alpha=True, outcomes=outcomes)
