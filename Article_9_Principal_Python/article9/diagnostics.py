"""Structural opportunity is deliberately distinct from observed diffusion."""
from collections import Counter
from itertools import combinations_with_replacement
import json
import networkx as nx
import numpy as np
import pandas as pd
from .attributes import ATTRIBUTES
from .scores import PURE_SCORES


def network_diagnostics(graph):
    n, m = graph.number_of_nodes(), graph.number_of_edges()
    degrees = np.array([d for _, d in graph.degree], dtype=float)
    communities = sorted({graph.nodes[i]["community_id"] for i in graph})
    partition = [{i for i in graph if graph.nodes[i]["community_id"] == group} for group in communities]
    components = list(nx.connected_components(graph))
    largest = max(map(len, components), default=0) / n if n else 0.0
    external = sum(graph.nodes[i]["community_id"] != graph.nodes[j]["community_id"] for i, j in graph.edges)
    return {"n_agents": n, "n_edges": m, "density": nx.density(graph),
            "degree_mean": float(degrees.mean()) if n else 0.0,
            "degree_min": int(degrees.min()) if n else 0,
            "degree_max": int(degrees.max()) if n else 0,
            "degree_sd_population": float(degrees.std(ddof=0)) if n else 0.0,
            "average_clustering": nx.average_clustering(graph, count_zeros=True) if n else 0.0,
            "n_components": len(components), "largest_component_fraction": largest,
            "isolated_nodes": int((degrees == 0).sum()),
            "external_edge_fraction": external / m if m else None,
            "external_edge_fraction_reason": "" if m else "no_edges",
            "modularity": nx.community.modularity(graph, partition) if m else None,
            "modularity_reason": "" if m else "no_edges",
            "warning": "largest_component_below_95_percent" if largest < .95 else ""}


def audience_diagnostics(graph, selected_ids):
    selected = set(selected_ids)
    counts = Counter(j for i in sorted(selected) for j in graph[i] if j not in selected)
    unique, incidences = len(counts), sum(counts.values())
    return {"potential_unique_neighbors": unique, "potential_contact_incidences": incidences,
            "potential_redundancy": (incidences - unique) / incidences if incidences else 0.0,
            "shared_audience_fraction": sum(v >= 2 for v in counts.values()) / unique if unique else 0.0,
            "selected_communities": len({graph.nodes[i]["community_id"] for i in selected}),
            "potential_audience_communities": len({graph.nodes[j]["community_id"] for j in counts})}


def policy_diagnostics(graph, nodes, result):
    chosen = nodes.set_index("actor_id", drop=False).loc[result.actor_ids]
    output = {"policy": result.policy, "selected_count": len(chosen),
              "activation_cost_total": float(chosen.activation_cost.sum()),
              "selected_by_community": json.dumps({str(int(k)): int(v) for k, v in chosen.groupby("community_id").size().items()}, sort_keys=True),
              "requested_quotas": json.dumps({str(k): int(v) for k, v in result.quotas.items()}, sort_keys=True),
              "component_order": json.dumps(result.component_order),
              "hybrid_duplicate_skips": int((result.audit.reason == "duplicate_skipped").sum()),
              **audience_diagnostics(graph, result.actor_ids)}
    for name in ["degree", "structural_reach", "community_reach", *ATTRIBUTES,
                 "predicted_purchase_value", *PURE_SCORES.values(), "combined_score"]:
        series = chosen[name]
        output[f"{name}_mean"] = float(series.mean()) if len(series) else None
        output[f"{name}_median"] = float(series.median()) if len(series) else None
        output[f"{name}_min"] = float(series.min()) if len(series) else None
        output[f"{name}_max"] = float(series.max()) if len(series) else None
        output[f"{name}_sd_population"] = float(series.std(ddof=0)) if len(series) else None
        output[f"{name}_mean_minus_population"] = float(series.mean() - nodes[name].mean()) if len(series) else None
    return output


def attribute_correlations(nodes):
    columns = ["degree", *ATTRIBUTES]
    ranks = nodes[columns].rank(method="average")
    rows = []
    for a, b in combinations_with_replacement(columns, 2):
        constant = nodes[a].nunique() < 2 or nodes[b].nunique() < 2
        value = None if constant else float(ranks[a].corr(ranks[b]))
        rows.append({"variable_a": a, "variable_b": b, "spearman": value,
                     "n": len(nodes), "reason": "constant_variable" if constant else ""})
    return pd.DataFrame(rows)


def policy_overlap(results):
    rows = []
    for a in sorted(results):
        for b in sorted(results):
            left, right = set(results[a].actor_ids), set(results[b].actor_ids)
            common, union = len(left & right), len(left | right)
            rows.append({"policy_a": a, "policy_b": b, "intersection": common,
                         "union": union, "jaccard": common / union if union else 1.0})
    return pd.DataFrame(rows)

