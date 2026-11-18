"""Initialization and selection orchestration, without a diffusion process."""
from dataclasses import dataclass
import pandas as pd
from .attributes import assign_attributes, initial_states
from .network import build_network
from .randomness import Streams
from .scores import compute_scores
from .selection import POLICIES, select_actors


@dataclass
class Population:
    graph: object
    nodes: pd.DataFrame
    latent: pd.DataFrame
    repetition: int


def initialize(config, repetition=0):
    streams = Streams(config.master_seed, repetition)
    graph = build_network(config, streams)
    nodes, latent = assign_attributes(graph, config, streams)
    return Population(graph, compute_scores(graph, nodes, config), latent, repetition)


def run_policies(population, config, policies=POLICIES):
    policies = tuple(policies)
    if len(set(policies)) != len(policies):
        raise ValueError("Policy list contains duplicates")
    results, states = {}, {}
    for policy in policies:
        streams = Streams(config.master_seed, population.repetition)
        result = select_actors(population.nodes, policy, config.k, streams, config)
        results[policy] = result
        states[policy] = initial_states(population.nodes.actor_id, result.actor_ids)
    return results, states
