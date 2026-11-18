# Artículo 9 Especificación operativa de M2

**Versión:** 0.2.0. **Fecha:** 26 de septiembre de 2026. **Implementación:** Python.  
**Base:** M1 v0.1.0, con red, atributos y siete políticas de selección.  
**Alcance:** evaluación, adopción, experiencia, satisfacción y difusión de WOM positivo.

## 1 Propósito

M2 convierte las selecciones de M1 en campañas temporales. Permite observar quién conoce la oferta, quién adopta, quién queda satisfecho y quién transmite recomendaciones. La red y los atributos se conservan durante cada campaña. Todos los actores siguen las mismas reglas de comportamiento, con independencia de la política que los seleccionó.

Las ecuaciones y los parámetros de esta versión son supuestos teóricos ilustrativos. No se calibran con datos empresariales y no garantizan que una categoría de actor gane. Los puntajes de selección, los valores económicos previstos y los valores económicos latentes no entran en las ecuaciones de comportamiento. Las diferencias entre políticas provienen de las personas que seleccionan.

Esta versión operacionaliza las alternativas de las secciones 42–48 y 52 de la guía del artículo. Los ingresos, costos comerciales, recompra y precisión del liderazgo económico previsto se reservan para M3.

## 2 Tiempo y secuencia de operaciones

El horizonte base es de 60 períodos mensuales. Se exportan también los estados del período 0, por lo que cada campaña tiene 61 observaciones agregadas.

1. En el período 0 se aplica la política de M1. La selección no crea conocimiento de la oferta ni adopción.
2. En el período 1 los 20 actores seleccionados reciben información directa, evalúan el producto y pueden adoptarlo. Los adoptantes reciben una evaluación inmediata de satisfacción.
3. Desde el período 2, los adoptantes de períodos anteriores pueden emitir WOM si cumplen las condiciones de satisfacción, disposición, actividad y audiencia disponible.
4. Cada período reúne todos los mensajes antes de evaluar a sus receptores. Cada receptor realiza una sola decisión de adopción en ese período.
5. Los nuevos adoptantes conocen su satisfacción en el período de adopción y pueden recomendar desde el período siguiente.
6. Se actualizan los estados, las cascadas, los conteos y las trazas al final del período.

Las decisiones de emisión usan el estado de inicio del período. El orden de recorrido de emisores no permite cascadas instantáneas. La campaña conserva todo el horizonte aunque no haya nuevos mensajes. Un actor elegible al final del horizonte puede mantener contactos pendientes; no se declara su cascada extinguida por haber terminado la observación.

## 3 Evaluación y adopción

Se utiliza la función logística `L(x) = 1 / (1 + exp(-x))`. Para el receptor j se definen necesidad `N_j`, ajuste del producto `T_j`, experiencia `E_j`, pertinencia de la experiencia `F_j`, calidad `q` y complejidad `c`.

```text
riesgo_j = c * (1 - E_j * F_j)
base_j = -2 + 2*N_j + 2*T_j + q - riesgo_j
```

La necesidad y el ajuste son condiciones necesarias: si `N_j <= 0` o `T_j <= 0`, la probabilidad de adopción es cero. Esta decisión operacional es más restrictiva que impedir únicamente la adopción cuando ambos son cero y queda explícita para análisis de sensibilidad.

Para la información directa recibida por un seleccionado:

```text
p_adopcion_directa_j = L(base_j)
```

Cada seleccionado se evalúa directamente una sola vez, en el período 1. Si no adopta, permanece informado y puede reconsiderar el producto cuando reciba posteriormente WOM. No obtiene nuevos intentos gratuitos por el transcurso del tiempo.

Para un emisor i, la señal creíble es:

```text
senal_i = credibilidad_i * ((1 - c) + c * E_i * F_i)
```

Con complejidad cero, la señal depende de credibilidad. Con complejidad positiva, la experiencia pertinente distingue más a los emisores. Credibilidad cero implica contribución creíble cero; no elimina necesariamente la adopción por necesidad, ajuste u otros componentes.

Para un receptor con uno o más mensajes nuevos en el período:

```text
senal_actual_j = máximo de senal_i entre sus mensajes nuevos
prueba_social_j = min(emisores_distintos_acumulados_j / 3, 1)
p_adopcion_WOM_j = L(base_j + 2*senal_actual_j + 0.5*prueba_social_j)
```

Se conserva el historial de emisores distintos, pero no la mayor señal de períodos anteriores. Cada período con mensajes nuevos utiliza su señal máxima actual. Un receptor sin mensajes nuevos no vuelve a evaluar por WOM. El uso del máximo evita sumar sin límite señales simultáneas; la regla es un supuesto que puede compararse con agregaciones alternativas más adelante.

Cada evaluación utiliza un solo uniforme `u` y adopta si `u < p`. Las probabilidades cero impiden adopción incluso en los controles con `u = 0`. Cada persona adopta como máximo una vez. La necesidad, el ajuste y el riesgo permanecen fijos en esta versión.

## 4 Experiencia satisfacción y envío

La experiencia del producto se representa mediante su calidad y ajuste al adoptante. No se simulan todavía experiencias repetidas o aprendizaje.

```text
satisfaccion_j = 0.60*q + 0.40*T_j
satisfecho_j = satisfaccion_j >= 0.60
```

La satisfacción permanece sin evaluar antes de adoptar. Se aplica la misma regla a seleccionados y clientes posteriores. Los adoptantes insatisfechos no emiten WOM positivo ni se convierten automáticamente en emisores de WOM negativo.

Para poder recomendar, una persona debe haber adoptado antes del período actual, estar satisfecha, tener actividad positiva, disposición positiva a recomendar, capacidad entera positiva, probabilidad positiva de envío y al menos un vecino elegible.

```text
capacidad_i = floor(4 * actividad_i)
p_envio_i = satisfaccion_i * disposicion_recomendar_i
```

Se realiza un sorteo de envío por emisor elegible y período. Si lo supera, contacta hasta su capacidad, limitada por los vecinos disponibles. Si falla, conserva sus contactos para períodos posteriores.

La actividad controla cuántos contactos puede intentar; la disposición y la satisfacción controlan si intenta comunicar en el período. Una actividad positiva menor que 0.25 produce capacidad cero con la escala base. Se registra esta situación como `zero_integer_capacity`, sin elevar artificialmente la capacidad a uno.

## 5 Selección de contactos y exposiciones

Los receptores elegibles son vecinos que no han adoptado al inicio del período y a quienes ese emisor todavía no ha enviado WOM. El emisor ordena sus candidatos por prioridades pseudoaleatorias y toma los primeros hasta completar su capacidad. Las prioridades se generan por pareja y período, con idéntica regla para las siete políticas.

Cada par dirigido emisor–receptor puede producir como máximo un mensaje durante la campaña. No se contacta nuevamente desde el mismo emisor a una persona que rechazó el mensaje. Otros emisores sí pueden contactar a esa persona mientras no adopte. La repetición de exposiciones proviene, por tanto, de recomendaciones de personas diferentes.

Todos los mensajes de un período se consideran simultáneos. Un receptor que adopte al final del período conserva los mensajes simultáneos recibidos de varios emisores; no se suprimen según el orden de ejecución.

Se distinguen:

| Indicador | Definición |
|---|---|
| Conocimiento de la oferta | Personas informadas directamente o mediante WOM |
| Alcance WOM único | Personas con al menos una exposición WOM; incluye seleccionados que reciban WOM |
| Alcance WOM único no seleccionado | Personas expuestas por WOM que no pertenecen a la selección inicial |
| Mensajes WOM | Total de mensajes transmitidos por la red |
| Exposición WOM repetida | Toda exposición posterior a la primera exposición WOM de una persona |
| Adopción directa | Adopción durante la evaluación inicial de un seleccionado |
| Adopción por WOM | Adopción en una evaluación provocada por mensajes nuevos |
| Emisores efectivos | Personas que enviaron al menos un mensaje en el período |
| Emisores elegibles al cierre | Personas que cumplen condiciones para intentar enviar en el período siguiente |

La información directa de los seleccionados no se cuenta como un mensaje WOM. Las identidades contables son `mensajes = alcance_WOM_unico + exposiciones_repetidas` y `adopciones = adopciones_directas + adopciones_WOM`.

Cuando dos mensajes llegan por primera vez a una persona en el mismo período, un orden canónico por receptor y emisor identifica uno como primera exposición y el otro como repetido. Esta convención contable no modifica la decisión conjunta de adopción ni otorga automáticamente la atribución al primer mensaje listado.

## 6 Cascadas y atribución

El actor que adopta por información directa es la raíz de su propia cascada y tiene profundidad cero. Una adopción por WOM recibe un único padre entre sus mensajes nuevos: el emisor con mayor señal creíble. Los empates se resuelven mediante un sorteo reproducible propio. El nuevo adoptante hereda la raíz del padre y aumenta su profundidad en uno.

Cada evento indica si su receptor adoptó en ese período, pero **solo el evento atribuido contiene `conversion_credit = True`**. No se debe sumar `receiver_adopted_this_month` como si cada mensaje hubiera generado una adopción diferente.

Si un seleccionado rechaza la información directa y posteriormente adopta por WOM, pertenece a la cascada del recomendador. No se crea una segunda raíz para contabilizar la misma adopción. Los padres siempre adoptaron en un período anterior a sus hijos, lo que impide ciclos de atribución.

Esta regla es una convención de atribución trazable. No identifica el efecto causal de un mensaje: la decisión también incorpora necesidad, ajuste y prueba social. Los ingresos y los criterios de atribución monetaria serán parte de M3.

## 7 Parámetros y aleatoriedad

| Parámetro | Valor base |
|---|---:|
| Horizonte mensual | 60 |
| Calidad del producto | 0.75 |
| Complejidad del producto | 0.50 |
| Capacidad base de contactos | 4 |
| Peso de calidad en satisfacción | 0.60 |
| Umbral de satisfacción | 0.60 |
| Intercepto de adopción | -2.00 |
| Efecto de necesidad | 2.00 |
| Efecto de ajuste | 2.00 |
| Efecto de calidad | 1.00 |
| Penalización de riesgo | 1.00 |
| Efecto de señal creíble | 2.00 |
| Efecto de prueba social | 0.50 |
| Emisores para saturar prueba social | 3 |

Los valores se validan por dominio y finitud. La configuración de M2 es la autoridad para su horizonte; el campo de horizonte reservado en M1 se utiliza como valor por defecto del ejecutor cuando no se proporciona una configuración M2.

M1 conserva sus generadores originales. M2 transforma claves de evento mediante BLAKE2b de 64 bits y usa los 53 bits altos divididos por `2**53` como un uniforme en `[0,1)`. Es un campo pseudoaleatorio determinista para reproducibilidad, no una fuente de aleatoriedad física.

La clave contiene semilla maestra, repetición, tipo de evento, período, actor y, cuando corresponda, otro actor. Los códigos son: adopción directa 400, envío 401, prioridad de contacto 402, adopción WOM 403 y desempate de atribución 404. La política no forma parte de la clave. Reordenar políticas, filas o emisores no cambia el valor asignado a un evento comparable.

## 8 Exportación y pruebas

Cada campaña exporta `config.json`, `periods.csv`, `wom_events.csv`, `evaluations.csv`, `sender_months.csv`, `state_history.csv`, `final_states.csv`, `cascades.csv`, `summary.json`, `summary.csv` y `manifest.json`. Cada repetición incluye una carpeta de población M1 compartida por sus siete políticas, con nodos, enlaces, selecciones e insumos latentes para el desarrollo posterior.

Las trazas permiten recuperar la probabilidad y el sorteo de cada evaluación, la causa de no emisión, el estado mensual de cada persona, la procedencia de cada mensaje y la genealogía de cada adopción. Las métricas temporales incluyen tiempo hasta umbrales de conocimiento y adopción; los umbrales no alcanzados quedan vacíos, sin sustituirse por el último mes observado.

La batería de M2 añade 22 pruebas a las 19 de M1: parámetros; ecuaciones manuales; credibilidad y complejidad; necesidad y ajuste; insatisfacción; actividad y capacidad cero; secuencia en una cadena; contacto sin repetición; mensajes simultáneos; reconsideración de seleccionados; agotamiento de audiencia; identidades contables; genealogía; independencia de orden; reproducibilidad de eventos; exclusión de valores ocultos; redes extremas; validación de entradas; exportaciones; integración de siete políticas y umbrales.

La integración conserva tres poblaciones, siete políticas y 60 períodos: 21 campañas de verificación con datos completos. Las pruebas deterministas pequeñas utilizan sorteos controlados para tener resultados manuales conocidos. Las 21 campañas exportadas utilizan exclusivamente el mecanismo pseudoaleatorio ordinario y los parámetros base.

## 9 Límites y continuidad

Esta versión no incorpora ingresos, utilidad, recompra, fatiga, WOM negativo, aprendizaje, cambios de red, cambios de necesidad ni correlaciones controladas de atributos. La satisfacción es una representación mínima basada en calidad y ajuste. La señal máxima, el umbral de satisfacción y la capacidad entera deben evaluarse en sensibilidades posteriores, sin ajustar reglas a resultados deseados.

Las campañas de verificación permiten inspeccionar comportamiento y errores. No constituyen el experimento principal ni justifican una recomendación universal de selección. El siguiente paso es M3, que añadirá compras valoradas, costos e ingresos con atribución consistente, antes del piloto del modelo comercial completo.
