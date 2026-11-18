"""Checked campaign measures and paired Monte Carlo summaries."""
import math
import numpy as np
import pandas as pd

ANALYSIS_METRICS = ["adoption_fraction","awareness_fraction","mean_adoption_fraction_1_60",
    "adoption_fraction_month12","adoption_fraction_month30","revenue","profit","saturated_95",
    "reached_50","restricted_t50","wom_redundancy","conditional_leader_precision",
    "conditional_leader_recall","conditional_leader_spearman","top_seed_revenue_share"]


def campaign_metrics(diffusion, economic):
    p=diffusion.periods.set_index("month");h=int(p.index.max())
    t=diffusion.summary["month_to_50pct_adoption"]
    revenue=economic.summary["revenue"]
    return {**economic.summary,
        "mean_adoption_fraction_1_60":float(p.loc[1:h,"adoption_fraction"].mean()),
        "adoption_fraction_month12":float(p.loc[min(12,h),"adoption_fraction"]),
        "adoption_fraction_month30":float(p.loc[min(30,h),"adoption_fraction"]),
        "saturated_95":int(economic.summary["adoption_fraction"] >= .95),
        "reached_50":int(t is not None),"restricted_t50":h+1 if t is None else t,
        "top_seed_revenue_share":float(economic.seed_accounts.root_revenue.max()/revenue) if revenue>0 else None}


def validate_campaign(diffusion, economic, n, k, horizon):
    tx=economic.transactions;s=economic.summary
    if len(diffusion.periods)!=horizon+1 or len(diffusion.final_states)!=n:
        raise AssertionError("Incomplete trajectory")
    assert 0 <= s["adoption_count"] <= s["awareness_count"] <= n
    assert len(tx.loc[tx.kind=="initial"])==s["adoption_count"]
    assert tx.transaction_id.is_unique and not tx.duplicated(["month","actor_id"]).any()
    assert len(economic.activation_costs)==k
    assert len(diffusion.state_history)==n*(horizon+1)
    assert not diffusion.events.duplicated(["sender","receiver"]).any()
    assert (diffusion.events.sender_adoption_month < diffusion.events.month).all()
    assert int(diffusion.events.conversion_credit.sum()) == s["wom_source_adoptions"]
    assert (tx.month >= tx.adoption_month).all() and (tx.month <= horizon).all()
    assert (tx.loc[tx.kind=="repurchase","month"]>tx.loc[tx.kind=="repurchase","adoption_month"]).all()
    close=lambda a,b: math.isclose(float(a),float(b),rel_tol=1e-10,abs_tol=1e-7)
    assert close(math.fsum(tx.revenue),s["revenue"])
    assert close(s["revenue"]-s["service_cost"]-s["activation_cost"],s["profit"])
    for prefix in ["own","immediate","root","attributed"]:
        assert close(math.fsum(economic.actor_accounts[f"{prefix}_revenue"]),s["revenue"])
        assert close(math.fsum(economic.actor_accounts[f"{prefix}_profit"]),s["profit"])
    assert close(economic.periods.cumulative_profit.iloc[-1],s["profit"])
    assert close(economic.seed_accounts.root_revenue.sum(),s["revenue"])


def estimate(values, indices):
    values=np.asarray(values,dtype=float)
    finite=values[np.isfinite(values)]
    n=len(finite)
    if not n:return {"n":0,"mean":None,"sd":None,"mcse":None,"ci_low":None,"ci_high":None}
    if n==len(values):
        means=values[indices].mean(axis=1)
    else:
        # Missing conditional metrics: intervals are explicitly conditional on available blocks.
        indices=np.random.default_rng(20260927+n).integers(0,n,size=(len(indices),n))
        means=finite[indices].mean(axis=1)
    sd=float(finite.std(ddof=1)) if n>1 else None
    return {"n":n,"mean":float(finite.mean()),"sd":sd,"mcse":sd/math.sqrt(n) if n>1 else None,
        "ci_low":float(np.quantile(means,.025)),"ci_high":float(np.quantile(means,.975))}


def paired_contrast(table, treatment, reference, metric, key="scenario"):
    other="policy" if key=="scenario" else "scenario"
    a=table.loc[table[key]==treatment,[other,"repetition",metric]]
    b=table.loc[table[key]==reference,[other,"repetition",metric]]
    joined=a.merge(b,on=[other,"repetition"],validate="one_to_one",suffixes=("_a","_b"),how="outer",indicator=True)
    if not joined._merge.eq("both").all():raise ValueError("Unpaired blocks")
    joined["difference"]=joined[f"{metric}_a"]-joined[f"{metric}_b"]
    return joined[[other,"repetition","difference"]]


def validate_grid(summary, scenario_ids, policies, repetitions):
    expected={(s,p,r) for s in scenario_ids for p in policies for r in repetitions}
    observed=list(summary[["scenario","policy","repetition"]].itertuples(index=False,name=None))
    if len(observed)!=len(expected) or set(observed)!=expected:raise ValueError("Incomplete or duplicate campaign grid")


def interaction(table, metric):
    levels=["base","adoption_m3","satisfaction_070","adoption_m3_satisfaction_070"]
    p=table.loc[table.scenario.isin(levels)].pivot(index=["policy","repetition"],columns="scenario",values=metric)
    if p.isna().any().any():raise ValueError("Incomplete interaction grid")
    return (p[levels[3]]-p[levels[1]]-p[levels[2]]+p[levels[0]]).rename("difference").reset_index()
