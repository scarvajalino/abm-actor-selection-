"""Comparable fixed windows and absorbing-state diagnostics for horizon extension."""
import pandas as pd

CONDITIONS = ('base', 'adoption_m3', 'satisfaction_070', 'adoption_m3_satisfaction_070')


def absorption_month(periods):
    # Month zero precedes the scheduled seed evaluation and is NOT absorbing.
    eligible = periods.loc[periods.month >= 1, 'eligible_senders_next_month']
    dead = periods.loc[(periods.month >= 1) & (periods.eligible_senders_next_month == 0), 'month']
    if dead.empty:
        return None
    first = int(dead.iloc[0])
    assert periods.loc[periods.month >= first, 'eligible_senders_next_month'].eq(0).all()
    assert periods.loc[periods.month > first, ['new_adoptions', 'wom_messages_new']].eq(0).all().all()
    return first


def horizon_metrics(diffusion, economic):
    p = diffusion.periods.set_index('month')
    e = economic.periods.set_index('month')
    assert p.index.tolist() == list(range(121))
    assert (p.adoption_count.diff().dropna() >= 0).all()
    result = {'policy': diffusion.policy, 'repetition': diffusion.repetition}
    for month in (60, 90, 120):
        for metric in ('adoption_fraction', 'adoption_count', 'awareness_fraction', 'eligible_senders_next_month'):
            result[f'{metric}_{month}'] = float(p.loc[month, metric])
        for metric in ('revenue', 'profit'):
            result[f'{metric}_{month}'] = float(e.loc[month, f'cumulative_{metric}'])
        result[f'saturated_95_{month}'] = int(p.loc[month, 'adoption_fraction'] >= .95)
        result[f'reached_50_{month}'] = int(p.loc[month, 'adoption_fraction'] >= .50)
        result[f'absorbed_{month}'] = int(p.loc[month, 'eligible_senders_next_month'] == 0)
    for metric in ('adoption_fraction', 'adoption_count', 'revenue', 'profit'):
        result[f'{metric}_gain_60_120'] = result[f'{metric}_120'] - result[f'{metric}_60']
    result['adoption_fraction_gain_108_120'] = float(p.loc[120, 'adoption_fraction'] - p.loc[108, 'adoption_fraction'])
    result['new_adoptions_109_120'] = int(p.loc[109:120, 'new_adoptions'].sum())
    result['mean_adoption_fraction_1_60'] = float(p.loc[1:60, 'adoption_fraction'].mean())
    result['mean_adoption_fraction_61_120'] = float(p.loc[61:120, 'adoption_fraction'].mean())
    result['mean_adoption_fraction_1_120'] = float(p.loc[1:120, 'adoption_fraction'].mean())
    result['absorption_month'] = absorption_month(diffusion.periods)
    result['last_observed_adoption_month'] = int(p.index[p.new_adoptions > 0].max()) if (p.new_adoptions > 0).any() else None
    result['month_to_50pct_adoption'] = diffusion.summary['month_to_50pct_adoption']
    result['positive_growth_60_120'] = int(result['adoption_count_gain_60_120'] > 0)
    result['positive_growth_109_120'] = int(result['new_adoptions_109_120'] > 0)
    result['ongoing_120'] = 1 - result['absorbed_120']
    return result
