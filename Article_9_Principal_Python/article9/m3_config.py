"""Illustrative economics in abstract monetary units; no empirical calibration."""
from dataclasses import asdict, dataclass
import math

M3_VERSION = "0.3.0"


@dataclass(frozen=True)
class EconomicConfig:
    service_cost_rate: float = 0.20
    service_cost_fixed: float = 0.0
    repurchase_probability: float = 0.0
    repurchase_value_factor: float = 1.0
    attribution_alpha: float = 1.0
    leader_fraction: float = 0.20

    def __post_init__(self):
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be finite and numeric")
            if value < 0:
                raise ValueError(f"{name} must be nonnegative")
        for name in ("service_cost_rate", "repurchase_probability", "attribution_alpha", "leader_fraction"):
            if getattr(self, name) > 1:
                raise ValueError(f"{name} must be in [0, 1]")
        if self.leader_fraction == 0 or self.repurchase_value_factor == 0:
            raise ValueError("leader_fraction and repurchase_value_factor must be positive")

    def to_dict(self):
        return asdict(self)
