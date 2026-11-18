"""Frozen screening design: theoretical perturbations, not empirical calibration."""
from dataclasses import replace
from article9.config import Config
from article9.m2_config import DiffusionConfig
from article9.m3_config import EconomicConfig
from article9.selection import POLICIES

PILOT_VERSION = "0.1.0"
REPETITIONS = tuple(range(20))
BOOTSTRAP_SEED = 20260927
BOOTSTRAP_DRAWS = 4000


def scenarios():
    return [
        dict(id="base", label="Base M3", group="reference", m1={}, m2={}, m3={}),
        dict(id="adoption_m3", label="Intercepto −3", group="adoption", m1={}, m2={"adoption_intercept":-3}, m3={}),
        dict(id="adoption_m4", label="Intercepto −4", group="adoption", m1={}, m2={"adoption_intercept":-4}, m3={}),
        dict(id="satisfaction_070", label="Umbral satisfacción 0,70", group="satisfaction", m1={}, m2={"satisfaction_threshold":.7}, m3={}),
        dict(id="satisfaction_080", label="Umbral satisfacción 0,80", group="satisfaction", m1={}, m2={"satisfaction_threshold":.8}, m3={}),
        dict(id="capacity_2", label="Capacidad base 2", group="capacity", m1={}, m2={"base_contact_capacity":2}, m3={}),
        dict(id="capacity_6", label="Capacidad base 6", group="capacity", m1={}, m2={"base_contact_capacity":6}, m3={}),
        dict(id="quality_050", label="Calidad 0,50", group="quality", m1={}, m2={"product_quality":.5}, m3={}),
        dict(id="quality_090", label="Calidad 0,90", group="quality", m1={}, m2={"product_quality":.9}, m3={}),
        dict(id="complexity_020", label="Complejidad 0,20", group="complexity", m1={}, m2={"product_complexity":.2}, m3={}),
        dict(id="complexity_080", label="Complejidad 0,80", group="complexity", m1={}, m2={"product_complexity":.8}, m3={}),
        dict(id="mixing_005", label="Mezcla intercomunidad 0,05", group="mixing", m1={"mixing_fraction":.05}, m2={}, m3={}),
        dict(id="mixing_040", label="Mezcla intercomunidad 0,40", group="mixing", m1={"mixing_fraction":.4}, m2={}, m3={}),
        dict(id="value_sigma_000", label="Ruido del valor 0", group="value_noise", m1={"value_noise_sigma":0}, m2={}, m3={}),
        dict(id="value_sigma_070", label="Ruido del valor 0,70", group="value_noise", m1={"value_noise_sigma":.7}, m2={}, m3={}),
        dict(id="repurchase_002", label="Recompra base 0,02", group="repurchase", m1={}, m2={}, m3={"repurchase_probability":.02}),
        dict(id="repurchase_005", label="Recompra base 0,05", group="repurchase", m1={}, m2={}, m3={"repurchase_probability":.05}),
        dict(id="service_rate_040", label="Servicio proporcional 0,40", group="service", m1={}, m2={}, m3={"service_cost_rate":.4}),
        dict(id="service_fixed_030", label="Servicio fijo adicional 30", group="service", m1={}, m2={}, m3={"service_cost_fixed":30}),
        dict(id="adoption_m3_satisfaction_070", label="Intercepto −3 y umbral 0,70", group="interaction", m1={}, m2={"adoption_intercept":-3,"satisfaction_threshold":.7}, m3={})]


def configurations(scenario):
    return replace(Config(), **scenario["m1"]), replace(DiffusionConfig(), **scenario["m2"]), replace(EconomicConfig(), **scenario["m3"])


def diffusion_key(scenario):
    # M3 has no feedback; latent monetary noise never enters M1 targeting or M2.
    import json
    return json.dumps({"m1":{k:v for k,v in scenario["m1"].items() if k != "value_noise_sigma"},"m2":scenario["m2"]},sort_keys=True)


def frozen_design():
    return {"pilot_version":PILOT_VERSION,"repetitions":list(REPETITIONS),"policies":list(POLICIES),
        "scenarios":scenarios(),"campaign_evaluations":len(scenarios())*len(POLICIES)*len(REPETITIONS),
        "unique_diffusion_profiles":len({diffusion_key(s) for s in scenarios()}),
        "baseline":{"m1":Config().to_dict(),"m2":DiffusionConfig().to_dict(),"m3":EconomicConfig().to_dict()},
        "bootstrap":{"seed":BOOTSTRAP_SEED,"draws":BOOTSTRAP_DRAWS,"unit":"paired_repetition_block", "interval":"pointwise_95_percentile"},
        "scope":"screening_pilot_not_main_experiment","design_type":"one_at_a_time_plus_one_2x2_interaction",
        "full_trace_sample":{"repetition":0,"policy":"random","scenarios":["base","adoption_m3","satisfaction_070","adoption_m3_satisfaction_070"]}}
