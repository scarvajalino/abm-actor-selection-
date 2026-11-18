"""Regression checks for fixed windows, absorption and horizon invariance."""
from dataclasses import replace
import numpy as np
import pandas as pd
import pytest
from article9.model import initialize, run_policies
from article9.diffusion import simulate
from article9.economics import account_campaign
from horizon_metrics import CONDITIONS, absorption_month, horizon_metrics
from run_horizon120 import design120, assert_same, canonical, output_hashes
from pilot_design import configurations


def test_H01_frozen_design():
    design = design120()
    assert tuple(s['id'] for s in design['scenarios']) == CONDITIONS
    assert len(design['repetitions']) * len(design['policies']) * len(CONDITIONS) == 560
    assert design['horizon_months'] == 120
    for s in design['scenarios']:
        c, d, e = configurations(s)
        assert c.n_agents == 600 and c.k == 20 and e.repurchase_probability == 0


@pytest.mark.parametrize('scenario', design120()['scenarios'], ids=CONDITIONS)
def test_H02_horizon_prefix_invariance(scenario):
    c, d, e = configurations(scenario)
    c = replace(c, n_agents=60, n_communities=6, k=6, mean_degree=6)
    pop = initialize(c, 2)
    selections, _ = run_policies(pop, c)
    short = simulate(pop, selections['random'], c, replace(d, horizon_months=5))
    long = simulate(pop, selections['random'], c, replace(d, horizon_months=10))
    for name in ('periods', 'state_history', 'events', 'evaluations', 'sender_log'):
        actual = getattr(long, name)
        assert_same(actual.loc[actual.month <= 5], canonical(getattr(short, name)))
    a = account_campaign(pop, selections['random'], short, c, e)
    b = account_campaign(pop, selections['random'], long, c, e)
    assert_same(b.transactions.loc[b.transactions.month <= 5], canonical(a.transactions))


def test_H03_absorption_excludes_zero_and_quiet_months():
    p = pd.DataFrame({'month':[0,1,2,3,4], 'eligible_senders_next_month':[0,2,1,0,0],
        'new_adoptions':[0,2,0,1,0], 'wom_messages_new':[0,0,0,1,0]})
    assert absorption_month(p) == 3
    assert absorption_month(p.iloc[:3]) is None
    bad = p.copy(); bad.loc[4, 'new_adoptions'] = 1
    with pytest.raises(AssertionError): absorption_month(bad)


def test_H04_windows_and_censoring():
    from types import SimpleNamespace
    p = pd.DataFrame({'month':np.arange(121), 'adoption_fraction':np.arange(121)/600,
        'adoption_count':np.arange(121), 'awareness_fraction':np.arange(121)/600,
        'eligible_senders_next_month':[0]+[1]*120, 'new_adoptions':[0]+[1]*120, 'wom_messages_new':[0]+[1]*120})
    d = SimpleNamespace(periods=p, policy='random', repetition=0, summary={'month_to_50pct_adoption':None})
    e = SimpleNamespace(periods=pd.DataFrame({'month':np.arange(121), 'cumulative_revenue':np.arange(121)*100,
        'cumulative_profit':np.arange(121)*80-20}))
    m = horizon_metrics(d,e)
    assert m['adoption_count_gain_60_120'] == 60 and m['new_adoptions_109_120'] == 12
    assert m['mean_adoption_fraction_1_60'] == pytest.approx(30.5/600)
    assert m['mean_adoption_fraction_61_120'] == pytest.approx(90.5/600)
    assert m['absorption_month'] is None and m['month_to_50pct_adoption'] is None
    assert m['ongoing_120'] == 1 and m['reached_50_120'] == 0


def test_H05_prefix_rejects_changes():
    a = pd.DataFrame({'month':[0,1], 'adoption':[0.,.1]})
    assert_same(a, canonical(a))
    b = a.copy(); b.loc[1, 'adoption'] += 1e-12
    with pytest.raises(AssertionError): assert_same(a, b)


def test_H06_manifest_never_hashes_itself(tmp_path):
    names = ['campaigns.csv', 'monthly.csv', 'prefix_checks.csv', 'records.zip']
    for name in names:
        (tmp_path/name).write_bytes(b'test')
    (tmp_path/'completion.json').write_text('{}')
    assert set(output_hashes(tmp_path)) == set(names)
