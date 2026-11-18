"""Stable random streams; fresh generators make policy order irrelevant."""
import numpy as np
from .config import integer

STREAM_IDS = {
    "communities": 100, "edges": 101,
    "activity": 200, "credibility": 201, "expertise": 202,
    "expertise_fit": 203, "recommendation_propensity": 204,
    "need": 205, "product_fit": 206, "predicted_economic_potential": 207,
    "latent_value": 208, "actor_ties": 209,
    "random_selection": 300, "community_ties": 301,
    "community_sample": 302, "hybrid_ties": 303, "hybrid_order": 304,
}


class Streams:
    def __init__(self, master_seed, repetition):
        integer(master_seed, "master_seed")
        integer(repetition, "repetition")
        self.master_seed = master_seed
        self.repetition = repetition

    def rng(self, component):
        seed = np.random.SeedSequence([self.master_seed, self.repetition, STREAM_IDS[component]])
        return np.random.Generator(np.random.PCG64(seed))

    def record(self):
        return {name: {"component_id": code,
                       "entropy": [self.master_seed, self.repetition, code],
                       "bit_generator": "PCG64"}
                for name, code in STREAM_IDS.items()}

