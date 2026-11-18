"""Compare the new runner's eight conditions against the archived pilot at month 60."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pandas as pd
from main_design import main_design
from run_main import run_repetition,atomic_bytes,json_bytes
from run_horizon120 import assert_same


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--reference',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    design=main_design();design['policies']=['random']
    run_repetition(0,args.out,design)
    old=pd.read_csv(args.reference/'rep_000/monthly.csv',float_precision='round_trip')
    current=pd.read_csv(args.out/'rep_000/monthly.csv',float_precision='round_trip')
    for scenario in design['scenarios']:
        expected=old.loc[(old.scenario==scenario['id'])&(old.policy=='random')].reset_index(drop=True)
        actual=current.loc[(current.scenario==scenario['id'])&(current.month<=60)].reset_index(drop=True)
        assert_same(actual[expected.columns],expected)
    result={'status':'passed','conditions':8,'policy':'random','repetition':0,
        'comparison':'all monthly M2/M3 fields 0..60 exactly match prior pilot',
        'excluded_from_main_experiment':True}
    atomic_bytes(args.out/'verification.json',json_bytes(result))
    print(json.dumps(result))


if __name__=='__main__':main()
