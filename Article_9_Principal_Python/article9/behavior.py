"""Behavioral equations. Scores used for targeting never enter these rules."""
import math


def logistic(value):
    if value >= 0:
        return 1.0 / (1.0 + math.exp(-value))
    exponential = math.exp(value)
    return exponential / (1.0 + exponential)


def credible_signal(sender, config):
    return float(sender["credibility"] * ((1 - config.product_complexity) +
                 config.product_complexity * sender["expertise"] * sender["expertise_fit"]))


def adoption_probability(receiver, config, signal=0.0, unique_senders=0, source="seed"):
    if source not in ("seed", "wom"):
        raise ValueError("source must be seed or wom")
    # Need and fit are necessary gates, not probabilities learned from data.
    if receiver["need"] <= 0 or receiver["product_fit"] <= 0:
        return 0.0
    risk = config.product_complexity * (1 - receiver["expertise"] * receiver["expertise_fit"])
    score = (config.adoption_intercept + config.need_effect * receiver["need"] +
             config.fit_effect * receiver["product_fit"] + config.quality_effect * config.product_quality -
             config.risk_effect * risk)
    if source == "wom":
        proof = min(unique_senders / config.social_proof_saturation, 1.0)
        score += config.credibility_effect * signal + config.social_proof_effect * proof
    return logistic(score)


def experience_satisfaction(receiver, config):
    weight = config.satisfaction_quality_weight
    return float(weight * config.product_quality + (1 - weight) * receiver["product_fit"])


def communication_capacity(actor, config):
    return math.floor(config.base_contact_capacity * actor["activity"])


def send_probability(actor, satisfaction):
    return float(satisfaction * actor["recommendation_propensity"])
