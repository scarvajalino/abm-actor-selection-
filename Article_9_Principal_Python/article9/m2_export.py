"""Reproducible campaign traces; economic outcomes are not fabricated in M2."""
from pathlib import Path
import pandas as pd
from .event_random import EventRandom
from .export import environment, sha256, source_hashes, write_csv, write_json
from .m2_config import M2_VERSION


def export_diffusion(directory, result, model_config, config, *, population_reference=""):
    destination = Path(directory)
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError(f"Output already contains files: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    write_json(destination / "config.json", {"m2_version": M2_VERSION, "m1_parameters": model_config.to_dict(),
        "m2_parameters": config.to_dict(), "policy": result.policy, "repetition": result.repetition,
        "population_reference": population_reference,
        "event_random": EventRandom(model_config.master_seed, result.repetition).record()})
    for name, frame in [("periods", result.periods), ("wom_events", result.events),
                         ("evaluations", result.evaluations), ("sender_months", result.sender_log),
                         ("state_history", result.state_history), ("final_states", result.final_states),
                         ("cascades", result.cascades)]:
        write_csv(destination / f"{name}.csv", frame.assign(policy=result.policy, repetition=result.repetition))
    write_json(destination / "summary.json", result.summary)
    write_csv(destination / "summary.csv", pd.DataFrame([result.summary]))
    files = {p.name: sha256(p) for p in sorted(destination.iterdir()) if p.is_file()}
    write_json(destination / "manifest.json", {"m2_version": M2_VERSION, "scope": "diffusion_without_revenue",
        "environment": environment(), "code_sha256": source_hashes(), "data_sha256": files})
    return destination

