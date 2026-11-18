"""Paired M1/M2/M3 runs. Each policy uses the same population and random fields."""
import argparse
import json
from pathlib import Path
import pandas as pd
from article9.config import Config, integer
from article9.model import initialize, run_policies
from article9.diffusion import simulate
from article9.m2_config import DiffusionConfig
from article9.m2_export import export_diffusion
from article9.economics import account_campaign
from article9.m3_config import EconomicConfig
from article9.m3_export import export_economics, input_hashes
from article9.export import export_run, write_csv, write_json
from article9.selection import POLICIES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m1-config", type=Path)
    parser.add_argument("--m2-config", type=Path)
    parser.add_argument("--m3-config", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--policies", nargs="+", choices=POLICIES, default=list(POLICIES))
    args = parser.parse_args()
    integer(args.repetitions, "repetitions", 1)
    integer(args.start, "start")
    if len(set(args.policies)) != len(args.policies):
        parser.error("Policies must be unique")
    def read(path, cls, **default):
        return cls(**json.loads(path.read_text())) if path else cls(**default)
    base = read(args.m1_config, Config)
    diffusion_config = read(args.m2_config, DiffusionConfig, horizon_months=base.horizon_months)
    economics_config = read(args.m3_config, EconomicConfig)
    if args.out.exists() and any(args.out.iterdir()):
        parser.error("Use a new or empty output directory")
    summaries = []
    for repetition in range(args.start, args.start + args.repetitions):
        population = initialize(base, repetition)
        selections, states = run_policies(population, base, args.policies)
        directory = args.out / f"rep_{repetition:03d}"
        export_run(directory / "population", population, base, selections, states)
        for policy in args.policies:
            selection = selections[policy]
            diffusion = simulate(population, selection, base, diffusion_config)
            export_diffusion(directory / policy / "m2", diffusion, base, diffusion_config, population_reference="../../population")
            result = account_campaign(population, selection, diffusion, base, economics_config)
            export_economics(directory / policy / "m3", result, base, economics_config,
                inputs=input_hashes(population, selection, diffusion), population_reference="../../population", diffusion_reference="../m2")
            summaries.append(result.summary)
            print(f"rep={repetition} policy={policy} adoptions={result.summary['adoption_count']} revenue={result.summary['revenue']:.3f} profit={result.summary['profit']:.3f}")
    write_csv(args.out / "summary_all.csv", pd.DataFrame(summaries).sort_values(["repetition", "policy"]))
    write_json(args.out / "batch.json", {"scope": "M3_economic_campaigns", "repetitions": args.repetitions,
        "policies": args.policies, "campaigns": len(summaries), "monetary_unit": "abstract_units"})


if __name__ == "__main__":
    main()
