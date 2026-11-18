"""Paired 20-block analysis of the four 120-month trajectories."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from article9.export import write_csv, write_json, sha256
from pilot_metrics import estimate, interaction, paired_contrast, validate_grid
from horizon_metrics import CONDITIONS
from run_horizon120 import verify_bundle, read_csv

LABELS = {'base':'Base M3', 'adoption_m3':'Intercepto −3', 'satisfaction_070':'Satisfacción 0,70',
          'adoption_m3_satisfaction_070':'Intercepto −3 + satisfacción 0,70'}
POLICY_LABELS = {'random':'Aleatoria', 'hubs':'Hubs', 'influencers':'Influencers', 'opinion_leaders':'Líderes de opinión',
                 'predicted_revenue':'Ingresos previstos', 'community_diversified':'Diversificada', 'hybrid':'Híbrida'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    args = parser.parse_args()
    root = args.input.resolve()
    out = root / 'analysis'
    if out.exists() and any(out.iterdir()):
        parser.error('Use an absent or empty analysis directory')
    out.mkdir(exist_ok=True)
    design = json.loads((root / 'design.json').read_text())
    summary = read_csv(root / 'campaigns_all.csv')
    validate_grid(summary, CONDITIONS, design['policies'], design['repetitions'])
    periods, checks = [], []
    for rep in design['repetitions']:
        folder = root / f'rep_{rep:03d}'
        verify_bundle(folder)
        periods.append(read_csv(folder / 'monthly.csv'))
        checks.append(read_csv(folder / 'prefix_checks.csv'))
    monthly = pd.concat(periods, ignore_index=True)
    prefix = pd.concat(checks, ignore_index=True)
    assert len(monthly) == len(summary)*121
    assert not monthly.duplicated(['scenario','policy','repetition','month']).any()
    check_columns = ['population_bytes','selected_ids','monthly_prefix','state60_bytes','transactions_prefix']
    assert prefix[check_columns].eq(True).all().all() and len(prefix) == len(summary)
    assert prefix.full_trace_prefix_checked.sum() == 4
    indices = np.random.default_rng(design['bootstrap']['seed']).integers(0,20,(design['bootstrap']['draws'],20))
    # Do not average censored observed times, IDs, or the labels.
    excluded = {'scenario','policy','repetition','label','month_to_50pct_adoption','last_observed_adoption_month','absorption_month'}
    metrics = [c for c in summary.columns if c not in excluded]
    estimates = []
    for (scenario,policy), group in summary.groupby(['scenario','policy']):
        for metric in metrics:
            estimates.append({'scenario':scenario,'policy':policy,'metric':metric,
                **estimate(group.sort_values('repetition')[metric],indices)})
    estimates = pd.DataFrame(estimates)
    write_csv(out/'scenario_policy_estimates.csv',estimates)
    pooled = summary.groupby(['scenario','repetition'],as_index=False)[metrics].mean()
    overview = []
    for scenario,group in pooled.groupby('scenario'):
        for metric in metrics:
            overview.append({'scenario':scenario,'metric':metric,**estimate(group.sort_values('repetition')[metric],indices)})
    overview = pd.DataFrame(overview)
    write_csv(out/'overview_paired_blocks.csv',overview)
    contrasts = []
    for policy in design['policies']:
        for metric in ['adoption_fraction_60','adoption_fraction_120','adoption_fraction_gain_60_120',
            'mean_adoption_fraction_1_60','mean_adoption_fraction_61_120','profit_60','profit_120']:
            values = paired_contrast(summary,policy,'random',metric,key='policy')
            for scenario,group in values.groupby('scenario'):
                contrasts.append({'scenario':scenario,'policy':policy,'metric':metric,
                    **estimate(group.sort_values('repetition').difference,indices)})
    write_csv(out/'paired_policy_minus_random.csv',pd.DataFrame(contrasts))
    interactions = []
    for metric in ['adoption_fraction_60','adoption_fraction_120','adoption_fraction_gain_60_120','profit_60','profit_120']:
        values = interaction(summary,metric)
        for policy,group in values.groupby('policy'):
            interactions.append({'policy':policy,'metric':metric,**estimate(group.sort_values('repetition').difference,indices)})
        block = values.groupby('repetition').difference.mean().sort_index()
        interactions.append({'policy':'pooled_equal_policy_weight','metric':metric,**estimate(block,indices)})
    interactions = pd.DataFrame(interactions)
    write_csv(out/'interaction_by_horizon.csv',interactions)
    curves = []
    for (scenario,month),group in monthly.groupby(['scenario','month']):
        block = group.groupby('repetition')[['adoption_fraction','eligible_senders_next_month']].mean().sort_index()
        for metric in block:
            curves.append({'scenario':scenario,'month':month,'metric':metric,**estimate(block[metric],indices)})
    curves = pd.DataFrame(curves)
    write_csv(out/'monthly_curves_paired_blocks.csv',curves)
    ranks = []
    for (scenario,rep),group in summary.groupby(['scenario','repetition']):
        group = group.set_index('policy').reindex(design['policies'])
        for metric in ['adoption_fraction','profit']:
            a=group[f'{metric}_60'].rank(ascending=False,method='average')
            b=group[f'{metric}_120'].rank(ascending=False,method='average')
            corr=float(np.corrcoef(a,b)[0,1]) if a.nunique()>1 and b.nunique()>1 else None
            for policy in design['policies']:
                ranks.append({'scenario':scenario,'repetition':rep,'policy':policy,'metric':metric,
                    'rank_60':a[policy],'rank_120':b[policy],'rank_correlation_60_120':corr})
    write_csv(out/'policy_rankings_60_120.csv',pd.DataFrame(ranks))
    write_csv(out/'prefix_checks_all.csv',prefix)
    fig, axes = plt.subplots(1,2,figsize=(12,4.8),layout='constrained')
    colors = ['#315b92','#298575','#cb8533','#a14666']
    for scenario,color in zip(CONDITIONS,colors):
        for ax,metric in zip(axes,['adoption_fraction','eligible_senders_next_month']):
            data = curves.loc[(curves.scenario==scenario)&(curves.metric==metric)].sort_values('month')
            scale=100 if metric=='adoption_fraction' else 1
            ax.plot(data.month,data['mean']*scale,label=LABELS[scenario],color=color,lw=2)
            ax.fill_between(data.month,data.ci_low*scale,data.ci_high*scale,color=color,alpha=.12)
    for ax in axes:
        ax.axvline(60,color='#777777',ls='--',lw=1)
        ax.set_xlabel('Mes');ax.set_xlim(0,120);ax.grid(alpha=.18)
        ax.spines[['top','right']].set_visible(False)
    axes[0].set_ylabel('Adopción acumulada (%)');axes[0].set_ylim(0,102)
    axes[0].set_title('Penetración y velocidad');axes[1].set_title('Capacidad de difusión restante')
    axes[1].set_ylabel('Emisores elegibles para el mes siguiente')
    axes[1].set_ylim(bottom=0)
    axes[0].legend(fontsize=8,loc='lower right')
    fig.suptitle('Cuatro condiciones · 20 bloques emparejados · media de siete políticas',fontsize=12)
    fig.savefig(out/'trayectorias_120_meses.png',dpi=180)
    plt.close(fig)
    lookup=overview.set_index(['scenario','metric'])
    def stat(s,m,k='mean'):return float(lookup.loc[(s,m),k])
    rows=[]
    for s in CONDITIONS:
        g=summary.loc[summary.scenario==s]
        rows.append('| '+LABELS[s]+f" | {100*stat(s,'adoption_fraction_60'):.2f} | {100*stat(s,'adoption_fraction_120'):.2f} | {100*stat(s,'adoption_fraction_gain_60_120'):.2f} [{100*stat(s,'adoption_fraction_gain_60_120','ci_low'):.2f}; {100*stat(s,'adoption_fraction_gain_60_120','ci_high'):.2f}] | {int(g.ongoing_120.sum())}/140 | {100*stat(s,'adoption_fraction_gain_108_120'):.2f} |")
    interaction_pool=interactions.loc[interactions.policy=='pooled_equal_policy_weight'].set_index('metric')
    lines=[
        '# Artículo 9. Comprobación de las cuatro condiciones hasta 120 meses', '',
        '## Resultado', '',
        'Se ejecutaron 560 campañas: cuatro condiciones × siete políticas × 20 repeticiones emparejadas. Las 560 reprodujeron exactamente las series mensuales, los estados individuales y las compras de los primeros 60 meses del piloto. Se conservaron las ecuaciones de M3 y sus costos base, sin recompra.', '',
        '| Condición | Adopción mes 60 % | Adopción mes 120 % | Ganancia pp [IC 95%] | Campañas aún con emisores | Ganancia meses 109–120 pp |',
        '|---|---:|---:|---:|---:|---:|', *rows, '',
        'Las medias dan igual peso a las siete políticas dentro de cada repetición. Los intervalos de la ganancia son bootstrap percentil de 95%, con 4.000 remuestreos de los 20 bloques completos; no se tratan las 140 campañas de cada condición como observaciones independientes. Son intervalos puntuales exploratorios, sin ajuste por multiplicidad ni calibración empírica.', '',
        '![Trayectorias hasta 120 meses](trayectorias_120_meses.png)', '',
        '## Cómo interpretar el agotamiento', '',
        'Una campaña se clasifica como absorbida cuando, después de la evaluación inicial, no quedan emisores elegibles para el siguiente mes. Con red, atributos y reglas fijos, sin nuevas semillas ni adopciones espontáneas, no puede reiniciarse. El mes cero se excluye porque todavía está programada la evaluación de las semillas. Un mes sin mensajes o sin nuevas compras no demuestra agotamiento.', '',
        'La saturación (≥95% de adopción) es distinta de la absorción. Una campaña saturada todavía puede crecer; una campaña absorbida puede terminar con baja penetración. Las campañas con emisores al mes 120 no tienen una meseta definitiva demostrada.', '',
        '## Diagnóstico por condición', '']
    for s in CONDITIONS:
        g=summary.loc[summary.scenario==s]
        lines.append(f"- {LABELS[s]}: {int(g.positive_growth_60_120.sum())}/140 campañas aumentaron adopción después del mes 60; {int(g.positive_growth_109_120.sum())}/140 tuvieron adopciones en los últimos 12 meses. Campañas absorbidas: {int(g.absorbed_60.sum())} al mes 60 y {int(g.absorbed_120.sum())} al mes 120. Emisores elegibles medios: {stat(s,'eligible_senders_next_month_60'):.2f} → {stat(s,'eligible_senders_next_month_120'):.2f}. Campañas con ≥95% de adopción al mes 120: {int(g.saturated_95_120.sum())}/140.")
    lines += ['', '## Interacción y políticas', '',
        'Se mantiene el cruce 2×2: combinación − intercepto − satisfacción + base. La interacción media en adopción es:', '',
        '| Horizonte | Interacción pp [IC 95%] |', '|---|---:|']
    for m in [60,120]:
        r=interaction_pool.loc[f'adoption_fraction_{m}']
        lines.append(f"| Mes {m} | {100*r['mean']:.2f} [{100*r.ci_low:.2f}; {100*r.ci_high:.2f}] |")
    lines += ['',
        'Las tablas desagregan las siete políticas, sus contrastes emparejados frente a selección aleatoria y sus rankings a 60 y 120 meses. Las posiciones pueden cambiar con el horizonte; no se elige una condición por favorecer a una política. Los resultados primarios de esta comprobación son penetración, crecimiento adicional y agotamiento, no una búsqueda de un ganador.', '',
        '## Economía y tiempos', '',
        'No se añadió recompra: cada nueva adopción produce una compra inicial. Se conserva servicio proporcional 20%, costo fijo de servicio cero y activación total de 20 u.m. Por tanto, utilidad acumulada = 0,8 × ingresos acumulados − 20, y la ganancia de utilidad entre meses 60 y 120 = 0,8 × la ganancia de ingresos. Las unidades monetarias son abstractas; el mes 61 no activa una nueva campaña ni un nuevo costo.', '',
        'Las medias de adopción 1–60, 61–120 y 1–120 se guardan con nombres distintos. Los meses de llegada al 50% no alcanzados permanecen vacíos y se acompañan de indicadores de alcance. No se reemplaza censura por un mes observado ficticio.', '',
        '## Diseño, verificación y reproducción', '',
        'N=600, seis comunidades, 20 seleccionados; semilla maestra 20260925 y repeticiones 0–19, iguales al piloto. Solo se extiende `DiffusionConfig.horizon_months` de 60 a 120. La red, atributos, selección y campos aleatorios se mantienen. El campo aleatorio se indexa por evento, mes y actor, sin depender del horizonte.', '',
        'En las 560 campañas se verificaron: población y red idénticas, seleccionados idénticos, series mensuales completas 0–60 idénticas, estados individuales del mes 60 idénticos incluso por huella de bytes, y libro de compras 0–60 idéntico. En las cuatro campañas preseleccionadas (repetición 0, política aleatoria) también coinciden todas las historias individuales, mensajes, evaluaciones y registros de emisores del prefijo 0–60.', '',
        'Las comprobaciones adicionales incluyen una compra inicial por adoptante, ausencia de duplicados, contabilidad conservativa, consistencia temporal, rejilla completa, 67.760 filas mensuales y hashes de los 20 archivos de repetición. Las pruebas automatizadas se entregan en el paquete de código; `analysis_validation.json` documenta la validación de los datos.', '',
        'Cada repetición conserva resúmenes, 121 meses por campaña, comprobaciones del prefijo y un ZIP con población, red, selección, estados a 60 y 120, compras y cuentas de raíces. Las cuatro campañas de muestra conservan trazas individuales y de eventos completas hasta 120. El resto de historias se regenera con el código y las semillas. Las referencias de 60 meses proceden del piloto v0.1, sin modificarlo.', '',
        '```bash',
        'python -m pip install -r requirements-lock.txt',
        'python -m pip install -r requirements-pilot.txt',
        'python -m pytest -q tests',
        'python run_horizon120.py --reference /ruta/Article_9_Piloto_Datos_v0.1 --out outputs/horizon120 --workers 4',
        'python analyze_horizon120.py --input outputs/horizon120',
        '```', '',
        'Usar directorios nuevos. Las cinco partes de datos del piloto previo deben extraerse en un mismo directorio antes de reproducir las comprobaciones contra 60 meses. Esta extensión no sustituye el experimento principal de ≥100 repeticiones por condición. El horizonte de 120 meses es un diagnóstico de diez años bajo supuestos estáticos, no una predicción realista de mercado a diez años.', '']
    (out/'Article_9_Horizonte_120_Informe_v0.1.md').write_text('\n'.join(lines),encoding='utf-8')
    validation={'status':'passed','campaigns':len(summary),'monthly_rows':len(monthly),'repetition_archives_verified':20,
        'campaign_prefix_checks_passed':len(prefix),'full_trace_prefix_checks_passed':4,
        'bootstrap_blocks':20,'bootstrap_draws':4000,'unit':'paired_repetition_with_equal_policy_weights'}
    write_json(out/'analysis_validation.json',validation)
    write_json(out/'manifest.json',{p.name:sha256(p) for p in sorted(out.iterdir()) if p.is_file()})
    print(json.dumps(validation))
    print('\n'.join(rows))


if __name__=='__main__':main()
