"""Approved eight-condition main experiment; fixed before its new runs."""
from dataclasses import replace
from article9.selection import POLICIES
from pilot_design import scenarios, configurations

CONDITIONS = ('base','complexity_020','complexity_080','mixing_005','mixing_040',
              'adoption_m3','satisfaction_070','adoption_m3_satisfaction_070')
PRIMARY = ('mean_awareness_fraction_1_60','mean_adoption_fraction_1_60','revenue_60')


def main_design():
    chosen=[s for name in CONDITIONS for s in scenarios() if s['id']==name]
    return {'version':'1.0.0','scope':'approved_main_experiment','approved_date':'2026-09-27',
        'scenarios':chosen,'policies':list(POLICIES),'repetitions':list(range(20,120)),
        'excluded_pilot_repetitions':list(range(20)),'campaigns':5600,'master_seed':20260925,
        'primary_horizon':60,'sensitivity_horizon':120,'primary_metrics':list(PRIMARY),
        'baseline':{k:v.to_dict() for k,v in zip(('m1','m2','m3'),main_configs(chosen[0]))},
        'bootstrap':{'seed':20260927,'draws':4000,'unit':'paired_repetition_block',
            'pointwise_interval':'percentile_95','primary_family':144,
            'simultaneous_interval':'approximate_max_standardized_bootstrap_95_across_144_primary_contrasts'},
        'primary_reference_policy':'random','replication_rule':'fixed_100_new_blocks_no_outcome_based_stopping',
        'full_trace_sample':{'repetition':20,'policy':'random','scenarios':list(CONDITIONS)},
        'limits':['not_full_factorial','conditional_prediction_among_selected_20',
                  'no_actor_loss_or_role_correlation_experiment','profit_is_affine_in_revenue',
                  'no_empirical_calibration','120_is_not_assumed_absorption']}


def main_configs(scenario):
    m1,m2,m3=configurations(scenario)
    return replace(m1,horizon_months=120),replace(m2,horizon_months=120),m3
