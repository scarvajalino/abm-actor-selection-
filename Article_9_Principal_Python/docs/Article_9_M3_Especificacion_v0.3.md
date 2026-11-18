# Artículo 9. M3: economía y liderazgo realizado

Versión 0.3.0. Python. Complementa M1 v0.1 y M2 v0.2.

## 1. Propósito y alcance

M3 operacionaliza las secciones 49–51 de la guía adjunta *Indications – Article 9 – NM – Strategic Actors*: compras, recompra, costos, utilidad, atribución y evaluación del liderazgo previsto. Las alternativas de la guía se convierten aquí en supuestos explícitos, sin calibración empírica. Las cantidades monetarias son **unidades monetarias abstractas (u.m.)**, no precios observados ni proyecciones financieras.

La red, selección, adopción, satisfacción y WOM mantienen las reglas y parámetros de M1/M2. M3 valora la trayectoria terminada de M2 sin retroalimentar la difusión. Los valores latentes se consultan después de la selección. Se conserva el diagnóstico de saturación de M2.

## 2. Entradas y programación

```python
result = account_campaign(population, selection, diffusion, model_config, economic_config)
```

| Entrada | Uso |
|---|---|
| `population.nodes` | Costos, valor previsto de compra, índice de liderazgo y desempate ex ante |
| `population.latent` | Valor monetario individual, generado en M1 y oculto a la selección |
| `selection` | Seleccionados y política |
| `diffusion.final_states` | Adopción, mes, satisfacción, padre inmediato y raíz |
| `diffusion.periods` | Horizonte efectivo de M2: meses 0 a H |
| Semilla maestra y repetición | Sorteos económicos reproducibles |
| `EconomicConfig` | Supuestos económicos |

Secuencia:

1. Mes 0: pagar el costo de cada seleccionado.
2. Mes de adopción: registrar una compra inicial, incluso si la experiencia posterior es insatisfactoria.
3. Desde el mes siguiente a adoptar hasta H inclusive: evaluar recompra si está habilitada.
4. Atribuir cada transacción en vistas separadas y calcular créditos ponderados.
5. Agregar por mes, actor, raíz y empresa; evaluar rankings al final.

La identidad `m{mes}_a{actor}_{tipo}` es única dentro de una campaña. Al concatenar campañas, la clave completa incluye también repetición y política. Se validan filas únicas, identidades de campaña, valores finitos y linajes con padres vecinos que adoptaron antes que sus hijos. No se modifican las tablas de entrada.

## 3. Parámetros base

| Parámetro | Valor | Interpretación |
|---|---:|---|
| `activation_cost` de M1 | 1 u.m. | Costo por seleccionado |
| `service_cost_rate` | 0,20 | Costo proporcional sobre cada compra |
| `service_cost_fixed` | 0 | Costo adicional por transacción |
| `repurchase_probability` | 0 | Intensidad mensual base; cero desactiva recompra |
| `repurchase_value_factor` | 1 | Multiplicador del valor latente en recompras |
| `attribution_alpha` | 1 | Fracción del crédito para la raíz; resto para el padre |
| `leader_fraction` | 0,20 | Fracción superior del universo seleccionado |

Todos los parámetros deben ser finitos. Costos no negativos; tasa, probabilidad y α en [0,1]; fracción de líderes en (0,1]; factor de recompra positivo. Se permiten pérdidas sin recortarlas a cero. El costo de servicio de 20% es ilustrativo y debe examinarse en sensibilidad.

M1 genera costos de activación uniformes y positivos. M3 admite costos individuales no negativos en la tabla, pero esto no implementa por sí solo una comparación con presupuestos igualados o costos según tipo de actor.

## 4. Compras

### Compra inicial

Se reutiliza el mecanismo de M1:

\[
\widehat V_i=50+150P_i,\qquad V_i=\widehat V_i\exp(\sigma Z_i-\sigma^2/2),\quad\sigma=0,35.
\]

`P_i` es el potencial observado; `Z_i` procede del flujo latente de M1. M3 no vuelve a sortear el valor. Cada adoptante compra una vez al adoptar por `V_i`; un no adoptante no compra. Más exposiciones o rutas WOM no crean compras iniciales adicionales. Una experiencia insatisfactoria no anula la compra ya realizada. No hay devoluciones.

### Recompra opcional

Con intensidad ρ>0, cada adoptante satisfecho evalúa una oportunidad mensual desde el mes posterior a adoptar:

\[
p_{i,t}^{rep}=\rho s_i,\qquad compra_{i,t}^{rep}=\mathbb{1}(u_{i,t}<p_{i,t}^{rep}),\qquad ingreso_{i,t}^{rep}=V_i f_{rep}.
\]

Se exige `satisfied=True` en M2. Los insatisfechos tienen probabilidad cero. Satisfacción y valor permanecen constantes. Fallar un sorteo no impide evaluar el siguiente mes. Hay como máximo una recompra por cliente y mes, ninguna en el mes de adopción ni después de H.

No se representan abandono, inventario, presupuesto individual, inflación o descuento. Un adoptante temprano tiene más oportunidades de recompra, diferencia temporal que forma parte del mecanismo cuando se habilita. `repurchase_trials.csv` registra elegibilidad, probabilidad, sorteo, resultado y motivo. Con ρ=0 conserva solo los encabezados.

## 5. Costos y utilidad

Para una compra de ingreso r:

\[
c_{serv}=c_{fijo}+\tau r,\qquad margen=r-c_{serv}.
\]

Para la campaña:

\[
Ingresos=\sum compras\ iniciales+\sum recompras,
\]

\[
Utilidad=Ingresos-\sum costos\ de\ servicio-\sum_{i\in S}c_i^{act}.
\]

La activación se cobra en mes 0 a todos los seleccionados, incluso si rechazan o adoptan luego por otra raíz. Los no seleccionados no pagan activación. Servicio se cobra únicamente cuando hay compra. No se incluyen costos de mensajes, costos corporativos o impuestos.

Con 20 seleccionados, recompra desactivada, servicio de 20% y activación de 1 u.m., `utilidad = 0,8 × ingresos − 20`. El ranking de utilidad coincide necesariamente con el de ingresos. Investigar una divergencia exige otros supuestos especificados antes del experimento; no se cambian para forzarla.

Los cálculos usan punto flotante, sin redondeo de cada compra a centavos. `math.fsum` se emplea en agregaciones; la conservación se verifica con tolerancia numérica. El redondeo en informes no altera CSV/JSON.

## 6. Atribución sin doble conteo

El libro de transacciones es la fuente única de ingresos. Las siguientes son **vistas alternativas del mismo dinero**; no se suman entre sí:

| Vista | Dueño de una transacción | Conservación |
|---|---|---|
| `own_*` | Comprador | Suma sobre toda la población = total de empresa |
| `immediate_*` | Padre; comprador si fue adquisición directa como semilla | Suma sobre toda la población = total |
| `root_*` | Raíz heredada de M2 | Suma sobre seleccionados = total |
| `attributed_*` | Reparto entre padre y raíz | Suma sobre toda la población = total |

Los sufijos son `revenue`, `service_cost` y `profit`. En cada vista el costo de activación permanece en el seleccionado que lo ocasionó; también se conserva la utilidad al sumar el universo completo correspondiente. Si α<1, puede haber crédito ponderado de recomendadores no seleccionados: sumar solo seleccionados no reproduce el total de esa vista.

Por transacción se asigna `(1−α) × ingreso` al padre inmediato y `α × ingreso` a la raíz. Si coinciden, se fusionan en un crédito de peso 1. Para adquisición directa de semilla, el dueño inmediato es la propia semilla. Los costos de servicio se reparten con los mismos pesos. `attribution_credits.csv` conserva pesos e importes por transacción.

Es una operacionalización conservativa del parámetro de atribución sugerido por la guía. No suma de forma superpuesta ingreso propio, directo e indirecto entre actores. `direct_referral_revenue` es un diagnóstico descriptivo de compras de hijos inmediatos, incluidas recompras; no es ingreso extra de la empresa.

La recompra conserva padre y raíz de la adquisición. Si un seleccionado rechaza y después adopta por WOM, su compra y descendencia pertenecen a la raíz heredada. Su propia fila como raíz puede permanecer en cero y conservar su costo de activación.

α solo cambia el crédito ponderado; no cambia compras o ingresos de empresa. El ranking predictivo base usa `root_revenue` y tampoco cambia con α. Evaluar liderazgo de recomendadores intermedios exigiría otro resultado y universo explícitos. Toda atribución es contable, no efecto causal incremental ni resultado contrafactual de retirar un actor.

## 7. Evaluación predictiva

El universo es **S, los seleccionados de esa campaña**: tuvieron oportunidad de activación. No se interpreta la ausencia de selección de los demás como fracaso observado. Las políticas seleccionan carteras distintas; sus métricas son condicionales a esas carteras, no una comparación de clasificadores sobre un mismo conjunto de prueba.

El predictor es `predicted_revenue_score`, índice ex ante de M1 entre 0 y 1. El resultado es `root_revenue`, que incluye compras de raíz y cascada. Se define `q = ceil(leader_fraction × |S|)`; con 20 seleccionados y 0,20, q=4.

1. Líderes previstos: q mayores índices; empate por `tie_rank` ex ante y después identificador.
2. Líderes realizados: q mayores ingresos positivos de raíz, incluyendo todos los empates positivos exactos en la frontera. Si hay menos de q positivos, solo esos. Sin ingresos positivos, no hay líderes realizados.
3. Calcular intersección, falsos positivos, falsos negativos, precisión y recall. Denominadores cero producen `null`.
4. Spearman usa correlación de rangos promedio. Es `null` con menos de dos actores o con un ranking constante; se exporta el motivo.
5. MAE de rango: promedio de las diferencias absolutas entre rangos promedio. La versión normalizada divide por `|S|−1` y es `null` para cero o un actor.

\[
precision=|P\cap R|/|P|,\qquad recall=|P\cap R|/|R|.
\]

Sin empates de frontera y con suficientes raíces positivas, ambos conjuntos tienen q miembros y precisión=recall. Empates o pocas raíces positivas pueden hacerlas diferir. Un ranking constante puede tener MAE de rango aunque Spearman no esté definido; debe leerse junto al estado de la correlación.

Estas medidas no estiman precisión/recall de elegir 20 entre 600 para encontrar las mejores raíces contrafactuales. Esa pregunta necesita oportunidades de activación comparables para los candidatos. Tampoco constituyen validación fuera de muestra o evidencia robusta con tres repeticiones.

### Error monetario separado

`purchase_value_mae_among_adopters` es la media de `abs(predicted_purchase_value − compra inicial)` entre adoptantes. Ambas variables están en u.m. No incluye recompras ni no compradores, y no es error de predicción de cascadas. `monetary_error_of_leadership_index` es `null`: restar un índice de liderazgo a dinero mezclaría escalas.

## 8. Aleatoriedad

M3 usa una clave ASCII independiente:

```text
Article9-M3-v1|master_seed|repetition|500|month|actor_id
```

BLAKE2b de 8 bytes, 53 bits altos divididos por 2^53: sorteo en [0,1). Política, α e intensidad no entran en la clave, permitiendo reutilizar sorteos entre escenarios comparables. El orden de ejecución no consume ni desplaza números aleatorios. Semilla maestra: 20260925.

No se cambian flujos de M1 o M2. Costos, recompra y α no alteran adopción, satisfacción o WOM. Los escenarios suplementarios usan repetición 0, dos políticas, ρ=0,05 y α=0, 0,5 y 1; no se mezclan con los promedios de los 21 escenarios base.

## 9. Salidas

Cada carpeta económica contiene 13 archivos:

| Archivo | Contenido |
|---|---|
| `config.json` | Parámetros, semilla, identidad, referencias M1/M2 y hashes de entradas |
| `transactions.csv` | Cliente, mes, tipo, linaje, dueño inmediato, ingreso, servicio y margen |
| `activation_costs.csv` | Seleccionado, mes 0 y costo |
| `repurchase_trials.csv` | Oportunidades y decisiones de recompra |
| `attribution_credits.csv` | Pesos e importes conservativos por transacción |
| `actor_accounts.csv` | Cuatro vistas contables de todas las personas |
| `seed_accounts.csv` | Seleccionados, incluidas raíces sin ingresos |
| `periods.csv` | Compras, ingresos, costos, utilidad por mes y acumulados |
| `prediction_ranking.csv` | Índice, rangos, líderes y error de rango en S |
| `prediction_metrics.json` | Métricas, universo, frontera y convenciones |
| `summary.json` y `summary.csv` | Resumen M2 y totales M3 |
| `manifest.json` | Versiones, entorno y hashes de código/datos |

Se retienen meses 0..H aunque no haya ventas. `profit` mensual cobra activación solo en mes 0; `cumulative_profit` conserva ese costo. Los CSV incluyen política y repetición. No definidos: vacío en CSV y `null` en JSON.

Los hashes identifican atributos ex ante, valores latentes, estados finales, eventos WOM y seleccionados usados. Referencias relativas ubican entradas en el paquete. No se sobrescriben carpetas no vacías.

## 10. Verificación y reproducción

Se preservan 19 pruebas M1 y 22 M2. V01–V22 comprueban parámetros, contabilidad manual, rechazo, adopción posterior de seleccionados, α, recompra, satisfacción, pérdidas, universos vacíos, reproducibilidad, ausencia de mutación, valores latentes, predicción, empates, entradas corruptas, exposición simultánea, exportación, costos individuales, horizonte y campañas integradas.

```bash
python -m pip install -r requirements-lock.txt
python scripts/verify_m3.py --out outputs/m3_verification
python run_m3.py --m1-config config_base.json --m2-config m2_config_base.json --m3-config m3_config_base.json --repetitions 3 --out outputs/m3_campaigns
```

El verificador conserva 21 campañas base y seis escenarios suplementarios. Exporta las 21 trayectorias M2 una sola vez y las referencia desde M3. El ejecutor independiente guarda, por repetición, `population/` y `<politica>/m2/`, `<politica>/m3/`. Las configuraciones simples de ejecución son distintas del archivo consolidado de configuración y semillas del informe.

## 11. Límites y siguiente paso

Sin compras antes de adoptar, pruebas gratuitas, devoluciones, abandono, costos de contacto, costos corporativos, descuento o respuesta de difusión a precios/recompra. Las cascadas se observan bajo competencia entre semillas; no son efectos marginales aislados.

La configuración M2 alcanzó 589–598 adoptantes de 600. Saturación y relación lineal entre utilidad e ingresos limitan la discriminación final. No se ajustaron parámetros para obtener ganadores.

Sigue un **piloto de sensibilidad**: tiempos y curvas, variación entre repeticiones, reglas de adopción/satisfacción, actividad, heterogeneidad de valor y supuestos de costo/recompra. Después se fijarán condiciones del experimento principal, con al menos 100 repeticiones por condición según la guía. Resiliencia y evaluación contrafactual de líderes necesitan diseños posteriores explícitos.
