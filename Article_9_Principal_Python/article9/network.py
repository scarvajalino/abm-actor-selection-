"""Fixed, undirected, simple stochastic block network."""
import networkx as nx
import numpy as np
import pandas as pd


def build_network(config, streams):
    n, c = config.n_agents, config.n_communities
    permutation = streams.rng("communities").permutation(n)
    community = np.empty(n, dtype=int)
    community[permutation] = np.repeat(np.arange(c), n // c)
    source, target = np.triu_indices(n, k=1)
    p_in, p_out = config.edge_probabilities()
    probabilities = np.where(community[source] == community[target], p_in, p_out)
    # Canonical pair ordering and draws independent of probabilities support pairing.
    keep = streams.rng("edges").random(len(source)) < probabilities
    graph = nx.Graph()
    graph.add_nodes_from((i, {"community_id": int(community[i])}) for i in range(n))
    graph.add_edges_from(zip(source[keep].tolist(), target[keep].tolist()))
    return graph


def structural_table(graph):
    if graph.is_directed() or graph.is_multigraph() or nx.number_of_selfloops(graph):
        raise ValueError("Expected a simple undirected graph without self-loops")
    ids = sorted(graph.nodes)
    groups = {graph.nodes[i]["community_id"] for i in ids}
    c = len(groups)
    max_degree = max(dict(graph.degree).values(), default=0)
    return pd.DataFrame([
        {"actor_id": i, "community_id": graph.nodes[i]["community_id"],
         "degree": graph.degree[i],
         "structural_reach": graph.degree[i] / max_degree if max_degree else 0.0,
         "community_reach": len({graph.nodes[j]["community_id"] for j in graph[i]}) / c if c else 0.0}
        for i in ids
    ]).set_index("actor_id", drop=False)


def edge_table(graph):
    edges = sorted((min(int(i), int(j)), max(int(i), int(j))) for i, j in graph.edges)
    return pd.DataFrame([
        {"source": i, "target": j,
         "same_community": graph.nodes[i]["community_id"] == graph.nodes[j]["community_id"]}
        for i, j in edges
    ], columns=["source", "target", "same_community"])

