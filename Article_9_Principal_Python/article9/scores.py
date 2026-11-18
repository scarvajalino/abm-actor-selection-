"""Transparent indices, not estimates in currency or adoption probabilities."""
import numpy as np
from .attributes import ATTRIBUTES, BASE_COLUMNS

PURE_SCORES = {"hubs": "hub_score", "influencers": "influencer_score",
               "opinion_leaders": "opinion_score", "predicted_revenue": "predicted_revenue_score"}
SCORE_COLUMNS = ("hub_score", "influencer_score", "opinion_score", "neighbor_potential",
                 "neighbor_fit", "conversion_proxy", "predicted_revenue_score", "combined_score")
EX_ANTE_COLUMNS = (*BASE_COLUMNS, *SCORE_COLUMNS)


def compute_scores(graph, nodes, config):
    # Explicit projection discards hidden or future fields even if a caller adds them.
    out = nodes.loc[:, list(BASE_COLUMNS)].copy().set_index("actor_id", drop=False).sort_index()
    if not out.index.is_unique or set(out.index) != set(graph.nodes):
        raise ValueError("Node identifiers must uniquely match the graph")
    bounded = out.loc[:, [*ATTRIBUTES, "structural_reach", "community_reach"]].to_numpy(dtype=float)
    if not np.isfinite(bounded).all() or np.any((bounded < 0) | (bounded > 1)):
        raise ValueError("Ex-ante attributes must be finite in [0, 1]")
    out["hub_score"] = out.structural_reach
    out["influencer_score"] = out.activity
    out["opinion_score"] = out.credibility * out.expertise * out.expertise_fit
    potential = out.predicted_economic_potential.to_dict()
    fit = (out.need * out.product_fit).to_dict()
    out["neighbor_potential"] = [float(np.mean([potential[j] for j in sorted(graph[i])])) if graph.degree[i] else 0.0 for i in out.index]
    out["neighbor_fit"] = [float(np.mean([fit[j] for j in sorted(graph[i])])) if graph.degree[i] else 0.0 for i in out.index]
    out["conversion_proxy"] = out.opinion_score * out.neighbor_fit
    components = ["predicted_economic_potential", "structural_reach", "neighbor_potential", "conversion_proxy", "activity"]
    out["predicted_revenue_score"] = out[components].to_numpy() @ np.asarray(config.revenue_weights)
    out["combined_score"] = out[list(PURE_SCORES.values())].to_numpy() @ np.asarray(config.combined_weights)
    return out
