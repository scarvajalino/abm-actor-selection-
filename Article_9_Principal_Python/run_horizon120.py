"""Extend the four paired pilot conditions; require exact agreement through month 60."""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import replace
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import time
import zipfile
import pandas as pd
from article9.model import initialize, run_policies
from article9.diffusion import simulate
from article9.economics import account_campaign
from article9.network import edge_table
from article9.export import write_csv, write_json, sha256, environment
from pilot_design import frozen_design, configurations
from pilot_metrics import validate_campaign, validate_grid
from run_pilot import add_zip, csv_bytes, code_hashes
from horizon_metrics import CONDITIONS, horizon_metrics


def design120():
    design = frozen_design()
    design['scenarios'] = [s for name in CONDITIONS for s in design['scenarios'] if s['id'] == name]
    design['campaign_evaluations'] = 560
    design['unique_diffusion_profiles'] = 4
    design['horizon_extension_version'] = '0.1.0'
    design['horizon_months'] = 120
    design['reference_horizon_months'] = 60
    design['design_type'] = 'paired_2x2_horizon_extension'
    design['scope'] = 'exploratory_horizon_check_not_main_experiment'
    design['checks'] = ['population_bytes', 'selected_ids', 'monthly_prefix', 'actor_states_at_60', 'transactions_prefix', 'four_full_trace_prefixes']
    design['absorption_rule'] = 'zero eligible senders after month 1; not merely zero observed events'
    return design


def read_csv(source):
    return pd.read_csv(source, float_precision='round_trip')


def canonical(frame):
    return read_csv(io.BytesIO(csv_bytes(frame)))


def assert_same(actual, expected):
    # Canonical CSV missing values and float round-trips; integers/categories exact.
    pd.testing.assert_frame_equal(canonical(actual).reset_index(drop=True),
        expected.reset_index(drop=True), check_dtype=False, check_exact=True)


def verify_bundle(directory):
    directory = Path(directory)
    done = json.loads((directory / 'completion.json').read_text())
    for name, digest in done['files_sha256'].items():
        assert sha256(directory / name) == digest, (directory, name)
    with zipfile.ZipFile(directory / 'records.zip') as z:
        assert z.testzip() is None
        manifest = json.loads(z.read('manifest.json'))
        for name, digest in manifest.items():
            assert hashlib.sha256(z.read(name)).hexdigest() == digest, (directory, name)
    return done


def output_hashes(directory):
    # An explicit list prevents accidental self-reference to completion.json.
    return {name: sha256(Path(directory) / name) for name in
        ('campaigns.csv', 'monthly.csv', 'prefix_checks.csv', 'records.zip')}


def run_repetition(rep, output, reference, design):
    start = time.monotonic()
    old = Path(reference) / f'rep_{rep:03d}'
    verify_bundle(old)
    out = Path(output) / f'rep_{rep:03d}'
    out.mkdir(parents=True, exist_ok=False)
    old_monthly = read_csv(old / 'monthly.csv')
    summaries, monthly, finals, states60, purchases, seeds, checks = [], [], [], [], [], [], []
    hashes = {}
    m1, _, _ = configurations(design['scenarios'][0])
    population = initialize(m1, rep)
    selections, _ = run_policies(population, m1)
    with zipfile.ZipFile(old / 'records.zip') as prior, zipfile.ZipFile(out / 'records.zip', 'x') as bundle:
        old_final = read_csv(prior.open('final_states.csv'))
        old_tx = read_csv(prior.open('transactions.csv'))
        old_prov = read_csv(prior.open('provenance.csv')).set_index(['scenario', 'policy'])
        for name, frame in [('nodes_ex_ante', population.nodes.reset_index(drop=True)), ('latent_values', population.latent), ('edges', edge_table(population.graph))]:
            payload = csv_bytes(frame)
            assert payload == prior.read(f'populations/p00/{name}.csv')
            add_zip(bundle, f'population/{name}.csv', payload, hashes)
        selected_frames = []
        for scenario in design['scenarios']:
            c1, dc60, ec = configurations(scenario)
            assert c1 == m1 and ec.repurchase_probability == 0
            dc = replace(dc60, horizon_months=120)
            for policy in design['policies']:
                selection = selections[policy]
                selected_hash = hashlib.sha256(json.dumps(sorted(selection.actor_ids)).encode()).hexdigest()
                assert selected_hash == old_prov.loc[(scenario['id'], policy), 'selected_ids_sha256']
                d = simulate(population, selection, m1, dc)
                e = account_campaign(population, selection, d, m1, ec)
                validate_campaign(d, e, m1.n_agents, m1.k, 120)
                periods = d.periods.merge(e.periods, on='month', validate='one_to_one')
                old_periods = old_monthly.loc[(old_monthly.scenario == scenario['id']) & (old_monthly.policy == policy), periods.columns].sort_values('month')
                assert_same(periods.loc[periods.month <= 60], old_periods)
                snapshot = d.state_history.loc[d.state_history.month == 60].reset_index(drop=True)
                previous = old_final.loc[old_final.diffusion_id == f'{scenario["id"]}__{policy}', snapshot.columns]
                assert_same(snapshot, previous)
                # Byte-level equality to the actual original per-campaign snapshot.
                assert hashlib.sha256(csv_bytes(snapshot)).hexdigest() == old_prov.loc[(scenario['id'], policy), 'final_states_sha256']
                tx60 = e.transactions.loc[e.transactions.month <= 60]
                expected_tx = old_tx.loc[(old_tx.scenario == scenario['id']) & (old_tx.policy == policy), tx60.columns]
                assert_same(tx60, expected_tx)
                meta = {'scenario': scenario['id'], 'policy': policy, 'repetition': rep}
                full_checked = False
                if rep == 0 and policy == 'random':
                    full_checked = True
                    for name, frame in [('state_history', d.state_history), ('wom_events', d.events), ('evaluations', d.evaluations), ('sender_months', d.sender_log)]:
                        assert_same(frame.loc[frame.month <= 60], read_csv(prior.open(f'full_trace_sample/{scenario["id"]}/{name}.csv')))
                        add_zip(bundle, f'full_trace_sample/{scenario["id"]}/{name}.csv', csv_bytes(frame), hashes)
                    for name, frame in [('attribution_credits', e.attribution_credits), ('prediction_ranking', e.prediction_ranking), ('actor_accounts', e.actor_accounts)]:
                        add_zip(bundle, f'full_trace_sample/{scenario["id"]}/{name}.csv', csv_bytes(frame), hashes)
                checks.append({**meta, 'population_bytes': True, 'selected_ids': True, 'monthly_prefix': True,
                    'state60_bytes': True, 'transactions_prefix': True, 'full_trace_prefix_checked': full_checked})
                summaries.append({'scenario': scenario['id'], 'label': scenario['label'], **horizon_metrics(d, e)})
                monthly.append(periods.assign(**meta))
                finals.append(d.final_states.assign(**meta))
                states60.append(snapshot.assign(**meta))
                purchases.append(e.transactions.assign(**meta))
                seeds.append(e.seed_accounts.assign(**meta))
        for policy in design['policies']:
            selected_frames.append(selections[policy].selected.assign(repetition=rep))
        for name, frames in [('final_states', finals), ('states_at_60', states60), ('transactions', purchases), ('seed_accounts', seeds), ('selections', selected_frames)]:
            add_zip(bundle, f'{name}.csv', csv_bytes(pd.concat(frames, ignore_index=True)), hashes)
        add_zip(bundle, 'manifest.json', json.dumps(hashes, sort_keys=True, indent=2).encode(), {})
    summary = pd.DataFrame(summaries).sort_values(['scenario', 'policy'])
    validate_grid(summary, [s['id'] for s in design['scenarios']], design['policies'], [rep])
    write_csv(out / 'campaigns.csv', summary)
    write_csv(out / 'monthly.csv', pd.concat(monthly, ignore_index=True).sort_values(['scenario', 'policy', 'month']))
    write_csv(out / 'prefix_checks.csv', pd.DataFrame(checks))
    record = {'repetition': rep, 'campaigns': len(summary), 'validation': 'passed',
        'seconds': time.monotonic() - start,
        'reference_completion_sha256': sha256(old / 'completion.json'),
        'files_sha256': output_hashes(out)}
    write_json(out / 'completion.json', record)
    verify_bundle(out)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    if args.workers < 1:
        parser.error('workers must be positive')
    out = args.out.resolve()
    if out.exists() and any(out.iterdir()):
        parser.error('Use a new output directory')
    out.mkdir(parents=True, exist_ok=True)
    reference = args.reference.resolve()
    design = design120()
    write_json(out / 'design.json', design)
    write_json(out / 'source_manifest.json', {'code_sha256': code_hashes(), 'environment': environment(),
        'started_at': datetime.now(timezone.utc).isoformat(), 'design_sha256': sha256(out / 'design.json'),
        'reference_design_sha256': sha256(reference / 'design.json'),
        'reference_source_manifest_sha256': sha256(reference / 'source_manifest.json')})
    records = []
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(run_repetition, r, str(out), str(reference), design) for r in design['repetitions']]
        for future in as_completed(futures):
            result = future.result()
            records.append(result)
            print(f"Completed rep {result['repetition']:02d}, {len(records)}/20; 28 campaigns, all prefix checks passed", flush=True)
    for r in design['repetitions']:
        verify_bundle(out / f'rep_{r:03d}')
    summary = pd.concat([read_csv(out / f'rep_{r:03d}/campaigns.csv') for r in design['repetitions']], ignore_index=True)
    validate_grid(summary, CONDITIONS, design['policies'], design['repetitions'])
    write_csv(out / 'campaigns_all.csv', summary.sort_values(['scenario', 'policy', 'repetition']))
    write_json(out / 'completion.json', {'status': 'passed', 'campaigns': len(summary),
        'repetitions': sorted(records, key=lambda x: x['repetition']), 'summary_sha256': sha256(out / 'campaigns_all.csv'),
        'finished_at': datetime.now(timezone.utc).isoformat()})


if __name__ == '__main__':
    main()
