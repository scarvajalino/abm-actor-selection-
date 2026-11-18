"""Illustrative, uncalibrated M2 assumptions; M1 selection rules are unchanged."""
from dataclasses import asdict, dataclass
import math
from .config import integer

M2_VERSION = "0.2.0"


@dataclass(frozen=True)
class DiffusionConfig:
    horizon_months: int = 60
    product_quality: float = 0.75
    product_complexity: float = 0.50
    base_contact_capacity: int = 4
    satisfaction_quality_weight: float = 0.60
    satisfaction_threshold: float = 0.60
    adoption_intercept: float = -2.0
    need_effect: float = 2.0
    fit_effect: float = 2.0
    quality_effect: float = 1.0
    risk_effect: float = 1.0
    credibility_effect: float = 2.0
    social_proof_effect: float = 0.50
    social_proof_saturation: int = 3

    def __post_init__(self):
        integer(self.horizon_months, "horizon_months", 1)
        integer(self.base_contact_capacity, "base_contact_capacity", 0)
        integer(self.social_proof_saturation, "social_proof_saturation", 1)
        unit_fields = ("product_quality", "product_complexity", "satisfaction_quality_weight", "satisfaction_threshold")
        numeric_fields = (*unit_fields, "adoption_intercept", "need_effect", "fit_effect",
                          "quality_effect", "risk_effect", "credibility_effect", "social_proof_effect")
        for name in numeric_fields:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite real number")
            if name in unit_fields and not 0 <= value <= 1:
                raise ValueError(f"{name} must lie in [0, 1]")
            if name not in unit_fields and name != "adoption_intercept" and value < 0:
                raise ValueError(f"{name} must be nonnegative")

    def to_dict(self):
        return asdict(self)

