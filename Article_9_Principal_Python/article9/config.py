"""Validated assumptions. No parameter is estimated from campaign outcomes."""
from dataclasses import asdict, dataclass
import math


def integer(value, name, minimum=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")


def weights_valid(weights, size, name):
    if len(weights) != size or any(not math.isfinite(x) or x < 0 for x in weights):
        raise ValueError(f"{name}: expected {size} finite nonnegative weights")
    if not math.isclose(sum(weights), 1.0, rel_tol=0, abs_tol=1e-12):
        raise ValueError(f"{name} must sum to one")


@dataclass(frozen=True)
class Config:
    n_agents: int = 600
    n_communities: int = 6
    mean_degree: float = 12.0
    mixing_fraction: float = 0.20
    k: int = 20
    activation_cost: float = 1.0
    value_noise_sigma: float = 0.35
    beta_alpha: float = 2.0
    beta_beta: float = 2.0
    master_seed: int = 20260925
    horizon_months: int = 60  # Reserved for M2; no diffusion steps in M1.
    require_modular: bool = True
    revenue_weights: tuple = (0.20, 0.20, 0.20, 0.20, 0.20)
    combined_weights: tuple = (0.25, 0.25, 0.25, 0.25)
    hybrid_weights: tuple = (0.25, 0.25, 0.25, 0.25)

    def __post_init__(self):
        for name, minimum in [("n_agents", 4), ("n_communities", 2),
                              ("k", 0), ("master_seed", 0), ("horizon_months", 1)]:
            integer(getattr(self, name), name, minimum)
        if self.n_agents % self.n_communities or self.n_agents // self.n_communities < 2:
            raise ValueError("Use equal communities with at least two people each")
        if self.k > self.n_agents:
            raise ValueError("k exceeds the eligible population")
        for name in ("mean_degree", "mixing_fraction", "activation_cost",
                     "value_noise_sigma", "beta_alpha", "beta_beta"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        if not 0 <= self.mixing_fraction <= 1 or self.mean_degree < 0:
            raise ValueError("Invalid mean degree or mixing fraction")
        if self.activation_cost <= 0 or self.value_noise_sigma < 0:
            raise ValueError("Cost must be positive; noise sigma must be nonnegative")
        if self.beta_alpha <= 0 or self.beta_beta <= 0:
            raise ValueError("Beta shape parameters must be positive")
        if not isinstance(self.require_modular, bool):
            raise ValueError("require_modular must be boolean")
        p_in, p_out = self.edge_probabilities()
        if not (0 <= p_in <= 1 and 0 <= p_out <= 1):
            raise ValueError("Link probabilities must be in [0, 1]; no clipping is permitted")
        if self.require_modular and not p_in > p_out:
            raise ValueError("Modular scenarios require p_in > p_out")
        for name, size in [("revenue_weights", 5), ("combined_weights", 4), ("hybrid_weights", 4)]:
            values = tuple(getattr(self, name))
            weights_valid(values, size, name)
            object.__setattr__(self, name, values)

    def edge_probabilities(self):
        size = self.n_agents // self.n_communities
        return (self.mean_degree * (1 - self.mixing_fraction) / (size - 1),
                self.mean_degree * self.mixing_fraction / (self.n_agents - size))

    def to_dict(self):
        return asdict(self)

