"""Checks specific to screening design, statistics, caching and recorded outputs."""
from copy import deepcopy
import json
import zipfile
import numpy as np
import pandas as pd
import pytest
from pilot_design import scenarios,configurations,diffusion_key,frozen_design
from pilot_metrics import estimate,paired_contrast,interaction,validate_grid,campaign_metrics
from run_pilot import run_repetition
from article9.model import initialize,run_policies
from article9.diffusion import simulate
from article9.economics import account_campaign


def test_P01_design():
    design=frozen_design();assert len(scenarios())==20 and design['campaign_evaluations']==2800
    assert len({diffusion_key(s) for s in scenarios()})==14
    for s in scenarios():
        m1,m2,m3=configurations(s)
        assert m1.n_agents==600 and m1.k==20 and m2.horizon_months==60
    assert len({s['id'] for s in scenarios()})==20


def test_P02_one_at_a_time():
    for s in scenarios():
        count=sum(len(s[k]) for k in ['m1','m2','m3'])
        assert count == (0 if s['id']=='base' else 2 if s['group']=='interaction' else 1)


def test_P03_noise_does_not_change_exante():
    base=configurations(scenarios()[0])[0];a=initialize(base,0)
    for s in scenarios():
        if s['group']!='value_noise':continue
        b=initialize(configurations(s)[0],0)
        assert a.nodes.equals(b.nodes) and sorted(a.graph.edges())==sorted(b.graph.edges())
        assert not a.latent.equals(b.latent)


def test_P04_paired_statistics():
    table=pd.DataFrame({'scenario':['base','base','a','a'],'policy':['random']*4,'repetition':[0,1,0,1],'x':[100,1000,105,1005]})
    delta=paired_contrast(table,'a','base','x')
    assert delta.difference.tolist()==[5,5]
    stats=estimate(delta.difference,np.array([[0,0],[0,1],[1,1]]))
    assert stats['mean']==stats['ci_low']==stats['ci_high']==5 and stats['mcse']==0
    with pytest.raises(ValueError):paired_contrast(table.iloc[:-1],'a','base','x')


def test_P05_censoring_and_monthly_average():
    from types import SimpleNamespace
    diff=SimpleNamespace(periods=pd.DataFrame({'month':[0,1,2],'adoption_fraction':[0,.1,.2]}),summary={'month_to_50pct_adoption':None})
    econ=SimpleNamespace(summary={'revenue':20,'adoption_fraction':.2},seed_accounts=pd.DataFrame({'root_revenue':[15,5]}))
    m=campaign_metrics(diff,econ)
    assert m['restricted_t50']==3 and m['reached_50']==0
    assert m['mean_adoption_fraction_1_60']==pytest.approx(.15) and m['top_seed_revenue_share']==.75


def test_P06_interaction_and_grid():
    levels=['base','adoption_m3','satisfaction_070','adoption_m3_satisfaction_070']
    table=pd.DataFrame({'scenario':levels,'policy':['random']*4,'repetition':[0]*4,'x':[10,8,5,1]})
    assert interaction(table,'x').difference.tolist()==[-2]
    validate_grid(table,levels,['random'],[0])
    with pytest.raises(ValueError):validate_grid(pd.concat([table,table.iloc[:1]]),levels,['random'],[0])


def test_P07_missing_values_and_reproducible_intervals():
    idx=np.random.default_rng(4).integers(0,3,(400,3))
    a=estimate([1,np.nan,3],idx)
    assert a==estimate([1,np.nan,3],idx) and a['n']==2 and a['mean']==2
    assert estimate([np.nan]*3,idx)['n']==0


def test_P08_worker_bundle_and_cached_economics(tmp_path):
    design=frozen_design();design['policies']=['random'];design['scenarios']=[s for s in scenarios() if s['id'] in ['base','value_sigma_000','service_rate_040']]
    r=run_repetition(0,tmp_path,design)
    assert r['campaigns']==3 and r['unique_diffusions']==1
    data=pd.read_csv(tmp_path/'rep_000/campaigns.csv').set_index('scenario')
    assert data.adoption_count.nunique()==1
    assert data.loc['base','revenue']==pytest.approx(data.loc['service_rate_040','revenue'])
    assert data.loc['service_rate_040','profit']==pytest.approx(.6*data.loc['base','revenue']-20)
    with zipfile.ZipFile(tmp_path/'rep_000/records.zip') as z:
        assert 'full_trace_sample/base/state_history.csv' in z.namelist()
        assert len(pd.read_csv(z.open('final_states.csv')))==600
