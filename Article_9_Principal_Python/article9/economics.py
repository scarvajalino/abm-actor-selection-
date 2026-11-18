"""Post-diffusion purchase ledger and conservative alternative attribution views."""
from dataclasses import dataclass
from collections import defaultdict
import math
import numpy as np
import pandas as pd
from .economic_random import EconomicRandom
from .prediction import evaluate_seed_prediction

TRANSACTION_COLUMNS = ["transaction_id", "month", "actor_id", "kind", "adoption_month",
                       "parent_id", "root_seed", "immediate_owner", "revenue", "service_cost", "margin"]
TRIAL_COLUMNS = ["month", "actor_id", "satisfaction", "eligible", "probability", "draw", "purchased", "reason"]
CREDIT_COLUMNS = ["transaction_id", "month", "actor_id", "weight", "revenue", "service_cost", "margin"]


@dataclass
class EconomicResult:
    policy: str
    repetition: int
    transactions: pd.DataFrame
    activation_costs: pd.DataFrame
    repurchase_trials: pd.DataFrame
    attribution_credits: pd.DataFrame
    actor_accounts: pd.DataFrame
    seed_accounts: pd.DataFrame
    periods: pd.DataFrame
    prediction_ranking: pd.DataFrame
    prediction_metrics: dict
    summary: dict


def _validated_inputs(population, selection, diffusion):
    ids = sorted(population.graph.nodes)
    for label, frame in (("nodes", population.nodes), ("latent", population.latent), ("states", diffusion.final_states)):
        if frame.actor_id.duplicated().any() or set(frame.actor_id) != set(ids):
            raise ValueError(f"{label} must contain each actor exactly once")
    chosen = set(selection.actor_ids)
    if len(chosen) != len(selection.actor_ids) or not chosen <= set(ids):
        raise ValueError("Invalid selected actors")
    if diffusion.policy != selection.policy or diffusion.repetition != population.repetition:
        raise ValueError("Campaign identity mismatch")
    final = diffusion.final_states.set_index("actor_id").loc[ids].copy()
    nodes = population.nodes.reset_index(drop=True).set_index("actor_id").loc[ids].copy()
    latent = population.latent.set_index("actor_id").loc[ids, "latent_purchase_value"]
    for name in ("adopted", "selected", "satisfied"):
        if not pd.api.types.is_bool_dtype(final[name]):
            raise ValueError(f"{name} must contain booleans")
    if set(final.index[final.selected]) != chosen:
        raise ValueError("Diffusion and selection disagree")
    months = diffusion.periods.month.tolist()
    if not months or months != list(range(len(months))) or len(months) < 2:
        raise ValueError("Diffusion must contain contiguous months 0..H")
    horizon = len(months) - 1
    if not (final.month == horizon).all():
        raise ValueError("Final state horizon mismatch")
    for name in ("activation_cost", "predicted_purchase_value", "predicted_revenue_score", "tie_rank"):
        vals = nodes[name].to_numpy(dtype=float)
        if not np.isfinite(vals).all() or (vals < 0).any():
            raise ValueError(f"Invalid {name}")
    if not np.isfinite(latent.to_numpy()).all() or (latent <= 0).any():
        raise ValueError("Latent purchase values must be finite and positive")
    for i, row in final.iterrows():
        if not row.adopted:
            if any(pd.notna(row[c]) for c in ("adoption_month", "parent_id", "root_seed", "cascade_depth")):
                raise ValueError("Nonadopter has adoption lineage")
            continue
        month, root, depth = row.adoption_month, row.root_seed, row.cascade_depth
        if not (pd.notna(month) and 1 <= month <= horizon and int(month) == month):
            raise ValueError("Invalid adoption month")
        if root not in chosen or not pd.notna(depth) or depth < 0 or int(depth) != depth:
            raise ValueError("Invalid cascade root or depth")
        if not math.isfinite(row.satisfaction) or not 0 <= row.satisfaction <= 1:
            raise ValueError("Invalid satisfaction")
        if row.acquisition_source == "seed":
            if i not in chosen or root != i or depth != 0 or pd.notna(row.parent_id) or month != 1:
                raise ValueError("Invalid direct seed lineage")
        elif row.acquisition_source == "wom":
            if row.parent_id not in final.index or not population.graph.has_edge(i, row.parent_id):
                raise ValueError("Invalid parent")
            parent = final.loc[row.parent_id]
            if not parent.adopted or parent.adoption_month >= month or parent.root_seed != root or parent.cascade_depth + 1 != depth:
                raise ValueError("Inconsistent or cyclic lineage")
        else:
            raise ValueError("Unknown acquisition source")
    return ids, chosen, nodes, latent, final, horizon


def account_campaign(population, selection, diffusion, model_config, config, *, event_random=None):
    """Value existing adoptions; never mutate selection, behavior or M2 state."""
    ids, chosen, nodes, latent, final, horizon = _validated_inputs(population, selection, diffusion)
    field = event_random or EconomicRandom(model_config.master_seed, population.repetition)
    purchases, trials = [], []

    def purchase(i, month, kind, factor):
        row = final.loc[i]
        value = float(latent.loc[i]) * factor
        service = config.service_cost_fixed + config.service_cost_rate * value
        if not math.isfinite(value) or not math.isfinite(service):
            raise ValueError("Economic transaction overflow")
        parent = None if pd.isna(row.parent_id) else int(row.parent_id)
        purchases.append({"transaction_id": f"m{month}_a{i}_{kind}", "month": month, "actor_id": i,
            "kind": kind, "adoption_month": int(row.adoption_month), "parent_id": parent,
            "root_seed": int(row.root_seed), "immediate_owner": i if parent is None else parent,
            "revenue": value, "service_cost": service, "margin": value - service})

    for i in ids:
        row = final.loc[i]
        if not row.adopted:
            continue
        purchase(i, int(row.adoption_month), "initial", 1.0)
        if config.repurchase_probability == 0:
            continue
        for month in range(int(row.adoption_month) + 1, horizon + 1):
            eligible = bool(row.satisfied)
            probability = config.repurchase_probability * row.satisfaction if eligible else 0.0
            draw = field.uniform(month, i) if eligible else None
            success = eligible and draw < probability
            trials.append({"month": month, "actor_id": i, "satisfaction": row.satisfaction,
                "eligible": eligible, "probability": probability, "draw": draw, "purchased": success,
                "reason": "purchased" if success else "draw_failed" if eligible else "unsatisfied"})
            if success:
                purchase(i, month, "repurchase", config.repurchase_value_factor)
    tx = pd.DataFrame(purchases, columns=TRANSACTION_COLUMNS).sort_values(["month", "actor_id"]).reset_index(drop=True)
    costs = pd.DataFrame([{"month": 0, "actor_id": i, "activation_cost": float(nodes.loc[i, "activation_cost"])}
                          for i in sorted(chosen)], columns=["month", "actor_id", "activation_cost"])
    credit_rows = []
    for row in tx.itertuples():
        weights = defaultdict(float)
        weights[row.immediate_owner] += 1 - config.attribution_alpha
        weights[row.root_seed] += config.attribution_alpha
        for owner, weight in sorted(weights.items()):
            if weight > 0:
                credit_rows.append({"transaction_id": row.transaction_id, "month": row.month,
                    "actor_id": owner, "weight": weight, "revenue": weight * row.revenue,
                    "service_cost": weight * row.service_cost, "margin": weight * row.margin})
    credits = pd.DataFrame(credit_rows, columns=CREDIT_COLUMNS)
    accounts = pd.DataFrame({"actor_id": ids, "selected": [i in chosen for i in ids]})
    def totals(frame, key, value):
        if frame.empty:
            return {}
        return {int(i): math.fsum(group[value]) for i, group in frame.groupby(key, sort=True)}
    for prefix, frame, key in (("own", tx, "actor_id"), ("immediate", tx, "immediate_owner"),
                               ("root", tx, "root_seed"), ("attributed", credits, "actor_id")):
        for value in ("revenue", "service_cost"):
            mapping = totals(frame, key, value)
            accounts[f"{prefix}_{value}"] = [mapping.get(i, 0.0) for i in ids]
    costs_by_id = costs.set_index("actor_id").activation_cost.to_dict()
    accounts["activation_cost"] = [costs_by_id.get(i, 0.0) for i in ids]
    for prefix in ("own", "immediate", "root", "attributed"):
        accounts[f"{prefix}_profit"] = accounts[f"{prefix}_revenue"] - accounts[f"{prefix}_service_cost"] - accounts.activation_cost
    # These referral columns are descriptive; they are not an additional firm ledger.
    referral = tx.loc[tx.parent_id.notna()]
    direct = totals(referral, "parent_id", "revenue")
    accounts["direct_referral_revenue"] = [direct.get(i, 0.0) for i in ids]
    seed_accounts = accounts.loc[accounts.selected].reset_index(drop=True)
    monthly = []
    cumulative_revenue = cumulative_service = 0.0
    activation = math.fsum(costs.activation_cost)
    by_month = {m: group for m, group in tx.groupby("month")}
    for month in range(horizon + 1):
        group = by_month.get(month, tx.iloc[:0])
        first = math.fsum(group.loc[group.kind == "initial", "revenue"])
        repeat = math.fsum(group.loc[group.kind == "repurchase", "revenue"])
        service = math.fsum(group.service_cost)
        revenue = first + repeat
        cumulative_revenue += revenue
        cumulative_service += service
        paid = activation if month == 0 else 0.0
        monthly.append({"month": month, "initial_purchases": int((group.kind == "initial").sum()),
            "repurchases": int((group.kind == "repurchase").sum()), "initial_revenue": first,
            "repurchase_revenue": repeat, "revenue": revenue, "service_cost": service,
            "activation_cost": paid, "profit": revenue - service - paid,
            "cumulative_revenue": cumulative_revenue, "cumulative_service_cost": cumulative_service,
            "cumulative_activation_cost": activation, "cumulative_profit": cumulative_revenue - cumulative_service - activation})
    periods = pd.DataFrame(monthly)
    ranking, metrics = evaluate_seed_prediction(nodes.reset_index(), seed_accounts, config.leader_fraction)
    initial = tx.loc[tx.kind == "initial"]
    errors = [abs(float(nodes.loc[r.actor_id, "predicted_purchase_value"]) - r.revenue) for r in initial.itertuples()]
    revenue, service = math.fsum(tx.revenue), math.fsum(tx.service_cost)
    summary = {**diffusion.summary, "initial_purchases": len(initial), "repurchases": len(tx) - len(initial),
        "initial_revenue": math.fsum(initial.revenue), "repurchase_revenue": math.fsum(tx.loc[tx.kind == "repurchase", "revenue"]),
        "revenue": revenue, "service_cost": service, "activation_cost": activation,
        "profit": revenue - service - activation,
        "revenue_per_selected_actor": revenue / len(chosen) if chosen else None,
        "revenue_per_adopter": revenue / len(initial) if len(initial) else None,
        "purchase_value_mae_among_adopters": math.fsum(errors) / len(errors) if errors else None,
        "conditional_leader_precision": metrics["precision"], "conditional_leader_recall": metrics["recall"],
        "conditional_leader_spearman": metrics["spearman"], "conditional_normalized_rank_mae": metrics["normalized_rank_mae"],
        "attribution_alpha": config.attribution_alpha, "monetary_unit": "abstract_units"}
    numeric = accounts.select_dtypes(include="number").to_numpy()
    if not np.isfinite(numeric).all() or not np.isfinite(periods.to_numpy()).all():
        raise ValueError("Economic aggregates overflow")
    return EconomicResult(selection.policy, population.repetition, tx, costs,
        pd.DataFrame(trials, columns=TRIAL_COLUMNS).sort_values(["month", "actor_id"]).reset_index(drop=True),
        credits, accounts, seed_accounts, periods, ranking, metrics, summary)
