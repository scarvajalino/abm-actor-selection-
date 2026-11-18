# Artículo 9 Diccionario de datos del experimento principal

Los datos son sintéticos. Cada campaña combina una condición (`scenario`), una política (`policy`) y una repetición (`repetition`). Esa clave identifica una campaña dentro de un bloque emparejado; las campañas que comparten repetición **no** son independientes para los contrastes. Los identificadores de actores y poblaciones son locales a cada repetición.

## Organización de los archivos

| Archivo | Unidad de fila o contenido |
|---|---|
| `design.json` | Matriz, configuraciones, semillas, métricas y reglas de análisis fijadas |
| `source_manifest.json` | Código y entorno al comenzar la ejecución |
| `campaigns_all.csv` | Una fila por campaña, 5.600 en total |
| `rep_XXX/campaigns.csv` | Las 56 campañas de una repetición |
| `rep_XXX/monthly.csv` | Una fila por campaña y mes, meses 0–120 |
| `rep_XXX/completion.json` | Comprobaciones y hashes de los tres archivos del bloque |
| `rep_XXX/records.zip` | Poblaciones, selecciones, estados, compras, atribución y diagnósticos |

Las partes de datos se extraen en el mismo directorio. Todas comparten la raíz `Article_9_Principal_Datos_v1.0/`; la parte 01 incluye los archivos globales. Ninguna parte sobrescribe otra repetición.

## Resultados principales

| Campo | Definición | Unidad |
|---|---|---|
| `mean_awareness_fraction_1_60` | Media de conocimiento acumulado en meses 1–60 | Fracción 0–1 |
| `mean_adoption_fraction_1_60` | Media de adopción acumulada en meses 1–60 | Fracción 0–1 |
| `revenue_60` | Compras acumuladas hasta el mes 60 | u.m. abstractas |

Las medias temporales incluyen exactamente 60 observaciones y excluyen mes 0. No son incidencia mensual. Los resultados del mes 120 son sensibilidad, no sustituyen el horizonte principal.

## Convenciones de nombres y resultados complementarios

- Sufijos `_60`, `_90`, `_120`: resultado disponible en ese horizonte.
- `_gain_60_120`: valor al 120 menos valor al 60. En fracciones, multiplicar por 100 para puntos porcentuales.
- `_gain_108_120` y `new_adoptions_109_120`: crecimiento observado en los últimos 12 meses.
- `adoption_fraction`: adoptantes / 600; `awareness_fraction`: personas informadas / 600.
- `mean_*_61_120`: media de los 60 meses 61–120, comparable en longitud con 1–60.
- `eligible_senders_next_month`: actores con adopción, satisfacción, capacidad y audiencia disponibles para enviar WOM el mes siguiente.
- `absorbed`: indicador de cero emisores elegibles después de la evaluación inicial. `ongoing_120`: su complemento al mes 120.
- `saturated_95`: indicador de adopción ≥95%; no equivale a absorción.
- `month_to_*`: primer mes observado de llegada a un umbral. Vacío significa que no se alcanzó; no se codifica como un mes de éxito.
- `last_observed_adoption_month`: última adopción observada hasta 120; no garantiza que no habrá posteriores.
- `wom_messages_cumulative`: todos los mensajes; `wom_unique_reach`: receptores distintos; `wom_redundancy`: fracción de exposiciones repetidas.
- `conversion_per_unique_wom_reach`: adopciones atribuidas a WOM / receptores distintos de WOM; `conversion_per_wom_message`: mismo numerador / mensajes totales. Vacío si denominador cero. Excluye adopciones directas de semillas del numerador.
- `top_seed_revenue_share`: fracción del ingreso de la mayor raíz; `root_revenue_gini`: concentración entre las 20 raíces, incluidos ceros. Son diagnósticos de concentración, no pruebas de resiliencia.
- `conditional_leader_*`: métricas del ranking entre los 20 seleccionados de esa campaña; no clasifican a los 600 candidatos. Valores indefinidos permanecen vacíos.
- `profit`: ingreso menos servicio y activación. En este experimento equivale a 0,8 × ingreso − 20 acumulado; no hay recompra.

## Dentro de cada archivo de repetición

`populations/pXX/` contiene `nodes_ex_ante.csv`, `latent_values.csv` y `edges.csv`. El índice de población se vincula a cada campaña mediante `provenance.csv`. La tabla latente no entra en la selección. La red cambia solamente en las condiciones de mezcla.

`selections.csv`, `policy_diagnostics.csv`, `policy_overlap.csv`, `attribute_correlations.csv` y `network_diagnostics.csv` describen los actores seleccionados, las audiencias y las redes. Las correlaciones observadas no implican que se haya realizado un experimento de correlación controlada.

`campaigns/<scenario>/<policy>/` contiene:

- Estados individuales a 60 y 120: selección, conocimiento, adopción, satisfacción, elegibilidad WOM, meses y linaje.
- `transactions.csv`: una compra inicial por adoptante; claves de transacción únicas dentro de la campaña. Para concatenar usar además condición, política y repetición.
- Cuentas de raíces y rankings predictivos separados a 60/120. Los rankings de 60 no utilizan resultados posteriores.
- Cascadas por raíz a 60/120: tamaño, profundidad, comunidades, mensajes y emisores elegibles. La atribución no equivale al efecto contrafactual de retirar esa raíz.

`communities.csv` tiene una fila por campaña, comunidad y horizonte; incluye adoptantes, informados y primer mes de adopción, vacío si no ocurrió.

Las trazas completas en `full_trace_sample/` corresponden exclusivamente a repetición 20, política aleatoria, ocho condiciones. Para otras campañas, los estados intermedios y eventos se regeneran con el código. No deben confundirse los archivos conservados de todas las campañas con la muestra de historias completas.

## Tablas del análisis

- `scenario_policy_estimates.csv`: resultados por condición y política, con número válido, media, dispersión, error Monte Carlo e intervalos puntuales.
- `paired_policy_minus_random.csv`: diferencias por repetición frente a selección aleatoria; secundarios sin ajuste por multiplicidad.
- `primary_simultaneous_contrasts.csv`: los 144 contrastes primarios con bandas simultáneas aproximadas, manteniendo el remuestreo conjunto de bloques.
- `paired_scenario_minus_base.csv`: variaciones respecto a la base por política.
- `policy_by_condition_interactions.csv`: cambio del contraste política–aleatoria entre una condición y la base; intervalos puntuales.
- `adoption_satisfaction_interaction.csv`: combinación − adopción − satisfacción + base, por política.
- `overview_paired_blocks.csv`: promedio previo de siete políticas dentro de cada repetición.
- `monthly_pooled_curves.csv`: curvas con incertidumbre entre bloques; `monthly_policy_mean_curves.csv`: curvas medias de cada política.
- `descriptive_decision_map.csv`: política con mayor media observada por objetivo y condición, sin declarar superioridad única.
- `replication_precision_diagnostics.csv`: comparación descriptiva de dos mitades de 50 bloques, sin exclusiones ni parada adaptativa.

Los intervalos y errores describen incertidumbre Monte Carlo del modelo. No constituyen intervalos de predicción sobre mercados reales. Las tablas conservan precisión numérica; solo el informe redondea.
