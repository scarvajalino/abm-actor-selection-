"""Horizon-specific outcomes without using future actor states for month 60."""
from dataclasses import replace
import math
import pandas as pd
from horizon_metrics import horizon_metrics


def slice_diffusion(d,horizon):
    if horizon<1 or horizon>int(d.periods.month.max()):raise ValueError('Invalid prefix horizon')
    periods=d.periods.loc[d.periods.month<=horizon].copy()
    history=d.state_history.loc[d.state_history.month<=horizon].copy()
    final=history.loc[history.month==horizon].reset_index(drop=True)
    events=d.events.loc[d.events.month<=horizon].copy()
    summary={**d.summary,**periods.iloc[-1].to_dict()}
    for variable,thresholds in [('awareness',(.1,.25,.5,.75)),('adoption',(.1,.25,.5))]:
        for t in thresholds:
            reached=periods.loc[periods[f'{variable}_fraction']>=t,'month']
            summary[f'month_to_{int(100*t)}pct_{variable}']=int(reached.min()) if len(reached) else None
    rows=[]
    for root in sorted(final.loc[final.selected,'actor_id']):
        members=final.loc[final.root_seed==root]
        own=final.loc[final.actor_id==root].iloc[0]
        direct=own.acquisition_source=='seed'
        rows.append({'root_seed':int(root),'seed_direct_adoption':bool(direct),
            'seed_adopted_via_wom':own.acquisition_source=='wom',
            'cascade_adopters_including_root':len(members),'cascade_adopters_excluding_root':len(members)-int(direct),
            'max_depth':float(members.cascade_depth.max()) if len(members) else None,
            'communities_with_adoption':int(members.community_id.nunique()),
            'wom_events':int((events.root_seed==root).sum()),'eligible_senders_at_end':int(members.wom_active.sum())})
    return replace(d,periods=periods,state_history=history,final_states=final,events=events,
        evaluations=d.evaluations.loc[d.evaluations.month<=horizon].copy(),
        sender_log=d.sender_log.loc[d.sender_log.month<=horizon].copy(),
        cascades=pd.DataFrame(rows),summary=summary)


def gini(values):
    values=sorted(float(v) for v in values)
    if not values or math.fsum(values)==0:return None
    n=len(values)
    return (2*math.fsum((i+1)*v for i,v in enumerate(values))/(n*math.fsum(values)))-(n+1)/n


def main_metrics(d120,e120,d60,e60):
    result=horizon_metrics(d120,e120)
    p=d120.periods.set_index('month')
    result['mean_awareness_fraction_1_60']=float(p.loc[1:60,'awareness_fraction'].mean())
    result['mean_awareness_fraction_61_120']=float(p.loc[61:120,'awareness_fraction'].mean())
    for h,d,e in [(60,d60,e60),(120,d120,e120)]:
        s=d.summary;v=e.summary
        for metric in ['awareness_count','wom_messages_cumulative','wom_unique_reach','wom_redundancy',
            'communities_aware','communities_with_adoption','selected_adopters','satisfied_customers',
            'wom_source_adoptions','seed_source_adoptions']:
            result[f'{metric}_{h}']=s[metric]
        for metric in ['conditional_leader_precision','conditional_leader_recall','conditional_leader_spearman',
            'conditional_normalized_rank_mae','purchase_value_mae_among_adopters']:
            result[f'{metric}_{h}']=v[metric]
        for var,thresholds in [('awareness',(10,25,50,75)),('adoption',(10,25,50))]:
            for threshold in thresholds:
                result[f'month_to_{threshold}pct_{var}_{h}']=s[f'month_to_{threshold}pct_{var}']
        result[f'conversion_per_unique_wom_reach_{h}']=s['wom_source_adoptions']/s['wom_unique_reach'] if s['wom_unique_reach'] else None
        result[f'conversion_per_wom_message_{h}']=s['wom_source_adoptions']/s['wom_messages_cumulative'] if s['wom_messages_cumulative'] else None
        revenues=e.seed_accounts.root_revenue
        result[f'top_seed_revenue_share_{h}']=float(revenues.max()/v['revenue']) if v['revenue'] else None
        result[f'root_revenue_gini_{h}']=gini(revenues)
        assert math.isclose(result[f'revenue_{h}'],v['revenue'],rel_tol=1e-10,abs_tol=1e-7)
        assert math.isclose(v['profit'],.8*v['revenue']-20,rel_tol=1e-10,abs_tol=1e-7)
    return result
