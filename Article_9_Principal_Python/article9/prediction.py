"""Conditional seed ranking, never counterfactual performance of unselected actors."""
import math
import numpy as np
import pandas as pd


def evaluate_seed_prediction(nodes, seed_accounts, leader_fraction):
    if not 0 < leader_fraction <= 1:
        raise ValueError("leader_fraction must be in (0, 1]")
    table = seed_accounts[["actor_id", "root_revenue"]].merge(
        nodes[["actor_id", "predicted_revenue_score", "tie_rank"]], on="actor_id", validate="one_to_one")
    n = len(table)
    if n != len(seed_accounts):
        raise ValueError("Missing selected actors in prediction inputs")
    table = table.sort_values(["predicted_revenue_score", "tie_rank", "actor_id"],
                              ascending=[False, True, True]).reset_index(drop=True)
    q = math.ceil(n * leader_fraction)
    table["predicted_order"] = np.arange(1, n + 1)
    table["predicted_rank_average"] = table.predicted_revenue_score.rank(ascending=False, method="average")
    table["realized_rank_average"] = table.root_revenue.rank(ascending=False, method="average")
    table["predicted_leader"] = table.predicted_order <= q
    positive = table.loc[table.root_revenue > 0, "root_revenue"].sort_values(ascending=False)
    cutoff = float(positive.iloc[min(q, len(positive)) - 1]) if len(positive) else None
    # Include every positive tie at the cutoff; zero revenue is never a realized leader.
    table["realized_leader"] = (table.root_revenue >= cutoff) if cutoff is not None else False
    table["absolute_rank_error"] = (table.predicted_rank_average - table.realized_rank_average).abs()
    hits = int((table.predicted_leader & table.realized_leader).sum())
    realized = int(table.realized_leader.sum())
    variable = n >= 2 and table.predicted_revenue_score.nunique() > 1 and table.root_revenue.nunique() > 1
    rho = float(np.corrcoef(table.predicted_rank_average, table.realized_rank_average)[0, 1]) if variable else None
    metrics = {"universe": "selected_actors_in_this_campaign", "outcome": "root_cascade_revenue",
               "universe_size": n, "leader_fraction": leader_fraction, "predicted_leader_count": q,
               "realized_leader_count": realized, "realized_cutoff": cutoff, "true_positives": hits,
               "false_positives": q - hits, "false_negatives": realized - hits,
               "precision": hits / q if q else None, "recall": hits / realized if realized else None,
               "spearman": rho, "spearman_status": "defined" if variable else "insufficient_or_constant_ranks",
               "mean_absolute_rank_error": float(table.absolute_rank_error.mean()) if n else None,
               "normalized_rank_mae": float(table.absolute_rank_error.mean() / (n - 1)) if n > 1 else None,
               "realized_boundary_ties_included": True,
               "population_wide_counterfactual_claim": False,
               "monetary_error_of_leadership_index": None}
    return table.sort_values("actor_id").reset_index(drop=True), metrics
