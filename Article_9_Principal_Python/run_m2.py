"""CLI for paired Article 9 M2 campaigns."""
import argparse
import json
from pathlib import Path
import pandas as pd
from article9.config import Config, integer
from article9.model import initialize, run_policies
from article9.m2_config import DiffusionConfig
from article9.diffusion import simulate
from article9.export import export_run, write_csv, write_json
from article9.m2_export import export_diffusion
from article9.selection import POLICIES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m1-config", type=Path)
    parser.add_argument("--m2-config", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--policies", nargs="+", choices=POLICIES, default=list(POLICIES))
    args = parser.parse_args()
    integer(args.repetitions, "repetitions", 1)
    integer(args.start, "start")
    base = Config(**json.loads(args.m1_config.read_text())) if args.m1_config else Config()
    config = DiffusionConfig(**json.loads(args.m2_config.read_text())) if args.m2_config else DiffusionConfig(horizon_months=base.horizon_months)
    if args.out.exists() and any(args.out.iterdir()):
        parser.error("Use a new or empty output directory")
    summaries = []
    for repetition in range(args.start, args.start + args.repetitions):
        population = initialize(base, repetition)
        selections, states = run_policies(population, base, args.policies)
        directory = args.out / f"rep_{repetition:03d}"
        export_run(directory / "population", population, base, selections, states)
        for policy in args.policies:
            result = simulate(population, selections[policy], base, config)
            export_diffusion(directory / policy, result, base, config, population_reference="../population")
            summaries.append(result.summary)
            print(f"rep={repetition} policy={policy} awareness={result.summary['awareness_count']} adoptions={result.summary['adoption_count']} WOM={result.summary['wom_messages_cumulative']}")
    write_csv(args.out / "summary_all.csv", pd.DataFrame(summaries).sort_values(["repetition", "policy"]))
    write_json(args.out / "batch.json", {"scope": "M2_diffusion_without_revenue", "repetitions": args.repetitions,
                                        "policies": args.policies, "campaigns": len(summaries)})


if __name__ == "__main__":
    main()
