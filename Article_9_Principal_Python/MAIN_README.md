# Artículo 9 Diseño aprobado del experimento principal

Versión 1.0. Aprobado por Sebastián el 27 de septiembre de 2026. Ejecución en Python, manteniendo las ecuaciones M1/M2/M3. Este protocolo se fija antes de las nuevas simulaciones; los pilotos informaron su diseño y se mantienen separados.

## Matriz

| Condición | Intercepto | Satisfacción mínima | Complejidad | Mezcla entre comunidades |
|---|---:|---:|---:|---:|
| Base | −2 | 0,60 | 0,50 | 0,20 |
| Complejidad baja | −2 | 0,60 | 0,20 | 0,20 |
| Complejidad alta | −2 | 0,60 | 0,80 | 0,20 |
| Menor mezcla | −2 | 0,60 | 0,50 | 0,05 |
| Mayor mezcla | −2 | 0,60 | 0,50 | 0,40 |
| Adopción −3 | −3 | 0,60 | 0,50 | 0,20 |
| Satisfacción 0,70 | −2 | 0,70 | 0,50 | 0,20 |
| Combinación | −3 | 0,70 | 0,50 | 0,20 |

Ocho condiciones × siete políticas × 100 repeticiones = **5.600 campañas**. No se duplica la base entre bloques. No es un factorial completo de todos los parámetros y no estima todas las interacciones entre complejidad, red y satisfacción.

Políticas: aleatoria, hubs, influencers, líderes de opinión, ingresos previstos, diversificada por comunidades e híbrida. N=600, seis comunidades de igual tamaño, 20 seleccionados, grado esperado 12. La red permanece fija durante cada campaña. La mezcla cambia entre escenarios, con menor mezcla asociada a mayor modularidad; se reportará modularidad efectiva y grado observado.

## Semillas y horizontes

Semilla maestra 20260925. Cien repeticiones **nuevas**, identificadores 20–119; se excluyen 0–19 del piloto. Los mismos bloques y campos aleatorios se usan entre políticas y condiciones. Las condiciones de mezcla conservan los sorteos de construcción pero generan redes diferentes.

Cada trayectoria se ejecuta hasta 120 meses. Horizonte principal: 60; sensibilidad temporal: 120. Se extrae el prefijo de difusión a 60 y se recalculan sus cuentas y liderazgo sin usar estados futuros. La coincidencia del libro económico y de los períodos 0–60 se verifica en cada campaña. Cero emisores elegibles desde el mes 1 indica absorción; un mes sin eventos no basta. No se supone que el mes 120 sea equilibrio.

## Resultados y análisis fijados

Tres resultados primarios: fracción media de conocimiento meses 1–60, fracción media de adopción meses 1–60 e ingresos acumulados al mes 60. Las medias temporales son medias aritméticas de 60 observaciones, sin incluir el mes 0. Resultados secundarios: adopción y conocimiento a 60/120, ganancias posteriores, alcance único, redundancia, cobertura comunitaria, conversión WOM, concentración y predicción entre seleccionados.

Referencia primaria: selección aleatoria dentro de cada condición. Unidad de análisis y remuestreo: repetición completa. Contrastes emparejados; 4.000 remuestreos bootstrap, semilla 20260927. Se entregan intervalos puntuales percentiles de 95% y bandas simultáneas aproximadas de 95% para la familia de 144 contrastes primarios (8 × 6 × 3), usando el máximo de desviaciones bootstrap estandarizadas por el error estándar observado. Las bandas no tienen cobertura finita exacta garantizada. Los contrastes secundarios e interacciones son exploratorios y usan intervalos puntuales.

Se reportan medias, medianas, desviaciones, IQR, percentiles 5/95 y error Monte Carlo. Las métricas indefinidas no se sustituyen por cero. Las mayores medias observadas se presentan como un mapa descriptivo, sin afirmar superioridad única frente a todas las políticas. Se mantienen 100 repeticiones fijas; los diagnósticos de precisión no deciden exclusiones ni parada según ganadores. Comparar las primeras y últimas 50 repeticiones será solo diagnóstico descriptivo.

## Economía y alcance

Sin recompra; servicio proporcional 20%, servicio fijo cero y activación uno por seleccionado. Utilidad = 0,8 × ingresos − 20; sus rankings coinciden. Los valores son u.m. abstractas. La predicción es condicional a los 20 seleccionados, no a los mejores actores contrafactuales entre 600. No se manipula correlación de roles, pérdida de actores, costos heterogéneos o presupuestos distintos. La heterogeneidad del valor y el error predictivo siguen conjuntamente determinados por la parametrización existente. No hay calibración empírica.

## Datos y reproducción

Se conservan todas las poblaciones, redes, selecciones, diagnósticos, resúmenes, series mensuales, estados a 60/120, compras, cuentas de raíces, rankings predictivos y cascadas. Las trazas individuales mensuales y de eventos completas se guardan para ocho campañas elegidas antes de ejecutar: repetición 20, política aleatoria, una por condición. Para las restantes, las historias se regeneran con código y semillas.

Los bloques se construyen en memoria, se verifican y luego se escriben atómicamente, con lista explícita de archivos y hashes. Los resultados del piloto permanecen intactos.

```bash
python -m pip install -r requirements-lock.txt
python -m pip install -r requirements-pilot.txt
python -m pytest -q tests
python run_main.py --out outputs/main_v1 --workers 8
python analyze_main.py --input outputs/main_v1
```

Usar un directorio nuevo. Menos trabajadores reduce el consumo de memoria sin cambiar resultados. `--resume` exige diseño, código y bloques existentes válidos. No se reejecuta silenciosamente una campaña dañada ni se cambia su semilla.
