"""Main-design gates, prefix accounting, paired intervals and durable output checks."""
from dataclasses import replace
import io
import json
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd
import pytest
from article9.model import initialize,run_policies
from article9.diffusion import simulate
from article9.economics import account_campaign
from main_design import main_design,main_configs,CONDITIONS,PRIMARY
from main_metrics import slice_diffusion
from main_statistics import simultaneous_primary
from run_main import atomic_bytes,run_repetition,verify_repetition
from run_horizon120 import assert_same,canonical


def test_N01_matrix_and_new_seeds():
    d=main_design()
    assert tuple(s['id'] for s in d['scenarios'])==CONDITIONS
    assert len(d['repetitions'])*len(d['policies'])*len(d['scenarios'])==5600
    assert set(d['repetitions']).isdisjoint(d['excluded_pilot_repetitions'])
    assert tuple(d['primary_metrics'])==PRIMARY
    for s in d['scenarios']:
        c,diff,econ=main_configs(s)
        assert c.n_agents==600 and c.k==20 and c.mean_degree==12
        assert c.horizon_months==diff.horizon_months==120
        assert econ.repurchase_probability==0 and econ.service_cost_rate==.2


@pytest.mark.parametrize('scenario',main_design()['scenarios'],ids=CONDITIONS)
def test_N02_prefix_reconstructs_direct_run(scenario):
    c,d,e=main_configs(scenario)
    c=replace(c,n_agents=60,n_communities=6,k=6,mean_degree=6)
    pop=initialize(c,24);targets,_=run_policies(pop,c)
    long=simulate(pop,targets['random'],c,replace(d,horizon_months=12))
    direct=simulate(pop,targets['random'],c,replace(d,horizon_months=5))
    prefix=slice_diffusion(long,5)
    for name in ['periods','final_states','events','evaluations','sender_log','cascades']:
        assert_same(getattr(prefix,name),canonical(getattr(direct,name)))
    for key,value in direct.summary.items():assert prefix.summary[key]==value
    expected=account_campaign(pop,targets['random'],direct,c,e)
    actual=account_campaign(pop,targets['random'],prefix,c,e)
    for name in ['transactions','seed_accounts','prediction_ranking']:
        assert_same(getattr(actual,name),canonical(getattr(expected,name)))


def test_N03_simultaneous_intervals_preserve_pairing():
    values=np.array([[1,2],[2,4],[3,6],[4,8]],dtype=float)
    idx=np.random.default_rng(23).integers(0,4,(2000,4))
    r=simultaneous_primary(values,idx)
    assert np.allclose(r['mean'],[2.5,5])
    assert r['low'][1]==pytest.approx(2*r['low'][0])
    assert r['high'][1]==pytest.approx(2*r['high'][0])
    assert np.allclose(r['mcse'],values.std(axis=0,ddof=1)/2)
    constant=simultaneous_primary(np.ones((4,2)),idx)
    assert np.all(constant['low']==1) and np.all(constant['zero_sample_variance'])
    with pytest.raises(ValueError):simultaneous_primary([[1,np.nan],[2,3]],idx)


def test_N04_atomic_replacement_does_not_append(tmp_path):
    p=tmp_path/'record.bin'
    atomic_bytes(p,b'old payload');atomic_bytes(p,b'new')
    assert p.read_bytes()==b'new'
    assert list(tmp_path.iterdir())==[p]


def test_N05_complete_worker_and_corruption_detection(tmp_path):
    d=main_design();d['scenarios']=d['scenarios'][:1];d['policies']=['random']
    result=run_repetition(0,tmp_path,d)
    assert result['campaigns']==1 and result['monthly_rows']==121
    assert result['full_trace_samples']==0
    folder=tmp_path/'rep_000'
    data=pd.read_csv(folder/'campaigns.csv')
    assert data.revenue_120.iloc[0]>=data.revenue_60.iloc[0]
    with zipfile.ZipFile(folder/'records.zip') as z:
        ranking=pd.read_csv(z.open('campaigns/base/random/prediction_ranking_60.csv'))
        assert len(ranking)==20
    verify_repetition(folder)
    atomic_bytes(folder/'monthly.csv',b'corrupted')
    with pytest.raises(AssertionError):verify_repetition(folder)
