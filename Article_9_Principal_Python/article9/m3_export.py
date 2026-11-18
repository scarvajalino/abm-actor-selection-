"""Economic tables and hashes of the M1/M2 inputs actually valued."""
import hashlib
import json
from pathlib import Path
import pandas as pd
from .economic_random import EconomicRandom
from .export import environment, sha256, source_hashes, write_csv, write_json
from .m3_config import M3_VERSION


def input_hashes(population, selection, diffusion):
    def digest(frame):
        data = frame.to_csv(index=False, float_format="%.17g", lineterminator="\n", na_rep="")
        return hashlib.sha256(data.encode("utf-8")).hexdigest()
    return {"nodes_ex_ante.csv": digest(population.nodes.sort_index().reset_index(drop=True)),
            "latent_values.csv": digest(population.latent.sort_values("actor_id")),
            "final_states.csv": digest(diffusion.final_states.assign(policy=diffusion.policy, repetition=diffusion.repetition)),
            "wom_events.csv": digest(diffusion.events.assign(policy=diffusion.policy, repetition=diffusion.repetition)),
            "selected_ids": hashlib.sha256(json.dumps(sorted(selection.actor_ids)).encode("utf-8")).hexdigest()}


def export_economics(directory, result, model_config, config, *, inputs, population_reference="", diffusion_reference=""):
    destination = Path(directory)
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"Output already contains files: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    write_json(destination / "config.json", {"m3_version": M3_VERSION, "parameters": config.to_dict(),
        "policy": result.policy, "repetition": result.repetition,
        "population_reference": population_reference, "diffusion_reference": diffusion_reference,
        "input_sha256": inputs, "economic_random": EconomicRandom(model_config.master_seed, result.repetition).record()})
    for name in ("transactions", "activation_costs", "repurchase_trials", "attribution_credits",
                 "actor_accounts", "seed_accounts", "periods", "prediction_ranking"):
        write_csv(destination / f"{name}.csv", getattr(result, name).assign(policy=result.policy, repetition=result.repetition))
    write_json(destination / "prediction_metrics.json", result.prediction_metrics)
    write_json(destination / "summary.json", result.summary)
    write_csv(destination / "summary.csv", pd.DataFrame([result.summary]))
    write_json(destination / "manifest.json", {"m3_version": M3_VERSION, "scope": "economics_after_M2",
        "environment": environment(), "code_sha256": source_hashes(),
        "data_sha256": {p.name: sha256(p) for p in sorted(destination.iterdir()) if p.is_file()}})
    return destination
