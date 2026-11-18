"""CLI: generate paired M1 selections. Does not run diffusion campaigns."""
import argparse
import json
from pathlib import Path
from article9.config import Config, integer
from article9.model import initialize, run_policies
from article9.export import export_run, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--start", type=int, default=0)
    args = parser.parse_args()
    integer(args.repetitions, "repetitions", 1)
    integer(args.start, "start")
    config = Config(**json.loads(args.config.read_text())) if args.config else Config()
    ids = range(args.start, args.start + args.repetitions)
    # Check all destination directories before writing the first run.
    for repetition in ids:
        destination = args.out / f"rep_{repetition:03d}"
        if destination.exists() and any(destination.iterdir()):
            parser.error(f"Output exists: {destination}. Use a new output directory.")
    for repetition in ids:
        population = initialize(config, repetition)
        results, states = run_policies(population, config)
        export_run(args.out / f"rep_{repetition:03d}", population, config, results, states)
        print(f"repetition={repetition} people={config.n_agents} policies={len(results)} selected_per_policy={config.k}")
    write_json(args.out / "batch.json", {"scope": "M1_initialization_and_selection", "repetitions": list(ids),
               "policies_per_repetition": 7, "diffusion_campaigns": 0})


if __name__ == "__main__":
    main()

