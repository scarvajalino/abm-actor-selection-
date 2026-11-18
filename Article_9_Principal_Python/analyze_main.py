"""Analyze approved outcomes; preserve pairing and separate primary and secondary results."""
import argparse
import json
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from article9.export import sha256
from pilot_metrics import validate_grid,paired_contrast,interaction,estimate
from main_design import CONDITIONS,PRIMARY
from main_statistics import descriptive,simultaneous_primary
from run_main import atomic_bytes,json_bytes,csv_bytes,verify_repetition

POLICIES={'random':'Aleatoria','hubs':'Hubs','influencers':'Influencers','opinion_leaders':'Líderes de opinión',
    'predicted_revenue':'Ingresos previstos','community_diversified':'Diversificada','hybrid':'Híbrida'}
LABELS={'base':'Base M3','complexity_020':'Complejidad 0,20','complexity_080':'Complejidad 0,80',
    'mixing_005':'Mezcla 0,05','mixing_040':'Mezcla 0,40','adoption_m3':'Intercepto −3',
    'satisfaction_070':'Satisfacción 0,70','adoption_m3_satisfaction_070':'Intercepto −3 + satisfacción 0,70'}
SECONDARY=['adoption_fraction_60','adoption_fraction_120','awareness_fraction_60','awareness_fraction_120',
    'profit_60','revenue_120','profit_120','adoption_fraction_gain_60_120','adoption_fraction_gain_108_120',
    'eligible_senders_next_month_60','eligible_senders_next_month_120','ongoing_120','absorbed_60','absorbed_120',
    'saturated_95_60','saturated_95_120','reached_50_60','reached_50_120',
    'wom_unique_reach_60','wom_redundancy_60','communities_with_adoption_60','communities_aware_60',
    'conversion_per_unique_wom_reach_60','conversion_per_wom_message_60','top_seed_revenue_share_60',
    'root_revenue_gini_60','conditional_leader_precision_60','conditional_leader_recall_60',
    'conditional_leader_spearman_60','conditional_normalized_rank_mae_60','mean_adoption_fraction_61_120']


def save_csv(path,frame):atomic_bytes(path,csv_bytes(frame))


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True)
    args=parser.parse_args();root=args.input.resolve();out=root/'analysis'
    if out.exists() and any(out.iterdir()):parser.error('Use an absent or empty analysis directory')
    out.mkdir(exist_ok=True)
    design=json.loads((root/'design.json').read_text());completed=json.loads((root/'completion.json').read_text())
    assert completed['status']=='passed' and completed['campaigns']==5600
    assert sha256(root/'campaigns_all.csv')==completed['summary_sha256']
    data=pd.read_csv(root/'campaigns_all.csv',float_precision='round_trip')
    validate_grid(data,CONDITIONS,design['policies'],design['repetitions'])
    assert set(data.repetition)==set(range(20,120))
    monthly=[];networks=[];provenance=[];communities=[];diagnostics=[]
    cols=['scenario','policy','repetition','month','adoption_fraction','awareness_fraction',
          'eligible_senders_next_month','cumulative_revenue','new_adoptions']
    for rep in design['repetitions']:
        folder=root/f'rep_{rep:03d}';record=verify_repetition(folder)
        assert record['campaigns']==56 and record['monthly_rows']==56*121
        monthly.append(pd.read_csv(folder/'monthly.csv',usecols=cols,float_precision='round_trip'))
        with zipfile.ZipFile(folder/'records.zip') as z:
            for name,target in [('network_diagnostics',networks),('provenance',provenance),('communities',communities),('policy_diagnostics',diagnostics)]:
                target.append(pd.read_csv(z.open(name+'.csv'),float_precision='round_trip'))
    monthly=pd.concat(monthly,ignore_index=True);networks=pd.concat(networks,ignore_index=True)
    provenance=pd.concat(provenance,ignore_index=True)
    assert len(monthly)==5600*121 and not monthly.duplicated(['scenario','policy','repetition','month']).any()
    assert provenance[['economics_60_prefix_exact','validation_60','validation_120']].eq(True).all().all()
    assert len(provenance)==5600
    save_csv(out/'network_diagnostics.csv',networks)
    save_csv(out/'policy_diagnostics.csv',pd.concat(diagnostics,ignore_index=True))
    save_csv(out/'community_outcomes.csv',pd.concat(communities,ignore_index=True))
    save_csv(out/'validation_by_campaign.csv',provenance)
    rng=np.random.default_rng(design['bootstrap']['seed'])
    indices=rng.integers(0,100,(design['bootstrap']['draws'],100))
    metrics=list(PRIMARY)+SECONDARY
    estimates=[]
    for (scenario,policy),group in data.groupby(['scenario','policy']):
        for metric in metrics:
            estimates.append({'scenario':scenario,'policy':policy,'metric':metric,
                **descriptive(group.sort_values('repetition')[metric],indices)})
    estimates=pd.DataFrame(estimates);save_csv(out/'scenario_policy_estimates.csv',estimates)
    pairs=[];matrix=[];keys=[]
    for scenario in CONDITIONS:
        group=data.loc[data.scenario==scenario]
        for policy in design['policies']:
            if policy=='random':continue
            for metric in metrics:
                joined=group.loc[group.policy==policy,['repetition',metric]].merge(
                    group.loc[group.policy=='random',['repetition',metric]],on='repetition',validate='one_to_one',suffixes=('_a','_b')).sort_values('repetition')
                delta=joined[f'{metric}_a']-joined[f'{metric}_b']
                key={'scenario':scenario,'policy':policy,'metric':metric}
                pairs.append({**key,**descriptive(delta,indices)})
                if metric in PRIMARY:matrix.append(delta.to_numpy());keys.append(key)
    pairs=pd.DataFrame(pairs);save_csv(out/'paired_policy_minus_random.csv',pairs)
    simultaneous=simultaneous_primary(np.column_stack(matrix),indices)
    bands=pd.DataFrame([{**key,'n':100,'mean':simultaneous['mean'][i],'mcse':simultaneous['mcse'][i],
        'simultaneous_low':simultaneous['low'][i],'simultaneous_high':simultaneous['high'][i],
        'zero_sample_variance':bool(simultaneous['zero_sample_variance'][i]),
        'family_size':len(keys),'critical_value':simultaneous['critical']} for i,key in enumerate(keys)])
    assert len(bands)==144
    save_csv(out/'primary_simultaneous_contrasts.csv',bands)
    scenario_pairs=[];effect_modification=[]
    for scenario in CONDITIONS[1:]:
        for metric in PRIMARY:
            contrast=paired_contrast(data,scenario,'base',metric)
            for policy,g in contrast.groupby('policy'):
                scenario_pairs.append({'scenario':scenario,'policy':policy,'metric':metric,
                    **descriptive(g.sort_values('repetition').difference,indices)})
            pivot=contrast.pivot(index='repetition',columns='policy',values='difference').sort_index()
            for policy in design['policies']:
                if policy!='random':effect_modification.append({'scenario':scenario,'policy':policy,'metric':metric,
                    **descriptive(pivot[policy]-pivot['random'],indices)})
    save_csv(out/'paired_scenario_minus_base.csv',pd.DataFrame(scenario_pairs))
    save_csv(out/'policy_by_condition_interactions.csv',pd.DataFrame(effect_modification))
    factor=[]
    for metric in list(PRIMARY)+['adoption_fraction_60','adoption_fraction_120']:
        values=interaction(data,metric)
        for policy,g in values.groupby('policy'):
            factor.append({'policy':policy,'metric':metric,**descriptive(g.sort_values('repetition').difference,indices)})
    save_csv(out/'adoption_satisfaction_interaction.csv',pd.DataFrame(factor))
    overview=[]
    pooled=data.groupby(['scenario','repetition'],as_index=False)[metrics].mean()
    for scenario,g in pooled.groupby('scenario'):
        for metric in metrics:
            overview.append({'scenario':scenario,'metric':metric,**descriptive(g.sort_values('repetition')[metric],indices)})
    overview=pd.DataFrame(overview);save_csv(out/'overview_paired_blocks.csv',overview)
    curves=[]
    for (scenario,month),g in monthly.groupby(['scenario','month']):
        block=g.groupby('repetition')[['adoption_fraction','awareness_fraction','eligible_senders_next_month']].mean().sort_index()
        for metric in block:
            curves.append({'scenario':scenario,'month':month,'metric':metric,**estimate(block[metric],indices)})
    curves=pd.DataFrame(curves);save_csv(out/'monthly_pooled_curves.csv',curves)
    policy_curves=monthly.groupby(['scenario','policy','month'],as_index=False)[['adoption_fraction','awareness_fraction','cumulative_revenue']].mean()
    save_csv(out/'monthly_policy_mean_curves.csv',policy_curves)
    leaders=[]
    for scenario in CONDITIONS:
        for metric in PRIMARY:
            subset=estimates.loc[(estimates.scenario==scenario)&(estimates.metric==metric)]
            best=subset['mean'].max()
            for row in subset.loc[subset['mean']==best].itertuples():
                leaders.append({'scenario':scenario,'metric':metric,'policy':row.policy,'mean':row.mean,
                    'interpretation':'highest_observed_mean_not_established_unique_winner'})
    leaders=pd.DataFrame(leaders);save_csv(out/'descriptive_decision_map.csv',leaders)
    # Stability diagnostics use disjoint blocks; no repetition is removed.
    stability=[]
    for (scenario,policy),g in data.groupby(['scenario','policy']):
        for metric in PRIMARY:
            a=g.loc[g.repetition<70,metric];b=g.loc[g.repetition>=70,metric]
            stability.append({'scenario':scenario,'policy':policy,'metric':metric,
                'first_50_mean':float(a.mean()),'last_50_mean':float(b.mean()),
                'difference_last_minus_first':float(b.mean()-a.mean())})
    save_csv(out/'replication_precision_diagnostics.csv',pd.DataFrame(stability))
    plot_results(out,estimates,curves,bands)
    write_report(out,data,estimates,overview,leaders,bands,networks)
    validation={'status':'passed','campaigns':5600,'new_repetition_blocks':100,'repetitions':[20,119],
        'monthly_rows':len(monthly),'archives_verified':100,'full_trace_samples':8,'monthly_prefix_economic_checks':5600,
        'primary_contrasts':144,'bootstrap_draws':4000,'simultaneous_critical_value':simultaneous['critical'],
        'core_equations_unchanged':True,'undefined_spearman_60':int(data.conditional_leader_spearman_60.isna().sum()),
        'undefined_spearman_120':int(data.conditional_leader_spearman_120.isna().sum())}
    atomic_bytes(out/'analysis_validation.json',json_bytes(validation))
    atomic_bytes(out/'manifest.json',json_bytes({p.name:sha256(p) for p in sorted(out.iterdir()) if p.is_file()}))
    print(json.dumps(validation));print(leaders.to_string(index=False))


def plot_results(out,estimates,curves,bands):
    fig,axes=plt.subplots(2,4,figsize=(15,7),layout='constrained',sharex=True,sharey=True)
    for ax,scenario in zip(axes.flat,CONDITIONS):
        d=curves.loc[(curves.scenario==scenario)&(curves.metric=='adoption_fraction')].sort_values('month')
        ax.plot(d.month,d['mean']*100,color='#315b92',lw=2)
        ax.fill_between(d.month,d.ci_low*100,d.ci_high*100,color='#315b92',alpha=.17)
        ax.axvline(60,color='#777',ls='--',lw=.9);ax.set_title(LABELS[scenario],fontsize=10)
        ax.set_xlim(0,120);ax.set_ylim(0,102);ax.grid(alpha=.18);ax.spines[['top','right']].set_visible(False)
    fig.supxlabel('Mes');fig.supylabel('Adopción acumulada (%)')
    fig.suptitle('Experimento principal · 100 bloques nuevos · media de siete políticas',fontsize=13)
    fig.savefig(out/'01_main_adoption_trajectories.png',dpi=180);plt.close(fig)
    fig,axes=plt.subplots(1,3,figsize=(14,5.8),layout='constrained')
    policy_order=list(POLICIES)
    for ax,metric,title in zip(axes,PRIMARY,['Conocimiento medio 1–60 (%)','Adopción media 1–60 (%)','Ingresos acumulados al mes 60 (u.m.)']):
        pivot=estimates.loc[estimates.metric==metric].pivot(index='scenario',columns='policy',values='mean').reindex(index=CONDITIONS,columns=policy_order)
        values=pivot.to_numpy()*(100 if metric!='revenue_60' else 1)
        ax.imshow(values,aspect='auto',cmap='Blues')
        ax.set_title(title,fontsize=10);ax.set_xticks(range(7),[POLICIES[p] for p in policy_order],rotation=70,ha='right',fontsize=8)
        ax.set_yticks(range(8),[LABELS[s] for s in CONDITIONS] if ax==axes[0] else ['']*8,fontsize=8)
        midpoint=(values.min()+values.max())/2
        for i in range(8):
            for j in range(7):
                label=f'{values[i,j]:.1f}' if metric!='revenue_60' else f'{values[i,j]/1000:.1f}k'
                ax.text(j,i,label,ha='center',va='center',fontsize=7,color='white' if values[i,j]>midpoint else '#222')
    fig.suptitle('Resultados principales por condición y política · medias descriptivas',fontsize=13)
    fig.savefig(out/'02_main_policy_outcomes.png',dpi=180);plt.close(fig)


def write_report(out,data,estimates,overview,leaders,bands,networks):
    lookup=overview.set_index(['scenario','metric'])
    def mean(s,m):return float(lookup.loc[(s,m),'mean'])
    lines=['# Artículo 9 Experimento principal de selección de actores','',
        '**Ejecución completada:** 5.600 campañas = ocho condiciones × siete políticas × 100 repeticiones nuevas. Se ejecutó cada trayectoria hasta 120 meses; el horizonte principal es 60. Las repeticiones 20–119 están separadas del piloto 0–19. No se cambiaron ecuaciones ni costos para obtener una política ganadora.','',
        '## Diseño y alcance','',
        'Red fija por campaña de 600 personas y seis comunidades; grado esperado 12; 20 seleccionados; semilla maestra 20260925. Se mantiene la misma población y los mismos campos aleatorios entre políticas dentro de cada bloque. Solo los escenarios de mezcla cambian la red. La matriz contiene la base, complejidad 0,20/0,80, mezcla 0,05/0,40 y las tres variantes del cruce adopción–satisfacción. No es un factorial completo entre todos los parámetros.','',
        'Los objetivos primarios fijados son conocimiento medio mensual 1–60, adopción media mensual 1–60 e ingresos acumulados al mes 60. Las medias temporales combinan velocidad y penetración; no son tasas de incidencia. Se preservan 100 repeticiones por condición y política, sin parada basada en resultados.','',
        '## Penetración y continuidad temporal','',
        'Cada fila promedia primero las siete políticas dentro de una repetición y luego los 100 bloques. Las 700 campañas de cada condición no se consideran independientes.','',
        '| Condición | Adopción 60 % | Adopción 120 % | Ganancia pp | Campañas con emisores al mes 120 |',
        '|---|---:|---:|---:|---:|']
    for s in CONDITIONS:
        active=int(data.loc[data.scenario==s,'ongoing_120'].sum())
        lines.append(f"| {LABELS[s]} | {100*mean(s,'adoption_fraction_60'):.2f} | {100*mean(s,'adoption_fraction_120'):.2f} | {100*mean(s,'adoption_fraction_gain_60_120'):.2f} | {active}/700 |")
    lines+=['','![Trayectorias](01_main_adoption_trajectories.png)','',
        'Una campaña sin emisores elegibles después de la evaluación inicial está absorbida bajo las reglas estáticas. Un mes sin mensajes no demuestra absorción. Saturación ≥95% y absorción son distintos. Las trayectorias activas al mes 120 no tienen una penetración terminal observada; los tiempos a umbrales no alcanzados permanecen vacíos.','',
        '## Mapa descriptivo por objetivo','',
        'La tabla identifica las mayores medias observadas. No demuestra superioridad única frente a todas las alternativas, ni superioridad universal. Los datos completos contienen las siete políticas y su dispersión.','',
        '| Condición | Mayor conocimiento medio | Mayor adopción media | Mayores ingresos al mes 60 |','|---|---|---|---|']
    for s in CONDITIONS:
        names=[' / '.join(POLICIES[p] for p in leaders.loc[(leaders.scenario==s)&(leaders.metric==m),'policy']) for m in PRIMARY]
        lines.append('| '+LABELS[s]+' | '+' | '.join(names)+' |')
    lines+=['','![Resultados por política](02_main_policy_outcomes.png)','',
        '## Contrastes emparejados e incertidumbre','',
        'La unidad de remuestreo es la repetición completa. Se realizaron 4.000 remuestreos bootstrap (semilla 20260927). Se entregan medias, medianas, desviaciones, IQR, percentiles 5/95, errores estándar Monte Carlo e intervalos percentiles puntuales de 95%. Las métricas indefinidas se excluyen con tamaño efectivo explícito.','',
        'Para los 144 contrastes primarios fijados (seis políticas frente a aleatoria × ocho condiciones × tres métricas), también se calculan bandas simultáneas aproximadas de 95% mediante el máximo de las desviaciones bootstrap estandarizadas por el error estándar observado. No son intervalos exactos de cobertura garantizada. La misma selección de bloques preserva la dependencia entre todos los contrastes. Los contrastes secundarios y las interacciones llevan intervalos puntuales, sin corrección de multiplicidad.','',
        '| Métrica primaria | Contrastes con banda simultánea por encima de cero | Por debajo de cero | Incluye cero |','|---|---:|---:|---:|']
    for m,label in zip(PRIMARY,['Conocimiento medio 1–60','Adopción media 1–60','Ingresos al mes 60']):
        b=bands.loc[bands.metric==m];above=int((b.simultaneous_low>0).sum());below=int((b.simultaneous_high<0).sum())
        lines.append(f'| {label} | {above}/48 | {below}/48 | {48-above-below}/48 |')
    lines+=['','Cien repeticiones reducen el error Monte Carlo, pero no garantizan que diferencias pequeñas queden bien determinadas. Se entrega el error de cada contraste y un diagnóstico descriptivo entre las primeras y últimas 50 repeticiones. Estos diagnósticos no se usaron para excluir campañas ni seleccionar una política. La incertidumbre es interna al modelo, no incertidumbre empírica sobre empresas reales.','',
        '## Red y atribución','',
        '| Mezcla entre comunidades | Modularidad media observada | Grado medio observado |','|---|---:|---:|']
    for mixing,g in networks.groupby('mixing_fraction'):
        lines.append(f'| {mixing:.2f} | {g.modularity.mean():.4f} | {g.degree_mean.mean():.3f} |')
    lines+=['','Una menor mezcla produce mayor modularidad en estas redes; el grado esperado permanece 12. Se guardan también cobertura y primer mes de adopción por comunidad, solapamiento de audiencias y correlaciones observadas. No se manipula el solapamiento ni las correlaciones como factores adicionales.','',
        'La economía no tiene recompra: servicio 20%, costo fijo cero y activación total 20 u.m. Por tanto, utilidad = 0,8 × ingresos − 20 y sus rankings coinciden necesariamente. Los ingresos de raíz son atribución contable bajo coexistencia de semillas; no efectos marginales contrafactuales de retirar actores.','',
        'La evaluación predictiva usa solamente los 20 seleccionados. Se calcula por separado a 60 y 120 meses, usando exclusivamente los estados y compras disponibles en cada horizonte. No evalúa la identificación de los mejores actores entre las 600 personas. El índice ex ante y las cantidades monetarias no se restan entre sí.','',
        '## Verificación y archivos','',
        'Se validaron las 5.600 campañas a ambos horizontes: compras únicas por adoptante, conservación contable, cronología de las cascadas, ausencia de pares emisor–receptor repetidos y consistencia exacta del prefijo económico 0–60. La rejilla contiene 677.600 filas mensuales. Los 100 archivos de repetición pasaron comprobaciones de integridad y hashes. Las pruebas automatizadas se adjuntan en el paquete de código.','',
        'Cada bloque conserva población, red, atributos ex ante y latentes, selección, diagnósticos, estados de todas las campañas a 60 y 120, compras, cuentas de raíces, rankings predictivos y cascadas. Las historias individuales mensuales, mensajes, evaluaciones y registros de emisores completos se conservan para ocho campañas preseleccionadas: repetición 20, política aleatoria, una por condición. Las demás historias completas pueden regenerarse con el código y las semillas; no se afirma que estén almacenadas en el paquete.','',
        '## Límites del artículo','',
        'El diseño cubre comparación de políticas, complejidad, modularidad y sensibilidad de adopción/satisfacción. No incluye pérdida de actores, recuperación, costos heterogéneos, presupuestos igualados con costos distintos, correlaciones controladas de roles ni separación entre heterogeneidad monetaria y error predictivo. No permite atribuir resiliencia a una política sin el experimento de pérdida de actores. Las reglas de credibilidad y expertise son supuestos estructurales explícitos, no relaciones empíricas estimadas.','',
        'El piloto informó la selección del diseño y sus métricas; los nuevos bloques aportan una evaluación separada de ese piloto dentro del mismo modelo. No hay calibración ni validación predictiva con datos reales. El horizonte de 120 meses es una sensibilidad de un sistema estático, no una proyección comercial a diez años.','',
        '## Reproducción','',
        '```bash','python -m pip install -r requirements-lock.txt','python -m pip install -r requirements-pilot.txt',
        'python -m pytest -q tests','python run_main.py --out outputs/main_v1 --workers 8',
        'python analyze_main.py --input outputs/main_v1','```','',
        'Usar una carpeta nueva. Para recursos limitados puede reducirse el número de trabajadores; no modifica semillas ni resultados. `--resume` acepta únicamente bloques ya verificados y código idéntico. Los ZIP se ensamblan y verifican antes de publicarse mediante escritura atómica. No se sobrescriben resultados del piloto.','']
    atomic_bytes(out/'Article_9_Experimento_principal_Informe_v1.0.md','\n'.join(lines).encode())


if __name__=='__main__':main()
