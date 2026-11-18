"""Ex-ante data and hidden economic values are returned separately."""
import numpy as np
import pandas as pd
from .network import structural_table

ATTRIBUTES = ("activity", "credibility", "expertise", "expertise_fit",
              "recommendation_propensity", "need", "product_fit", "predicted_economic_potential")
BASE_COLUMNS = ("actor_id", "community_id", "degree", "structural_reach", "community_reach",
                *ATTRIBUTES, "predicted_purchase_value", "activation_cost", "tie_rank")


def assign_attributes(graph, config, streams):
    nodes = structural_table(graph)
    n = len(nodes)
    for name in ATTRIBUTES:
        nodes[name] = streams.rng(name).beta(config.beta_alpha, config.beta_beta, size=n)
    nodes["predicted_purchase_value"] = 50 + 150 * nodes["predicted_economic_potential"]
    nodes["activation_cost"] = config.activation_cost
    ranks = np.empty(n, dtype=int)
    ranks[streams.rng("actor_ties").permutation(n)] = np.arange(n)
    nodes["tie_rank"] = ranks
    z = streams.rng("latent_value").normal(size=n)
    latent_values = nodes["predicted_purchase_value"].to_numpy() * np.exp(
        config.value_noise_sigma * z - config.value_noise_sigma ** 2 / 2)
    if not np.all(np.isfinite(latent_values) & (latent_values > 0)):
        raise ValueError("Latent values overflowed or underflowed; review value_noise_sigma")
    latent = pd.DataFrame({"actor_id": nodes.actor_id.to_numpy(), "latent_purchase_value": latent_values})
    return nodes, latent


def initial_states(actor_ids, selected_ids=()):
    ids = sorted(int(i) for i in actor_ids)
    chosen = set(selected_ids)
    if not chosen.issubset(ids):
        raise ValueError("Selected actors must belong to population")
    return pd.DataFrame({"actor_id": ids, "selected": [i in chosen for i in ids],
                         "aware": False, "adopted": False, "wom_active": False,
                         "satisfaction": np.nan, "exposures": 0, "revenue": 0.0})

