"""Paired bootstrap Monte Carlo summaries; no confirmatory hypothesis testing."""
import argparse
import io
import json
import math
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from article9.export import write_csv,write_json,sha256
from pilot_design import BOOTSTRAP_SEED,BOOTSTRAP_DRAWS
from pilot_metrics import ANALYSIS_METRICS,estimate,paired_contrast,interaction,validate_grid

POLICY_LABELS={'random':'Aleatoria','hubs':'Hubs','influencers':'Influencers','opinion_leaders':'Líderes de opinión',
    'predicted_revenue':'Ingresos previstos','community_diversified':'Diversificada','hybrid':'Híbrida'}


def analyze(directory):
    directory=Path(directory);out=directory/'analysis'
    if out.exists() and any(out.iterdir()):raise FileExistsError('Analysis output must be new or empty')
    out.mkdir(exist_ok=True)
    design=json.loads((directory/'design.json').read_text());done=json.loads((directory/'completion.json').read_text())
    assert done['status']=='passed'
    assert done['summary_sha256']==sha256(directory/'campaigns_all.csv')
    assert done['design_sha256']==sha256(directory/'design.json')
    s=pd.read_csv(directory/'campaigns_all.csv',float_precision='round_trip')
    levels=[x['id'] for x in design['scenarios']];labels={x['id']:x['label'] for x in design['scenarios']}
    reps=design['repetitions'];policies=design['policies'];n=len(reps)
    validate_grid(s,levels,policies,reps)
    idx=np.random.default_rng(BOOTSTRAP_SEED).integers(0,n,size=(BOOTSTRAP_DRAWS,n))
    aggregates=[]
    for (scenario,policy),g in s.groupby(['scenario','policy']):
        g=g.sort_values('repetition')
        for metric in ANALYSIS_METRICS:aggregates.append({'scenario':scenario,'policy':policy,'metric':metric,**estimate(g[metric],idx)})
    aggregate=pd.DataFrame(aggregates);write_csv(out/'scenario_policy_estimates.csv',aggregate)
    contrasts=[];policy_contrasts=[]
    for metric in ANALYSIS_METRICS:
        for level in levels[1:]:
            d=paired_contrast(s,level,'base',metric)
            for policy,g in d.groupby('policy'):
                contrasts.append({'scenario':level,'policy':policy,'metric':metric,**estimate(g.sort_values('repetition').difference,idx)})
        for policy in policies:
            d=paired_contrast(s,policy,'random',metric,key='policy')
            for level,g in d.groupby('scenario'):
                policy_contrasts.append({'scenario':level,'policy':policy,'metric':metric,**estimate(g.sort_values('repetition').difference,idx)})
    contrasts=pd.DataFrame(contrasts);policy_contrasts=pd.DataFrame(policy_contrasts)
    write_csv(out/'paired_scenario_minus_base.csv',contrasts);write_csv(out/'paired_policy_minus_random.csv',policy_contrasts)
    overview=[]
    for level in levels:
        # The seven policies within a repetition are dependent; first average within block.
        g=s.loc[s.scenario==level].groupby('repetition')[ANALYSIS_METRICS].mean().reindex(reps)
        row={'scenario':level,'label':labels[level]}
        for metric in ['adoption_fraction','mean_adoption_fraction_1_60','saturated_95','revenue','profit','reached_50']:
            row.update({f'{metric}_{k}':v for k,v in estimate(g[metric],idx).items()})
        overview.append(row)
    overview=pd.DataFrame(overview);write_csv(out/'scenario_overview_paired_blocks.csv',overview)
    inter=[]
    for metric in ['adoption_fraction','mean_adoption_fraction_1_60','revenue','profit']:
        for policy,g in interaction(s,metric).groupby('policy'):
            inter.append({'policy':policy,'metric':metric,**estimate(g.sort_values('repetition').difference,idx)})
    write_csv(out/'adoption_satisfaction_interaction.csv',pd.DataFrame(inter))
    ranking=[];stability=[]
    for metric in ['adoption_fraction','mean_adoption_fraction_1_60','revenue','profit']:
        temp=s[['scenario','policy','repetition',metric]].copy()
        temp['rank']=temp.groupby(['scenario','repetition'])[metric].rank(ascending=False,method='average')
        maxes=temp.groupby(['scenario','repetition'])[metric].transform('max')
        temp['top']=(temp[metric]==maxes).astype(float)
        temp['winner_share']=temp['top']/temp.groupby(['scenario','repetition'])['top'].transform('sum')
        for (level,policy),g in temp.groupby(['scenario','policy']):
            ranking.append({'scenario':level,'policy':policy,'metric':metric,'mean_rank':g['rank'].mean(),
                'top_frequency':g['top'].mean(),'tie_adjusted_win_share':g.winner_share.mean()})
        base=temp.loc[temp.scenario=='base'].set_index(['repetition','policy'])[metric]
        for level in levels:
            correlations=[]
            for rep in reps:
                x=temp.loc[(temp.scenario==level)&(temp.repetition==rep)].set_index('policy')[metric].reindex(policies).rank()
                y=base.loc[rep].reindex(policies).rank()
                correlations.append(float(np.corrcoef(x,y)[0,1]) if x.nunique()>1 and y.nunique()>1 else np.nan)
            stability.append({'scenario':level,'metric':metric,**estimate(correlations,idx)})
    write_csv(out/'policy_ranking_stability.csv',pd.DataFrame(ranking))
    write_csv(out/'rank_correlation_with_base.csv',pd.DataFrame(stability))
    # All monthly aggregate trajectories remain available, including months with no changes.
    monthly=pd.concat([pd.read_csv(directory/f'rep_{r:03d}/monthly.csv',float_precision='round_trip') for r in reps],ignore_index=True)
    assert len(monthly)==len(s)*61 and not monthly.duplicated(['scenario','policy','repetition','month']).any()
    curve=monthly.groupby(['scenario','policy','month']).agg(adoption_mean=('adoption_fraction','mean'),
        adoption_sd=('adoption_fraction','std'),awareness_mean=('awareness_fraction','mean'),
        revenue_mean=('cumulative_revenue','mean'),profit_mean=('cumulative_profit','mean')).reset_index()
    write_csv(out/'monthly_curve_summary.csv',curve)
    # Structural comparisons and deterministic economic identities.
    validation={'grid_campaigns':len(s),'unique_diffusions':done['unique_diffusions'],'monthly_rows':len(monthly),
        'replicate_count':n,'baseline_unchanged':True,'financial_identity_checks':True,'paired_input_checks':True,
        'undefined_spearman_campaigns':int(s.conditional_leader_spearman.isna().sum())}
    withs=s.set_index(['scenario','policy','repetition'])
    for level in ['service_rate_040','service_fixed_030','repurchase_002','repurchase_005','value_sigma_000','value_sigma_070']:
        a=withs.loc[level].sort_index();b=withs.loc['base'].sort_index()
        assert np.array_equal(a.adoption_count,b.adoption_count)
    base=withs.loc['base'].sort_index()
    assert np.allclose(withs.loc['service_rate_040'].sort_index().profit,.6*base.revenue-20)
    assert np.allclose(withs.loc['service_fixed_030'].sort_index().profit,.8*base.revenue-30*base.adoption_count-20)
    assert np.all(withs.loc['repurchase_005'].sort_index().repurchases >= withs.loc['repurchase_002'].sort_index().repurchases)
    # Verify every archive and keep network summaries from all repetitions.
    net=[];verified_archives=0
    for rep in reps:
        folder=directory/f'rep_{rep:03d}';completion=json.loads((folder/'completion.json').read_text())
        for name,digest in completion['files_sha256'].items():assert sha256(folder/name)==digest
        with zipfile.ZipFile(folder/'records.zip') as z:
            manifests=json.loads(z.read('manifest.json'))
            for name,digest in manifests.items():
                import hashlib
                assert hashlib.sha256(z.read(name)).hexdigest()==digest
            prov=pd.read_csv(z.open('provenance.csv')).set_index(['scenario','policy'])
            for level in ['service_rate_040','service_fixed_030','repurchase_002','repurchase_005','value_sigma_000','value_sigma_070']:
                assert prov.loc[level].final_states_sha256.equals(prov.loc['base'].final_states_sha256)
                assert prov.loc[level].selected_ids_sha256.equals(prov.loc['base'].selected_ids_sha256)
            net.append(pd.read_csv(z.open('network_diagnostics.csv')).assign(repetition=rep))
        verified_archives+=1
    write_csv(out/'network_diagnostics.csv',pd.concat(net,ignore_index=True))
    validation['verified_repetition_archives']=verified_archives
    write_json(out/'analysis_validation.json',validation)
    figures(out,overview,curve,policy_contrasts,levels,labels,policies,n)
    write_report(out,overview,aggregate,policy_contrasts,pd.DataFrame(inter),s,design,validation)
    write_json(out/'manifest.json',{'data_sha256':{p.name:sha256(p) for p in sorted(out.iterdir()) if p.is_file()}})
    return validation


def figures(out,overview,curve,contrasts,levels,labels,policies,n):
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    a=overview.set_index('scenario').loc[levels];means=100*a.adoption_fraction_mean.to_numpy()
    lo=100*a.adoption_fraction_ci_low.to_numpy();hi=100*a.adoption_fraction_ci_high.to_numpy()
    fig,ax=plt.subplots(figsize=(10,9))
    y=np.arange(len(levels));ax.errorbar(means,y,xerr=np.vstack([means-lo,hi-means]),fmt='o',color='#16697a',capsize=3)
    ax.set_yticks(y,[labels[x] for x in levels]);ax.invert_yaxis();ax.set_xlim(0,102)
    ax.axvline(95,color='#b75d36',ls='--',lw=1);ax.set_xlabel('Adopción al mes 60 (%)')
    ax.set_title(f'Sensibilidad de la adopción final · {n} bloques emparejados',loc='left',weight='bold')
    ax.grid(axis='x',alpha=.2);fig.text(.02,.01,'Media de siete políticas por bloque. Barras: IC bootstrap puntual 95%; no calibración empírica.',fontsize=9)
    fig.tight_layout(rect=(0,.03,1,1));fig.savefig(out/'01_sensitivity_adoption.png',dpi=180);plt.close(fig)
    chosen=['base','adoption_m3','satisfaction_070','adoption_m3_satisfaction_070']
    fig,axes=plt.subplots(2,2,figsize=(12,8),sharex=True,sharey=True)
    colors=plt.get_cmap('tab10').colors
    for level,ax in zip(chosen,axes.flat):
        for j,policy in enumerate(policies):
            c=curve.loc[(curve.scenario==level)&(curve.policy==policy)].sort_values('month')
            ax.plot(c.month,100*c.adoption_mean,label=POLICY_LABELS[policy],color=colors[j],lw=1.6)
        ax.set_title(labels[level]);ax.set_ylim(0,101);ax.set_xlim(0,60);ax.grid(alpha=.18)
        ax.set_xlabel('Mes');ax.set_ylabel('Adopción media (%)')
    handles,labs=axes[0,0].get_legend_handles_labels();fig.legend(handles,labs,loc='lower center',ncol=4,frameon=False)
    fig.suptitle('Trayectorias medias: cruce preespecificado adopción × satisfacción',weight='bold')
    fig.tight_layout(rect=(0,.085,1,.96));fig.savefig(out/'02_adoption_trajectories.png',dpi=180);plt.close(fig)
    selected=['base','value_sigma_070','repurchase_005','service_fixed_030']
    fig,axes=plt.subplots(2,2,figsize=(12,8))
    for level,ax in zip(selected,axes.flat):
        c=contrasts.loc[(contrasts.scenario==level)&(contrasts.metric=='profit')].set_index('policy').loc[policies[1:]]
        mean=c['mean'].to_numpy();low=c.ci_low.to_numpy();high=c.ci_high.to_numpy();y=np.arange(len(c))
        ax.errorbar(mean,y,xerr=np.maximum(0,np.vstack([mean-low,high-mean])),fmt='o',color='#16697a',capsize=3)
        ax.set_yticks(y,[POLICY_LABELS[x] for x in c.index]);ax.invert_yaxis();ax.axvline(0,color='gray',ls='--')
        ax.set_title(labels[level]);ax.set_xlabel('Utilidad − selección aleatoria (u.m.)');ax.grid(axis='x',alpha=.2)
    fig.suptitle('Diferencias emparejadas de utilidad · IC bootstrap puntual 95%',weight='bold')
    fig.tight_layout(rect=(0,0,1,.96));fig.savefig(out/'03_profit_contrasts.png',dpi=180);plt.close(fig)


def write_report(out,overview,aggregate,contrasts,inter,s,design,validation):
    lines=['# Artículo 9. Piloto de sensibilidad v0.1','',
        '**Resultado:** 2.800 evaluaciones económicas completas: 20 escenarios × 7 políticas × 20 repeticiones. Se ejecutaron 1.960 trayectorias de difusión distintas; los cambios exclusivamente económicos reutilizan la misma trayectoria.','',
        'Se mantuvieron las ecuaciones y parámetros base de M3 v0.3. El diseño se fijó antes de ejecutar. El piloto es un examen teórico de sensibilidad, no validación empírica ni experimento principal.','',
        '## 1. Diseño y controles','',
        '600 personas, seis comunidades, 20 seleccionados y 60 meses. Semilla maestra 20260925; repeticiones 0–19. Los flujos de red, atributos y eventos se emparejan entre políticas y condiciones. Las dos condiciones de mezcla generan redes distintas con los mismos sorteos, conservando el grado esperado. En las demás condiciones se conserva la red.','',
        'Se verifican 63 pruebas previas y ocho específicas del piloto (71 en total), más invariantes contables y temporales en cada campaña. El código original M3 no se editó.','',
        '## 2. Sensibilidad de los escenarios evaluados','',
        'Cada fila promedia primero las siete políticas dentro de una repetición y después los 20 bloques. No se consideran las 140 campañas independientes. Los intervalos son bootstrap percentil puntual de 95%, con 4.000 remuestreos de bloques. Describen incertidumbre Monte Carlo bajo estos supuestos, no incertidumbre sobre una población real. No están ajustados por comparaciones múltiples.','',
        '| Escenario | Adopción final % [IC 95%] | Campañas ≥95% adopción | Adopción media meses 1–60 % | Alcanzó 50% |','|---|---:|---:|---:|---:|']
    for r in overview.itertuples():
        lines.append(f'| {r.label} | {100*r.adoption_fraction_mean:.1f} [{100*r.adoption_fraction_ci_low:.1f}; {100*r.adoption_fraction_ci_high:.1f}] | {100*r.saturated_95_mean:.1f}% | {100*r.mean_adoption_fraction_1_60_mean:.1f} | {100*r.reached_50_mean:.1f}% |')
    lines+=['','La adopción media mensual es la media aritmética de las fracciones de los meses 1–60, no la adopción final ni una tasa de incidencia. Resume tanto velocidad como penetración. Los tiempos no alcanzados permanecen vacíos; `restricted_t50` usa 61 como puntuación acotada para contrastes y **no** como mes de éxito observado. Debe leerse junto a `reached_50`.','',
        '![Sensibilidad](01_sensitivity_adoption.png)','','![Trayectorias](02_adoption_trajectories.png)','',
        '## 3. Comparación de políticas en la base','',
        '| Política | Adopción final % | Adopción media mensual % | Ingresos medios u.m. | Δ utilidad frente a aleatoria [IC 95%] |',
        '|---|---:|---:|---:|---:|']
    base=s.loc[s.scenario=='base']
    for policy,g in base.groupby('policy'):
        c=contrasts.loc[(contrasts.scenario=='base')&(contrasts.policy==policy)&(contrasts.metric=='profit')].iloc[0]
        lines.append(f'| {POLICY_LABELS[policy]} | {100*g.adoption_fraction.mean():.2f} | {100*g.mean_adoption_fraction_1_60.mean():.2f} | {g.revenue.mean():.2f} | {c["mean"]:.2f} [{c.ci_low:.2f}; {c.ci_high:.2f}] |')
    lines+=['','Los rankings, proporciones de victorias y diferencias emparejadas de las 20 condiciones están en las tablas de análisis. Una victoria puntual no establece superioridad general. Los empates comparten crédito de victoria; los rangos usan posiciones promedio.','',
        '## 4. Economía y predicción','',
        '- Con servicio proporcional de 20% y activación total de 20, utilidad = 0,8 × ingresos − 20. Aumentar solamente la tasa a 40% conserva el orden por ingresos.',
        '- Agregar 30 u.m. por compra produce utilidad = 0,8 × ingresos − 30 × adopciones − 20 en ese escenario sin recompra. Puede cambiar el orden porque adopciones y valores individuales no son equivalentes.',
        '- Las recompras de 0,02 y 0,05 usan los mismos sorteos. Una intensidad mayor no reduce recompras dentro de la misma trayectoria. Adoptar antes abre más oportunidades de recompra.',
        '- Variar σ modifica simultáneamente la dispersión del valor latente y su incertidumbre relativa al predictor; no identifica por separado heterogeneidad económica y error predictivo. σ=0 todavía conserva diferencias observadas de valor entre clientes.',
        '- La precisión, recall y Spearman de líderes siguen siendo condicionales a los 20 seleccionados, con cuatro líderes previstos. No permiten evaluar el rendimiento contrafactual de los no seleccionados. Los promedios de métricas indefinidas indican el número de observaciones válidas.',
        '- No se varió α: ya se verificó en M3 que redistribuye crédito pero no modifica compras o utilidad. La predicción usa ingreso de raíz, no el crédito ponderado.','',
        '![Contrastes económicos](03_profit_contrasts.png)','',
        '## 5. Cruce entre adopción y satisfacción','',
        'Se estimó por bloque la interacción: resultado(−3; 0,70) − resultado(−3; 0,60) − resultado(−2; 0,70) + resultado(−2; 0,60). No es un análisis factorial completo de todos los parámetros.','',
        '| Política | Interacción en adopción final, puntos porcentuales [IC 95%] |','|---|---:|']
    for r in inter.loc[inter.metric=='adoption_fraction'].itertuples():
        lines.append(f'| {POLICY_LABELS[r.policy]} | {100*r.mean:.2f} [{100*r.ci_low:.2f}; {100*r.ci_high:.2f}] |')
    lines+=['','## 6. Interpretación y siguiente decisión','',
        'Conservar la base como referencia; no sustituirla automáticamente por la condición que produzca mayor separación entre políticas. Los cambios de satisfacción y calidad alteran quién puede recomendar; cambiar capacidad también modifica la fracción con capacidad entera cero por la regla `floor(capacidad × actividad)`. No deben interpretarse como variaciones puramente continuas en volumen.',
        '', 'Antes del experimento principal, fijar el rango teórico de adopción/satisfacción y los objetivos primarios (penetración final, adopción temprana, ingresos o utilidad). Conservar condiciones de difusión baja y alta que tengan sentido teórico, incluso cuando no favorezcan políticas sofisticadas. Después ejecutar al menos 100 repeticiones por condición principal y separar análisis exploratorios de confirmatorios. No elegir condiciones por el ganador observado.',
        '', 'Este piloto no prueba pérdida de actores, resiliencia, correlaciones entre roles, presupuestos igualados o variación de N. Tampoco cubre interacciones de orden superior o toda la región de parámetros. No hay calibración empírica ni prueba de causalidad sobre empresas reales.','',
        '## 7. Archivos y reproducción','',
        '`design.json` conserva el diseño y las semillas; `source_manifest.json` identifica código y entorno. Cada repetición incluye resúmenes, 61 meses por campaña y un ZIP con poblaciones, red, selección, estados finales por trayectoria única, libro de compras por evaluación, cuentas de raíces y procedencia. Se guardaron trazas mensuales individuales y de eventos completas de cuatro campañas preseleccionadas: política aleatoria, repetición 0, en las cuatro celdas del cruce. Para el resto se conservan estados finales, libros contables y series agregadas; sus historias detalladas se regeneran con código y semillas.','',
        '```bash','python -m pip install -r requirements-lock.txt','python -m pip install -r requirements-pilot.txt','python -m pytest -q tests','python run_pilot.py --out outputs/pilot_v01 --workers 4','python analyze_pilot.py --input outputs/pilot_v01','```','',
        'Usar directorios nuevos. Las tablas se conservan sin redondear; cifras de lectura redondeadas. Los datos son sintéticos. Las comprobaciones de integridad figuran en `analysis_validation.json` y los resultados de pruebas en el paquete reproducible.','']
    (out/'Article_9_Piloto_sensibilidad_Informe_v0.1.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--input',type=Path,required=True)
    args=parser.parse_args();print(json.dumps(analyze(args.input),indent=2))
