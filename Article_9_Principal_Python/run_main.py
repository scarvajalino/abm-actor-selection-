"""Run 5,600 approved campaigns, writing complete verified archives atomically."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import time
import zipfile
import pandas as pd
from article9.model import initialize,run_policies
from article9.diffusion import simulate
from article9.economics import account_campaign
from article9.network import edge_table
from article9.diagnostics import network_diagnostics,policy_diagnostics,policy_overlap,attribute_correlations
from article9.export import sha256,environment
from pilot_metrics import validate_campaign,validate_grid
from run_pilot import csv_bytes,add_zip,code_hashes
from run_horizon120 import assert_same,canonical
from main_design import main_design,main_configs,CONDITIONS
from main_metrics import slice_diffusion,main_metrics


FILES=('campaigns.csv','monthly.csv','records.zip')


def atomic_bytes(path,payload):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as stream:
            stream.write(payload);stream.flush();os.fsync(stream.fileno())
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def json_bytes(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode()


def verify_zip(source):
    with zipfile.ZipFile(source) as z:
        assert z.testzip() is None
        manifest=json.loads(z.read('manifest.json'))
        assert set(z.namelist())==set(manifest)|{'manifest.json'}
        for name,digest in manifest.items():
            assert hashlib.sha256(z.read(name)).hexdigest()==digest,name


def verify_repetition(folder):
    folder=Path(folder)
    record=json.loads((folder/'completion.json').read_text())
    assert set(record['files_sha256'])==set(FILES)
    for name,digest in record['files_sha256'].items():assert sha256(folder/name)==digest,(folder,name)
    verify_zip(folder/'records.zip')
    return record


def run_repetition(rep,output,design):
    started=time.monotonic();out=Path(output)/f'rep_{rep:03d}'
    out.mkdir(parents=True,exist_ok=False)
    memory=io.BytesIO();hashes={};populations={};summaries=[];monthly=[]
    nodes=[];networks=[];selections_all=[];policy_checks=[];overlaps=[];correlations=[];provenance=[];communities=[]
    with zipfile.ZipFile(memory,'w') as bundle:
        for scenario in design['scenarios']:
            m1,dc,ec=main_configs(scenario)
            key=json.dumps(m1.to_dict(),sort_keys=True)
            if key not in populations:
                pid=f'p{len(populations):02d}'
                population=initialize(m1,rep);selections,_=run_policies(population,m1)
                populations[key]=(pid,population,selections)
                for name,frame in [('nodes_ex_ante',population.nodes.reset_index(drop=True)),('latent_values',population.latent),('edges',edge_table(population.graph))]:
                    add_zip(bundle,f'populations/{pid}/{name}.csv',csv_bytes(frame),hashes)
                networks.append({'population_id':pid,'repetition':rep,'mixing_fraction':m1.mixing_fraction,**network_diagnostics(population.graph)})
                overlaps.append(policy_overlap(selections).assign(population_id=pid,repetition=rep))
                correlations.append(attribute_correlations(population.nodes).assign(population_id=pid,repetition=rep))
                for policy in design['policies']:
                    selections_all.append(selections[policy].selected.assign(population_id=pid,repetition=rep))
                    policy_checks.append({'population_id':pid,'repetition':rep,**policy_diagnostics(population.graph,population.nodes,selections[policy])})
            pid,population,selections=populations[key]
            for policy in design['policies']:
                selection=selections[policy]
                d=simulate(population,selection,m1,dc)
                e=account_campaign(population,selection,d,m1,ec)
                d60=slice_diffusion(d,60)
                e60=account_campaign(population,selection,d60,m1,ec)
                validate_campaign(d,e,m1.n_agents,m1.k,120)
                validate_campaign(d60,e60,m1.n_agents,m1.k,60)
                assert_same(e.periods.loc[e.periods.month<=60],canonical(e60.periods))
                assert_same(e.transactions.loc[e.transactions.month<=60],canonical(e60.transactions))
                meta={'scenario':scenario['id'],'policy':policy,'repetition':rep}
                summary={**meta,'label':scenario['label'],**main_metrics(d,e,d60,e60)}
                summaries.append(summary)
                monthly.append(d.periods.merge(e.periods,on='month',validate='one_to_one').assign(**meta))
                prefix=f'campaigns/{scenario["id"]}/{policy}'
                for name,frame in [('states_60',d60.final_states),('states_120',d.final_states),
                    ('transactions',e.transactions),('seed_accounts_60',e60.seed_accounts),('seed_accounts_120',e.seed_accounts),
                    ('prediction_ranking_60',e60.prediction_ranking),('prediction_ranking_120',e.prediction_ranking),
                    ('cascades_60',d60.cascades),('cascades_120',d.cascades)]:
                    add_zip(bundle,f'{prefix}/{name}.csv',csv_bytes(frame),hashes)
                for h,snapshot in [(60,d60.final_states),(120,d.final_states)]:
                    for community,group in snapshot.groupby('community_id'):
                        adopted=group.loc[group.adopted]
                        communities.append({**meta,'horizon':h,'community_id':int(community),
                            'aware':int(group.aware.sum()),'adopters':len(adopted),
                            'first_adoption_month':float(adopted.adoption_month.min()) if len(adopted) else None})
                sample=design['full_trace_sample']
                if rep==sample['repetition'] and policy==sample['policy']:
                    for name,frame in [('state_history',d.state_history),('wom_events',d.events),('evaluations',d.evaluations),
                        ('sender_months',d.sender_log),('attribution_credits',e.attribution_credits),('actor_accounts_60',e60.actor_accounts),('actor_accounts_120',e.actor_accounts)]:
                        add_zip(bundle,f'full_trace_sample/{scenario["id"]}/{name}.csv',csv_bytes(frame),hashes)
                provenance.append({**meta,'population_id':pid,'horizon':120,'primary_horizon':60,
                    'selected_ids_sha256':hashlib.sha256(json.dumps(sorted(selection.actor_ids)).encode()).hexdigest(),
                    'economics_60_prefix_exact':True,'validation_60':True,'validation_120':True})
        for name,frame in [('network_diagnostics',pd.DataFrame(networks)),('selections',pd.concat(selections_all,ignore_index=True)),
            ('policy_diagnostics',pd.DataFrame(policy_checks)),('policy_overlap',pd.concat(overlaps,ignore_index=True)),
            ('attribute_correlations',pd.concat(correlations,ignore_index=True)),('communities',pd.DataFrame(communities)),('provenance',pd.DataFrame(provenance))]:
            add_zip(bundle,f'{name}.csv',csv_bytes(frame),hashes)
        add_zip(bundle,'manifest.json',json_bytes(hashes),{})
    archive=memory.getvalue();verify_zip(io.BytesIO(archive))
    summary=pd.DataFrame(summaries).sort_values(['scenario','policy'])
    periods=pd.concat(monthly,ignore_index=True).sort_values(['scenario','policy','month'])
    validate_grid(summary,[s['id'] for s in design['scenarios']],design['policies'],[rep])
    payloads={'records.zip':archive,'campaigns.csv':csv_bytes(summary),'monthly.csv':csv_bytes(periods)}
    for name,payload in payloads.items():atomic_bytes(out/name,payload)
    for name,payload in payloads.items():assert sha256(out/name)==hashlib.sha256(payload).hexdigest()
    record={'repetition':rep,'campaigns':len(summary),'monthly_rows':len(periods),'validation':'passed',
        'seconds':time.monotonic()-started,'files_sha256':{name:hashlib.sha256(payloads[name]).hexdigest() for name in FILES},
        'full_trace_samples':len(design['scenarios']) if rep==design['full_trace_sample']['repetition'] else 0}
    atomic_bytes(out/'completion.json',json_bytes(record))
    verify_repetition(out)
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=8)
    parser.add_argument('--resume',action='store_true')
    parser.add_argument('--design-only',action='store_true')
    args=parser.parse_args()
    if args.workers<1:parser.error('workers must be positive')
    out=args.out.resolve();design=main_design()
    if args.resume:
        assert json.loads((out/'design.json').read_text())==design
        previous=json.loads((out/'source_manifest.json').read_text())
        assert previous['code_sha256']==code_hashes(),'Source changed; cannot resume silently'
    else:
        if out.exists() and any(out.iterdir()):parser.error('Use a new output folder or --resume')
        out.mkdir(parents=True,exist_ok=True)
        atomic_bytes(out/'design.json',json_bytes(design))
        atomic_bytes(out/'source_manifest.json',json_bytes({'code_sha256':code_hashes(),'environment':environment(),
            'design_sha256':sha256(out/'design.json'),'started_at':datetime.now(timezone.utc).isoformat()}))
    if args.design_only:return
    pending=[];records=[]
    for rep in design['repetitions']:
        folder=out/f'rep_{rep:03d}'
        if folder.exists():records.append(verify_repetition(folder))
        else:pending.append(rep)
    errors=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures={pool.submit(run_repetition,r,str(out),design):r for r in pending}
        for task in as_completed(futures):
            rep=futures[task]
            try:
                record=task.result();records.append(record)
                print(f"Completed {len(records)}/100 blocks; rep {rep}; {record['campaigns']} campaigns; {record['seconds']:.1f}s",flush=True)
            except Exception as exc:
                errors.append({'repetition':rep,'error':repr(exc)})
                print(f'FAILED rep {rep}: {exc!r}',flush=True)
    if errors:
        atomic_bytes(out/'execution_errors.json',json_bytes(errors))
        raise RuntimeError(f'{len(errors)} failed blocks; preserve and repair explicitly')
    records=[verify_repetition(out/f'rep_{r:03d}') for r in design['repetitions']]
    summary=pd.concat([pd.read_csv(out/f'rep_{r:03d}/campaigns.csv',float_precision='round_trip') for r in design['repetitions']],ignore_index=True)
    validate_grid(summary,CONDITIONS,design['policies'],design['repetitions'])
    atomic_bytes(out/'campaigns_all.csv',csv_bytes(summary.sort_values(['scenario','policy','repetition'])))
    atomic_bytes(out/'completion.json',json_bytes({'status':'passed','campaigns':len(summary),'repetitions':records,
        'summary_sha256':sha256(out/'campaigns_all.csv'),'finished_at':datetime.now(timezone.utc).isoformat()}))
    print('COMPLETE: 5600 campaigns; 100 blocks and every archive verified',flush=True)


if __name__=='__main__':main()
