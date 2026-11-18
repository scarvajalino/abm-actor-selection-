"""Canonical CSV/JSON artifacts and content hashes for reproducibility."""
import hashlib
import json
import platform
from pathlib import Path
import networkx as nx
import numpy as np
import pandas as pd
from . import __version__
from .diagnostics import attribute_correlations, network_diagnostics, policy_diagnostics, policy_overlap
from .network import edge_table
from .randomness import Streams


def write_json(path, payload):
    Path(path).write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True,
                                    allow_nan=False) + "\n", encoding="utf-8")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_hashes():
    root = Path(__file__).resolve().parents[1]
    files = [*sorted((root / "article9").glob("*.py")),
             *sorted((root / "tests").glob("*.py")),
             *sorted((root / "scripts").glob("*.py"))]
    files.extend(p for p in [root / "run_m1.py", root / "run_m2.py", root / "run_m3.py", root / "requirements-lock.txt", root / "pytest.ini"] if p.exists())
    return {str(path.relative_to(root)): sha256(path) for path in files}


def environment():
    return {"python": platform.python_version(), "numpy": np.__version__,
            "pandas": pd.__version__, "networkx": nx.__version__,
            "platform": platform.platform()}


def write_csv(path, table):
    table.to_csv(path, index=False, float_format="%.17g", lineterminator="\n", na_rep="")


def export_run(directory, population, config, results, states):
    directory = Path(directory)
    if directory.exists() and any(directory.iterdir()):
        raise FileExistsError(f"Refusing to overwrite nonempty run directory: {directory}")
    directory.mkdir(parents=True, exist_ok=True)
    repetition = population.repetition
    streams = Streams(config.master_seed, repetition)
    p_in, p_out = config.edge_probabilities()
    write_json(directory / "config.json", {"model_version": __version__, "specification_version": "0.1",
               "parameters": config.to_dict(), "repetition": repetition,
               "p_in": p_in, "p_out": p_out, "streams": streams.record()})
    nodes = population.nodes.sort_index().reset_index(drop=True)
    write_csv(directory / "nodes_ex_ante.csv", nodes)
    write_csv(directory / "edges.csv", edge_table(population.graph))
    write_csv(directory / "latent_values.csv", population.latent.sort_values("actor_id"))
    selected, audits, state_tables = [], [], []
    diagnostics = []
    for policy in sorted(results):
        result = results[policy]
        selected.append(result.selected.assign(repetition=repetition))
        audits.append(result.audit.assign(repetition=repetition))
        state_tables.append(states[policy].assign(policy=policy, repetition=repetition))
        diagnostics.append({"repetition": repetition, **policy_diagnostics(population.graph, nodes, result)})
    # Concatenating all-empty selections is supported (k=0); column headers persist.
    write_csv(directory / "selection.csv", pd.concat(selected, ignore_index=True))
    write_csv(directory / "selection_audit.csv", pd.concat(audits, ignore_index=True))
    write_csv(directory / "initial_states.csv", pd.concat(state_tables, ignore_index=True))
    write_csv(directory / "network_diagnostics.csv", pd.DataFrame([{"repetition": repetition, **network_diagnostics(population.graph)}]))
    write_csv(directory / "attribute_correlations.csv", attribute_correlations(nodes).assign(repetition=repetition))
    write_csv(directory / "policy_diagnostics.csv", pd.DataFrame(diagnostics))
    write_csv(directory / "policy_overlap.csv", policy_overlap(results).assign(repetition=repetition))
    files = {p.name: sha256(p) for p in sorted(directory.iterdir()) if p.is_file()}
    write_json(directory / "manifest.json", {"model_version": __version__, "environment": environment(),
               "code_sha256": source_hashes(), "data_sha256": files,
               "scope": "initialization_and_selection_only", "repetition": repetition})
    return directory
