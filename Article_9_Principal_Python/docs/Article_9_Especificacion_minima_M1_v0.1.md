# Artículo 9 Especificación mínima de red atributos y selección

**Versión:** 0.1  
**Fecha:** 25 de septiembre de 2026  
**Proyecto:** Reach, Credibility, or Revenue? An Agent-Based Model of Strategic Actor Selection in Entrepreneurial Word of Mouth  
**Responsable operativo:** Santiago, con orientación y revisión de los profesores.  
**Implementación acordada:** Python.  
**Estado:** especificación propuesta para implementar y verificar el módulo M1; todavía no contiene código ejecutado ni resultados de simulación.

## 1 Propósito y alcance

Este documento define el primer módulo del modelo del Artículo 9. M1 generará una red social sintética, asignará atributos a sus integrantes y aplicará siete políticas para seleccionar actores iniciales de una campaña. Su propósito es entregar una población reproducible y selecciones verificables sobre las cuales incorporar posteriormente la adopción, la comunicación boca a boca y los ingresos.

La pregunta operativa de M1 es: **¿qué personas selecciona cada política cuando la estructura de la red, la actividad comunicativa, la credibilidad, la experiencia y el potencial económico pueden diferir?** M1 permite estudiar las diferencias entre selecciones y sus oportunidades estructurales. Para comparar resultados comerciales se necesitará el módulo de difusión.

El modelo es un ejercicio teórico y computacional sin calibración con empresas, campañas, encuestas ni transacciones reales. Las distribuciones, parámetros y ponderaciones de esta versión son supuestos ilustrativos, modificables y sujetos a sensibilidad. Ninguna regla debe programarse para garantizar que una política gane.

Esta especificación operacionaliza las secciones de red, atributos y selección de la guía adjunta. Por instrucción del profesor, **Python sustituye a NetLogo**. El protocolo ODD se conserva como forma de documentar el modelo; los experimentos se ejecutarán mediante scripts y archivos de configuración de Python, en lugar de BehaviorSpace.

### Incluido en M1

- Generación de la red y asignación de comunidades.
- Atributos continuos, información observable antes de la campaña y valor económico latente.
- Puntajes y siete políticas de selección con igual número de actores y costo unitario.
- Medidas estructurales, solapamiento entre selecciones y auditoría de decisiones.
- Exportación de insumos y definición de pruebas de verificación.

### Etapas posteriores

La evaluación del producto, adopción, satisfacción, envío de mensajes, cascadas, compras, recompras, ingresos, utilidad y pérdida de actores se implementarán después. M1 no calculará ingresos realizados, precisión predictiva comercial ni resiliencia. El horizonte de 60 meses se reserva para el ABM completo y no supone ejecutar 60 pasos vacíos en M1.

## 2 Configuración inicial

| Elemento | Valor de partida | Interpretación |
|---|---:|---|
| Personas `n_agents` | 600 | Universo de posibles actores y clientes |
| Comunidades `n_communities` | 6 | Grupos de 100 personas |
| Grado medio esperado `mean_degree` | 12 | Objetivo en esperanza, no grado idéntico para todos |
| Fracción externa esperada `mixing_fraction` | 0.20 | Proporción esperada de vínculos fuera de la comunidad |
| Actores seleccionados `k` | 20 | Cantidad exacta y sin duplicados por política |
| Políticas | 7 | Aleatoria, hubs, actividad, opinión, ingresos previstos, diversificada e híbrida |
| Costo por actor `activation_cost` | 1 | Unidad abstracta de recurso; costo total de selección igual a 20 |
| Distribución de atributos base | Beta(2, 2) | Valores entre 0 y 1; heterogeneidad ilustrativa |
| Ruido del valor económico `value_noise_sigma` | 0.35 | Diferencia entre estimación previa y valor latente |
| Horizonte futuro `horizon_months` | 60 | Aplicable al módulo posterior de difusión |
| Repeticiones futuras por política | 100 como mínimo | Plan base de la guía, posterior a verificación y piloto |

Para M1 se permiten configuraciones pequeñas destinadas a pruebas. Se exige que `n_agents` sea divisible por `n_communities`, que existan al menos dos comunidades y que cada comunidad tenga al menos dos integrantes. Una configuración fuera de estos límites se rechaza con un mensaje explícito; no se redondean tamaños silenciosamente. La selección admite `0 <= k <= n_agents`; el caso `k = 0` se usa como control.

## 3 Red social sintética

### 3.1 Generación

Se utilizará un modelo de bloques estocásticos simple: grafo no dirigido, sin pesos, sin lazos sobre el mismo nodo y sin vínculos duplicados. La topología permanecerá fija durante cada campaña. La pertenencia a una comunidad es un atributo de inicialización, no una clasificación inferida posteriormente a partir de los resultados.

Los identificadores serán enteros de `0` a `n_agents - 1`. Una permutación reproducible distribuirá esos identificadores entre los seis grupos de igual tamaño. Así, los identificadores consecutivos no funcionarán como un criterio implícito de comunidad.

Sean `N` el número de personas, `s = N / C` el tamaño de cada comunidad, `d` el grado medio esperado y `mu` la fracción externa esperada. Para cada pareja no ordenada de nodos se sorteará un único vínculo independiente con probabilidad:

```text
p_in  = d * (1 - mu) / (s - 1)
p_out = d * mu / (N - s)
```

Se utiliza `p_in` dentro de una comunidad y `p_out` entre comunidades. La configuración base implica `p_in ≈ 0.09697` y `p_out = 0.0048`. Se comprueba que ambas probabilidades estén entre 0 y 1; una configuración inválida se rechaza, sin recortar probabilidades. Para escenarios modulares se exige además `p_in > p_out`.

Esta construcción conserva el grado medio **esperado** al variar `mu`, lo que ayuda a separar la mezcla entre comunidades de la densidad de la red. La modularidad realizada se medirá: `mu` no se presentará como si fuera el valor observado de modularidad.

### 3.2 Condiciones estructurales previstas

| Escenario | `mu` | Interpretación relativa |
|---|---:|---|
| Mayor mezcla | 0.50 | Menor separación entre comunidades |
| Base | 0.20 | Separación intermedia |
| Menor mezcla | 0.05 | Mayor separación entre comunidades |

La comparación inicial utilizará solo el escenario base. Los otros valores quedan previstos para análisis de sensibilidad. En futuras comparaciones entre estos escenarios se reutilizarán la población y los sorteos por pareja, cambiando únicamente las probabilidades de vínculo.

Se conservarán todos los componentes, incluidos los nodos aislados. No se agregarán enlaces para forzar conectividad ni se descartarán semillas por producir una estructura poco favorable. Si la componente mayor contiene menos del 95% de las personas, se emitirá una advertencia para revisión metodológica; no se regenerará la red automáticamente.

El generador produce variación en grado, pero no garantiza una distribución de cola pesada ni agrupamiento moderado. Los hubs serán los nodos de mayor grado **relativo en la red generada**. Se reportará el agrupamiento observado. Incorporar hubs extremos o cierre triádico requeriría una extensión explícita y una nueva versión de la especificación.

### 3.3 Diagnósticos obligatorios

Se exportarán número de nodos y vínculos, densidad, grado medio, mínimo, máximo y dispersión, promedio de agrupamiento local, número de componentes, fracción en la componente mayor, nodos aislados, proporción realizada de vínculos externos y modularidad de la partición inicial. El agrupamiento local de nodos con grado inferior a dos será cero. La modularidad de una red sin enlaces será nula/no definida en el archivo, acompañada por el motivo; no se reemplazará por un cero interpretado como resultado.

## 4 Personas y atributos

Todos los individuos pueden ser seleccionados. Cada persona conserva el mismo vector de atributos bajo las siete políticas. Los roles se derivan de puntajes: no se asigna una etiqueta exclusiva de hub, influencer o líder de opinión.

### 4.1 Información previa disponible para la selección

| Campo | Símbolo | Construcción y función |
|---|---|---|
| `actor_id` | i | Identificador estable |
| `community_id` | g_i | Comunidad asignada |
| `degree` | d_i | Número de vecinos |
| `structural_reach` | R_i | `d_i / max_degree`; cero si no hay enlaces |
| `community_reach` | G_i | Comunidades distintas entre vecinos divididas por C; cero para aislados |
| `activity` | A_i | Frecuencia o capacidad relativa de comunicación |
| `credibility` | C_i | Credibilidad percibida del actor |
| `expertise` | E_i | Conocimiento del actor |
| `expertise_fit` | F_i | Pertinencia de ese conocimiento para el producto |
| `recommendation_propensity` | W_i | Disposición a recomendar tras una experiencia satisfactoria |
| `need` | N_i | Indicador previo de necesidad |
| `product_fit` | T_i | Indicador previo de ajuste del producto |
| `predicted_economic_potential` | P_i | Indicador previo de valor económico |
| `predicted_purchase_value` | Vhat_i | `50 + 150 * P_i`, en unidades monetarias abstractas |
| `activation_cost` | c_i | Constante igual a 1 en M1 |
| `tie_rank` | b_i | Posición en una permutación aleatoria común para resolver empates |

En el escenario base, `A`, `C`, `E`, `F`, `W`, `N`, `T` y `P` se generan de manera independiente mediante Beta(2, 2), también independientemente de la estructura. Independencia de generación no significa correlaciones muestrales exactamente iguales a cero.

Actividad y disposición a recomendar representan mecanismos diferentes: la primera se relacionará con la intensidad de comunicación; la segunda, con la probabilidad de recomendar después de adoptar y quedar satisfecho. M1 solamente inicializa ambas. Un valor positivo no convierte al individuo en emisor activo.

Se supone que la empresa conoce la red y estos indicadores previos, incluidos los de los vecinos. Es una condición de información idealizada para comparar reglas. No equivale a afirmar que una empresa real pueda observar perfectamente esas características. La información incompleta o medida con error se reservará para sensibilidad posterior.

### 4.2 Valor económico latente y estados iniciales

Para cada persona se sorteará `Z_i ~ Normal(0, 1)` independientemente de los indicadores previos y se generará:

```text
latent_purchase_value_i = predicted_purchase_value_i
                          * exp(sigma * Z_i - sigma**2 / 2)
```

Con `sigma = 0.35`, el valor latente es positivo y difiere de la estimación previa. Con `sigma = 0`, ambos coinciden. Este valor se genera una sola vez por población para permitir comparaciones emparejadas, pero permanece oculto para las políticas. No constituye ingreso realizado: solo podría producir un ingreso si el módulo posterior genera una compra.

El archivo o estructura de valores latentes estará separado de la tabla que recibe la función de selección. Tampoco se permitirán como entradas los futuros ingresos, adopciones, satisfacción, cascadas o posiciones en rankings realizados.

Cada ejecución de una política partirá con `selected = False`, `aware = False`, `adopted = False`, `wom_active = False`, satisfacción no evaluada, cero exposiciones y cero ingresos. Al seleccionar se modificará únicamente `selected`, junto con los campos de auditoría de la selección. La información del producto y la evaluación comenzarán en el módulo siguiente.

### 4.3 Correlaciones y sensibilidad

M1 registrará distribuciones y correlaciones de Spearman entre grado, actividad, credibilidad, experiencia, ajuste de experiencia, disposición a recomendar y potencial económico. Las correlaciones que involucren una variable constante se exportarán como no definidas.

La primera implementación utilizará únicamente atributos generados de forma independiente. La guía contempla correlaciones positivas y negativas: su generación controlada será una extensión de M1 antes de ejecutar ese experimento. Deberá conservar las distribuciones marginales, documentar el procedimiento y reportar las correlaciones realizadas. Se prohíbe presentar el escenario independiente como si ya cubriera esas condiciones.

## 5 Puntajes calculados antes de la campaña

Los puntajes serán deterministas dadas la red y la información previa. No se ajustarán sus ponderaciones utilizando los resultados de las campañas que se pretenda comparar.

### 5.1 Alcance actividad y opinión

```text
hub_score_i        = R_i
influencer_score_i = A_i
opinion_score_i    = L_i = C_i * E_i * F_i
```

El producto de credibilidad, experiencia y pertinencia representa complementariedad: una experiencia que no corresponde al producto no aporta al puntaje. Esta es una decisión ilustrativa. Una media aritmética alternativa podrá evaluarse posteriormente, sin sustituir la regla base después de observar qué resultados favorece.

### 5.2 Indicador de ingresos previstos

Sea `neighbors(i)` el conjunto de vecinos. Se definen:

```text
neighbor_potential_i = promedio de P_j entre los vecinos de i
neighbor_fit_i       = promedio de (N_j * T_j) entre los vecinos de i
conversion_proxy_i   = L_i * neighbor_fit_i

predicted_revenue_score_i = 0.20 * P_i
                          + 0.20 * R_i
                          + 0.20 * neighbor_potential_i
                          + 0.20 * conversion_proxy_i
                          + 0.20 * A_i
```

Los promedios sobre un vecindario vacío serán cero. Los cinco componentes se encuentran entre 0 y 1 y los pesos suman uno. Los pesos iguales evitan introducir una jerarquía adicional sin justificación; no se presentan como estimaciones de efectos reales.

El indicador combina valor propio, alcance, valor de los vecinos, una aproximación a conversión y actividad. Se denomina política de ingresos previstos por su objetivo, pero **su puntaje es un índice de ordenamiento entre 0 y 1, no una predicción monetaria ni una probabilidad de compra**. No incluye recompra en M1. No se calculará error absoluto entre este índice e ingresos monetarios futuros; esa comparación mezclaría escalas.

### 5.3 Puntaje combinado

```text
combined_score_i = 0.25 * hub_score_i
                 + 0.25 * influencer_score_i
                 + 0.25 * opinion_score_i
                 + 0.25 * predicted_revenue_score_i
```

Este puntaje se utilizará únicamente para ordenar candidatos dentro de las comunidades. Compartir el intervalo 0–1 no implica que los cuatro componentes tengan igual dispersión o igual influencia efectiva. Se reportarán sus distribuciones y se reservarán ponderaciones y normalización por rangos para sensibilidad.

## 6 Siete políticas de selección

Cada política devuelve exactamente `k` personas diferentes. Para cualquier ranking se ordenará primero por puntaje descendente y luego por `tie_rank` ascendente. La permutación de desempate se generará una vez por población y se reutilizará entre políticas; no dependerá del orden en que se ejecuten.

| Código | Política | Regla |
|---|---|---|
| `random` | Aleatoria | Muestreo uniforme de k personas sin reemplazo mediante un generador exclusivo |
| `hubs` | Hubs | Primeras k personas por `hub_score` |
| `influencers` | Actividad comunicativa | Primeras k personas por `influencer_score` |
| `opinion_leaders` | Líderes de opinión | Primeras k personas por `opinion_score` |
| `predicted_revenue` | Ingresos previstos | Primeras k personas por `predicted_revenue_score` |
| `community_diversified` | Diversificada | Cuotas por comunidad y selección interna por `combined_score` |
| `hybrid` | Híbrida | Cuotas entre los cuatro rankings puros, con sustitución de duplicados |

### 6.1 Política diversificada

Si `k >= C`, se reserva una plaza por comunidad. Las plazas restantes se distribuyen proporcionalmente al número de candidatos todavía disponibles en cada comunidad. Se usa el método de mayores restos: asignar la parte entera de cada cuota y distribuir las plazas sobrantes por el mayor resto decimal. Los empates se resuelven con una permutación de comunidades generada una vez por población.

Con 20 plazas y seis comunidades iguales se obtienen cuotas `4, 4, 3, 3, 3, 3`. Las dos comunidades con cuatro plazas variarán de acuerdo con el desempate reproducible. Dentro de cada grupo se seleccionan los mejores candidatos por `combined_score`.

Si `0 < k < C`, se sortean k comunidades distintas con un generador exclusivo y se elige al mejor candidato de cada una. Si `k = 0`, el conjunto seleccionado es vacío. Se registran las cuotas solicitadas y realizadas.

### 6.2 Política híbrida

Los cuatro rankings componentes serán hubs, actividad, opinión e ingresos previstos. Cada uno recibirá el 25% de las plazas. Para `k = 20` corresponden cinco plazas a cada componente. Para otros valores se utilizan partes enteras y mayores restos; los empates entre componentes se resuelven mediante una permutación reproducible propia.

La selección avanzará por rondas, tomando una persona por componente que tenga cuota pendiente. Dentro de cada ronda se usará el mismo orden de componentes sorteado para esa población. Cada componente recorrerá su ranking y omitirá personas ya seleccionadas hasta encontrar la siguiente disponible. Las cuatro listas contienen a toda la población; por tanto, con `k <= N` siempre existen candidatos para completar las cuotas.

Se registrará el componente que ocupó cada plaza y cuántos candidatos se omitieron por duplicación. Un actor puede tener puntajes altos en varias dimensiones, pero ocupa una sola plaza. El orden de componentes puede afectar la selección y se incluirá en sensibilidad; no se elegirá a posteriori el orden que produzca mejores resultados.

### 6.3 Comparación justa

En una repetición las siete políticas compartirán red, comunidades, atributos, valores latentes, costos y desempates comunes. Solo variará la regla de selección. Cada política trabajará sobre una copia de los estados iniciales para impedir que una selección modifique la siguiente.

La igualdad de cantidad y costo es válida porque el costo unitario es constante. La comparación con costos heterogéneos y presupuesto fijo será un experimento distinto y no se mezclará con la comparación base.

## 7 Medidas y archivos de salida

### 7.1 Diagnósticos de las selecciones

Para cada política se informarán cantidad y costo total, actores seleccionados por comunidad, distribución de cada atributo y puntaje entre seleccionados, grado medio seleccionado y diferencias descriptivas respecto de toda la población.

Sea `S` el conjunto seleccionado. La audiencia potencial externa a la selección será:

```text
U(S) = unión de los vecinos de los actores de S, excluyendo a los propios actores de S
```

`potential_unique_neighbors = |U(S)|` mide contactos potenciales a un paso, no personas efectivamente informadas. Si `m_j` es el número de actores de S que tienen al contacto j como vecino, se calculan:

```text
potential_contact_incidences = suma de m_j para j en U(S)
potential_redundancy = (potential_contact_incidences - |U(S)|)
                      / potential_contact_incidences
shared_audience_fraction = número de j con m_j >= 2 / |U(S)|
```

Los dos cocientes serán cero cuando sus denominadores sean cero. La redundancia potencial cuenta incidencias repetidas y la fracción compartida cuenta personas compartidas; se reportarán por separado. No equivalen a mensajes enviados, exposición repetida observada o alcance efectivo.

Se distinguirán comunidades representadas entre seleccionados y comunidades presentes en `U(S)`. La coincidencia entre pares de políticas se medirá mediante tamaño de intersección e índice de Jaccard `|S_a ∩ S_b| / |S_a ∪ S_b|`; para dos selecciones vacías Jaccard será uno. Se exportará la matriz completa de siete por siete.

### 7.2 Contrato de exportación

| Archivo previsto | Una fila por | Campos principales |
|---|---|---|
| `config.json` | Configuración | Versión, parámetros, pesos, semilla maestra y semillas por componente |
| `nodes_ex_ante.csv` | Persona | Identificadores, comunidad, atributos observables, métricas y puntajes |
| `edges.csv` | Vínculo | `source`, `target`, `same_community`; siempre `source < target` |
| `latent_values.csv` | Persona | Identificador y valor latente; excluido de entradas de selección |
| `selection.csv` | Plaza asignada | Repetición, política, actor, orden, puntaje usado, componente y cuota cuando corresponda |
| `selection_audit.csv` | Decisión | Política, candidato, motivo de aceptación o descarte y duplicaciones híbridas |
| `network_diagnostics.csv` | Red | Métricas estructurales y advertencias |
| `attribute_correlations.csv` | Par de variables | Correlación, tamaño y motivo si no está definida |
| `policy_diagnostics.csv` | Política | Cantidad, costo, atributos seleccionados y audiencia potencial |
| `policy_overlap.csv` | Par de políticas | Intersección, unión y Jaccard |
| `verification_report.json` | Prueba | Identificador, resultado, evidencia y error si lo hay |
| `manifest.json` | Ejecución | Versión de código, entorno, archivos y huellas SHA-256 |

Todos los CSV tendrán identificador de repetición o se ubicarán en un directorio identificado de forma inequívoca por escenario y repetición. Las medidas de desempeño comercial no se rellenarán con ceros ficticios: estarán ausentes de M1, salvo los estados iniciales explícitamente definidos como cero.

## 8 Implementación y reproducibilidad en Python

La implementación propuesta utilizará Python 3, NumPy para sorteos, NetworkX para la representación y los diagnósticos de red, pandas para tablas y pytest para pruebas. Las versiones realmente utilizadas se fijarán al implementar mediante un archivo de dependencias y se registrarán en cada ejecución. M1 no requiere un entorno de agentes complejo.

| Componente propuesto | Responsabilidad |
|---|---|
| `config.py` | Validación de parámetros y pesos |
| `network.py` | Comunidades, vínculos y métricas |
| `attributes.py` | Indicadores previos y valores latentes separados |
| `scores.py` | Puntajes deterministas |
| `selection.py` | Siete políticas y auditoría |
| `diagnostics.py` | Audiencias potenciales, correlaciones y solapamiento |
| `export.py` | Archivos y manifiesto |
| `run_m1.py` | Inicialización y comparación de selecciones |
| `tests/` | Verificación con casos pequeños y controles |

Estas son interfaces previstas, no archivos ya implementados. La función de selección recibirá exclusivamente red, tabla de información previa, puntajes, política, k y generadores autorizados. No recibirá el objeto completo que contiene valores latentes o resultados posteriores.

Una semilla maestra y un identificador de repetición producirán generadores separados para pertenencia comunitaria, vínculos, cada atributo, valor latente, desempates, selección aleatoria, cuotas comunitarias y orden híbrido. La asignación de componentes a semillas utilizará identificadores numéricos estables documentados; no dependerá del orden de llamadas ni de funciones hash variables entre sesiones.

Cambiar el orden de ejecución de las políticas no cambiará sus resultados. Agregar una política tampoco regenerará la población. Las tablas se exportarán con orden canónico por identificador y los vínculos por `source, target`. La reproducción exacta se verificará dentro del entorno de dependencias registrado; fechas y otros metadatos de ejecución se excluirán de comparaciones de identidad de resultados.

Cuando se incorpore difusión, compartir una semilla global no será suficiente si las políticas consumen sorteos en órdenes diferentes. Los sorteos de eventos deberán asociarse a claves estables, como repetición, período, persona o pareja y tipo de evento, para mantener una comparación emparejada.

## 9 Pruebas de aceptación

Las pruebas siguientes están **especificadas y pendientes de ejecución**. No constituyen resultados de verificación.

| ID | Prueba | Criterio de aceptación |
|---|---|---|
| T01 | Configuración | Rechaza tamaños incompatibles, k fuera de rango, pesos inválidos y probabilidades fuera de [0, 1] |
| T02 | Integridad de red | N nodos únicos; C grupos del tamaño esperado; sin lazos ni enlaces duplicados; simetría |
| T03 | Cálculo estructural | Grados, componentes, alcance y audiencias coinciden con un grafo pequeño calculado manualmente |
| T04 | Atributos y límites | Atributos en [0, 1], valor latente positivo y costos iguales; controles con valores 0 y 1 |
| T05 | Separación ex ante | Cambiar o permutar valores latentes y futuros resultados no altera puntajes ni selección |
| T06 | Puntajes | Los cuatro puntajes puros y el combinado coinciden con cálculos manuales; pesos suman uno |
| T07 | Rankings distintos | Un caso con hub poco activo y actor activo de bajo grado produce selecciones distintas según la regla |
| T08 | Selección exacta | Cada política devuelve k actores elegibles únicos y costo total k |
| T09 | Aleatoria | Selección reproducible sin reemplazo; con k = N selecciona a todos |
| T10 | Diversificación | Con N = 600, C = 6 y k = 20 cumple las cuotas 4, 4, 3, 3, 3, 3 y representa las seis comunidades |
| T11 | Híbrida | Asigna cinco plazas por componente y completa 20 personas incluso si los cuatro rankings coinciden |
| T12 | Empates | Empates totales respetan los desempates registrados; cambiar el orden de políticas no cambia selecciones |
| T13 | Estado inicial | Seleccionar no crea conocimiento del producto, adopción, satisfacción, WOM ni ingresos |
| T14 | Audiencia compartida | Un caso de vecinos compartidos reproduce manualmente incidencias, audiencia única y ambos cocientes |
| T15 | Casos límite | k = 0, k = N, k < C, red vacía, aislados y red completa usan las convenciones definidas |
| T16 | Reproducción | Misma configuración, semillas y entorno producen los mismos datos y selecciones |
| T17 | Independencia de ejecución | Invertir el orden de las siete políticas conserva resultados y huellas de la población |
| T18 | Exportación | Archivos pueden volver a leerse; identificadores, tipos, conteos y referencias entre tablas son válidos |
| T19 | Inspección entre semillas | Diez poblaciones predefinidas generan diagnósticos y 70 selecciones sin violar invariantes |

La inspección T19 utilizará una semilla maestra registrada y repeticiones `0` a `9`. Sus resultados se reportarán completos, incluidas advertencias; no se excluirán realizaciones para producir correlaciones o diferencias deseadas. Estas 70 selecciones **no son 70 simulaciones de difusión** ni cuentan dentro de las 700 campañas previstas.

La igualdad de atributos personales no garantiza resultados iguales si las posiciones de red difieren. Por ello, un control de simetría completo debe igualar también las oportunidades estructurales relevantes. No se exigirá que todas las políticas escojan exactamente las mismas personas cuando sus restricciones difieran.

M1 se considerará verificado cuando todas las pruebas de invariantes y casos manuales sean satisfactorias, la inspección entre semillas esté documentada y las advertencias estructurales hayan sido revisadas. La verificación confirma que el código cumple las reglas; la plausibilidad de esas reglas requiere revisión conceptual por los profesores.

## 10 Entrega y siguiente etapa

La especificación se guardará en `02_Especificacion_del_modelo`. El código y las dependencias irán en `03_Codigo`; la configuración y las semillas, en `04_Diseno_experimental`; el informe de pruebas, en `05_Verificacion_y_piloto/01_Pruebas_y_registros`; y las tablas exportadas, en `06_Resultados_simulaciones/01_Datos_brutos`.

El siguiente paso es **implementar M1 en Python y ejecutar las pruebas T01–T19**. Santiago revisará los diagnósticos, perfiles de actores y diferencias entre selecciones, mientras los profesores revisan supuestos y pertinencia teórica. Los cambios se registrarán por versión con su justificación, antes de incorporarlos al código.

Después se redactará e implementará M2: evaluación y adopción de actores seleccionados, satisfacción, comunicación, exposición y adopción de clientes. Las fórmulas de adopción deberán permitir que las políticas fallen y no convertirán los puntajes de selección en resultados comerciales predeterminados.

La evaluación de ingresos previstos frente a liderazgo realizado requerirá definir el universo evaluado y la atribución de ingresos. No se considerará que un actor no seleccionado habría fracasado como iniciador solo porque no se observó su campaña. M1 no resolverá esa pregunta mediante rankings artificiales o resultados ocultos usados durante la selección.

Las 700 campañas de la comparación base, los experimentos de complejidad y modularidad, y las sensibilidades de la guía se ejecutarán después de completar y verificar el modelo comercial y revisar el piloto. Las simplificaciones de esta v0.1 acotan el primer módulo y no eliminan los experimentos previstos para el artículo.

**Fuente de alcance:** guía adjunta *Indications – Article 9 – NM – Strategic Actors*, especialmente las secciones 29–41, 53–60, 81 y 99–101. Los valores numéricos, distribuciones, fórmulas de puntajes y algoritmos detallados aquí constituyen decisiones propuestas de implementación cuando la guía no fija una regla única. No se incorporan referencias bibliográficas ni afirmaciones empíricas nuevas.
