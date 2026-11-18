"""Run a frozen paired screening design without changing any M1/M2/M3 equation."""
import argparse
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import zipfile
import pandas as pd
from article9.config import Config
from article9.model import initialize, run_policies
from article9.diffusion import simulate
from article9.economics import account_campaign
from article9.diagnostics import network_diagnostics
from article9.network import edge_table
from article9.export import write_json, write_csv, sha256, environment
from article9.selection import POLICIES
from pilot_design import scenarios, configurations, diffusion_key, frozen_design
from pilot_metrics import campaign_metrics, validate_campaign, validate_grid


def code_hashes():
    root=Path(__file__).resolve().parent
    return {str(p.relative_to(root)):sha256(p) for p in sorted(root.rglob('*.py')) if '__pycache__' not in p.parts}


def csv_bytes(frame):
    return frame.to_csv(index=False,float_format='%.17g',lineterminator='\n',na_rep='').encode('utf-8')


def add_zip(z,name,payload,manifest):
    info=zipfile.ZipInfo(name,(2026,9,27,7,0,44));info.compress_type=zipfile.ZIP_DEFLATED
    info.external_attr=0o644<<16
    z.writestr(info,payload,compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
    manifest[name]=hashlib.sha256(payload).hexdigest()


def run_repetition(rep,output,design):
    started=time.monotonic();out=Path(output)/f'rep_{rep:03d}';out.mkdir(parents=True,exist_ok=False)
    populations={};targets={};network_rows=[];selected_rows=[]
    groups=defaultdict(list)
    for s in design['scenarios']:groups[diffusion_key(s)].append(s)
    summaries=[];monthly=[];finals=[];purchases=[];seeds=[];provenance=[]
    data_hashes={};diffusion_count=0;sample_count=0
    with zipfile.ZipFile(out/'records.zip','x') as bundle:
        for related in groups.values():
            anchor=related[0];m1,dc,_=configurations(anchor)
            for scenario in related:
                c1,_,_=configurations(scenario);key=json.dumps(c1.to_dict(),sort_keys=True)
                if key not in populations:
                    pop=initialize(c1,rep);selections,_=run_policies(pop,c1)
                    pid=f'p{len(populations):02d}'
                    populations[key]=(pid,pop);targets[key]=selections
                    for name,frame in [('nodes_ex_ante',pop.nodes.reset_index(drop=True)),('latent_values',pop.latent),('edges',edge_table(pop.graph))]:
                        add_zip(bundle,f'populations/{pid}/{name}.csv',csv_bytes(frame),data_hashes)
                    network_rows.append({'population_id':pid,**network_diagnostics(pop.graph)})
                    for policy in design['policies']:
                        selected_rows.append(selections[policy].selected.assign(population_id=pid,repetition=rep))
            anchor_key=json.dumps(m1.to_dict(),sort_keys=True);anchor_pid,pop=populations[anchor_key]
            for policy in design['policies']:
                selected=targets[anchor_key][policy]
                d=simulate(pop,selected,m1,dc);diffusion_count+=1
                d_id=f'{anchor["id"]}__{policy}'
                final_hash=hashlib.sha256(csv_bytes(d.final_states)).hexdigest()
                finals.append(d.final_states.assign(diffusion_id=d_id,policy=policy,repetition=rep))
                for s in related:
                    c1,_,ec=configurations(s);key=json.dumps(c1.to_dict(),sort_keys=True)
                    pid,economic_population=populations[key];selection=targets[key][policy]
                    # The only population difference allowed within a group is hidden value noise.
                    assert selection.actor_ids==selected.actor_ids
                    assert economic_population.nodes.equals(pop.nodes)
                    assert sorted(economic_population.graph.edges())==sorted(pop.graph.edges())
                    result=account_campaign(economic_population,selection,d,c1,ec)
                    validate_campaign(d,result,c1.n_agents,c1.k,dc.horizon_months)
                    summaries.append({'scenario':s['id'],'group':s['group'],'label':s['label'],**campaign_metrics(d,result)})
                    period=d.periods.merge(result.periods,on='month',validate='one_to_one')
                    monthly.append(period.assign(scenario=s['id'],policy=policy,repetition=rep))
                    purchases.append(result.transactions.assign(scenario=s['id'],policy=policy,repetition=rep))
                    seeds.append(result.seed_accounts.assign(scenario=s['id'],policy=policy,repetition=rep))
                    provenance.append({'scenario':s['id'],'policy':policy,'repetition':rep,'population_id':pid,
                        'diffusion_id':d_id,'final_states_sha256':final_hash,
                        'selected_ids_sha256':hashlib.sha256(json.dumps(sorted(selection.actor_ids)).encode()).hexdigest()})
                    sample=design['full_trace_sample']
                    if rep==sample['repetition'] and policy==sample['policy'] and s['id'] in sample['scenarios']:
                        sample_count+=1
                        for name,frame in [('state_history',d.state_history),('wom_events',d.events),('evaluations',d.evaluations),
                            ('sender_months',d.sender_log),('repurchase_trials',result.repurchase_trials),('attribution_credits',result.attribution_credits),
                            ('prediction_ranking',result.prediction_ranking),('actor_accounts',result.actor_accounts)]:
                            add_zip(bundle,f'full_trace_sample/{s["id"]}/{name}.csv',csv_bytes(frame),data_hashes)
        frames={'final_states':pd.concat(finals,ignore_index=True),'transactions':pd.concat(purchases,ignore_index=True),
            'seed_accounts':pd.concat(seeds,ignore_index=True),'selections':pd.concat(selected_rows,ignore_index=True),
            'network_diagnostics':pd.DataFrame(network_rows),'provenance':pd.DataFrame(provenance)}
        for name,frame in frames.items():add_zip(bundle,f'{name}.csv',csv_bytes(frame),data_hashes)
        add_zip(bundle,'manifest.json',json.dumps(data_hashes,sort_keys=True,indent=2).encode(),{})
    summary=pd.DataFrame(summaries).sort_values(['scenario','policy'])
    periods=pd.concat(monthly,ignore_index=True).sort_values(['scenario','policy','month'])
    validate_grid(summary,[s['id'] for s in design['scenarios']],design['policies'],[rep])
    write_csv(out/'campaigns.csv',summary);write_csv(out/'monthly.csv',periods)
    with zipfile.ZipFile(out/'records.zip') as z:
        assert z.testzip() is None
        for name,digest in data_hashes.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
    record={'repetition':rep,'campaigns':len(summary),'unique_diffusions':diffusion_count,'full_trace_samples':sample_count,
        'seconds':time.monotonic()-started,'validation':'passed','files_sha256':{p.name:sha256(p) for p in out.iterdir() if p.is_file()}}
    write_json(out/'completion.json',record)
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--workers',type=int,default=4)
    parser.add_argument('--design-only',action='store_true')
    args=parser.parse_args()
    if args.workers<1:parser.error('workers must be positive')
    out=args.out.resolve()
    if out.exists() and any(out.iterdir()):parser.error('Use a new or empty output folder')
    out.mkdir(parents=True,exist_ok=True)
    design=frozen_design()
    write_json(out/'design.json',design)
    write_json(out/'source_manifest.json',{'code_sha256':code_hashes(),'environment':environment(),
        'original_m3_zip_sha256':'66c941ce378c49582d69f4f8ab61bad875e5a69559e054ba87ffc3a562e4dd0e',
        'design_sha256':sha256(out/'design.json'),'started_at':datetime.now(timezone.utc).isoformat()})
    if args.design_only:return
    records=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        tasks=[pool.submit(run_repetition,r,str(out),design) for r in design['repetitions']]
        for task in as_completed(tasks):
            record=task.result();records.append(record)
            print(f"Completed repetition {record['repetition']:02d}: {record['campaigns']} economic evaluations, {record['unique_diffusions']} diffusions, {len(records)}/{len(tasks)} blocks",flush=True)
    summary=pd.concat([pd.read_csv(out/f'rep_{r:03d}/campaigns.csv',float_precision='round_trip') for r in design['repetitions']],ignore_index=True)
    validate_grid(summary,[s['id'] for s in design['scenarios']],design['policies'],design['repetitions'])
    write_csv(out/'campaigns_all.csv',summary.sort_values(['scenario','policy','repetition']))
    records.sort(key=lambda x:x['repetition'])
    write_json(out/'completion.json',{'status':'passed','campaigns':len(summary),
        'unique_diffusions':sum(r['unique_diffusions'] for r in records),'repetitions':records,
        'finished_at':datetime.now(timezone.utc).isoformat(),'design_sha256':sha256(out/'design.json'),
        'summary_sha256':sha256(out/'campaigns_all.csv')})


if __name__=='__main__':main()
