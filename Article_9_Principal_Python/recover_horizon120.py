"""Repair only explicitly named invalid archives, preserving the failed attempts."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import pandas as pd
from article9.export import sha256, write_csv, write_json
from horizon_metrics import CONDITIONS
from pilot_metrics import validate_grid
from run_horizon120 import verify_bundle, run_repetition, read_csv


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input',type=Path,required=True)
    parser.add_argument('--reference',type=Path,required=True)
    parser.add_argument('--quarantine',type=Path,required=True)
    parser.add_argument('--recover',type=int,nargs='+',required=True)
    args=parser.parse_args()
    root=args.input.resolve();reference=args.reference.resolve();quarantine=args.quarantine.resolve()
    design=json.loads((root/'design.json').read_text())
    source=json.loads((root/'source_manifest.json').read_text())
    code=Path(__file__).resolve().parent
    for name,digest in source['code_sha256'].items():
        assert sha256(code/name)==digest, f'Changed simulation source: {name}'
    quarantine.mkdir(parents=True,exist_ok=False)
    recovery=[]
    for rep in args.recover:
        assert rep in design['repetitions']
        old=root/f'rep_{rep:03d}'
        try:verify_bundle(old)
        except Exception as exc:failure=f'{type(exc).__name__}: {exc}'
        else:raise ValueError('Refusing to replace a valid repetition')
        backup=quarantine/old.name
        old.rename(backup)
        run_repetition(rep,str(root),str(reference),design)
        comparisons={name:sha256(old/name)==sha256(backup/name) for name in ['campaigns.csv','monthly.csv','prefix_checks.csv']}
        assert all(comparisons.values()),comparisons
        recovery.append({'repetition':rep,'failure':failure,'same_code_and_seeds':True,
            'recreated_serially':True,'byte_equal_to_first_attempt':comparisons,
            'failed_archive_sha256':sha256(backup/'records.zip'),
            'repaired_archive_sha256':sha256(old/'records.zip')})
        print(f'Repaired repetition {rep}; all summary, monthly and prefix CSV bytes unchanged',flush=True)
    records=[verify_bundle(root/f'rep_{r:03d}') for r in design['repetitions']]
    summary=pd.concat([read_csv(root/f'rep_{r:03d}/campaigns.csv') for r in design['repetitions']],ignore_index=True)
    validate_grid(summary,CONDITIONS,design['policies'],design['repetitions'])
    write_csv(root/'campaigns_all.csv',summary.sort_values(['scenario','policy','repetition']))
    write_json(root/'recovery_log.json',{'recovery':recovery,'recovery_script_sha256':sha256(Path(__file__)),
        'cause':'Archive truncation observed; underlying cause not established; no parameter changes'})
    write_json(root/'completion.json',{'status':'passed','campaigns':len(summary),'repetitions':records,
        'summary_sha256':sha256(root/'campaigns_all.csv'),'finished_at':datetime.now(timezone.utc).isoformat()})
    print('All 20 repetitions verified; 560 campaigns complete',flush=True)


if __name__=='__main__':main()
