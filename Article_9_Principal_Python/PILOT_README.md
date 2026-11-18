# Artículo 9. Piloto de sensibilidad v0.1

Extensión de ejecución y análisis sobre **M3 v0.3 sin editar sus ecuaciones**. El ZIP original de M3 tiene SHA256 `66c941ce378c49582d69f4f8ab61bad875e5a69559e054ba87ffc3a562e4dd0e`.

## Diseño fijado antes de ejecutar

20 escenarios × 7 políticas × 20 repeticiones = **2.800 evaluaciones económicas**. Se requieren 1.960 difusiones distintas: los seis cambios exclusivamente económicos reutilizan la difusión base. No se contabilizan como nuevas trayectorias estocásticas independientes. N=600, comunidades=6, k=20, horizonte=60. Semilla maestra 20260925, repeticiones 0–19.

| Factor | Base | Valores adicionales |
|---|---:|---|
| Intercepto de adopción | −2 | −3, −4 |
| Umbral de satisfacción | 0,60 | 0,70; 0,80 |
| Capacidad base de contacto | 4 | 2, 6 |
| Calidad | 0,75 | 0,50; 0,90 |
| Complejidad | 0,50 | 0,20; 0,80 |
| Mezcla entre comunidades | 0,20 | 0,05; 0,40 |
| Ruido del valor latente σ | 0,35 | 0; 0,70 |
| Intensidad de recompra | 0 | 0,02; 0,05 |
| Costo proporcional de servicio | 0,20 | 0,40 |
| Costo fijo adicional por compra | 0 | 30 u.m. |
| Cruce diagnóstico | −2 y 0,60 | Intercepto −3 con satisfacción 0,70 |

Son 18 cambios de un factor más el cruce y la base. No es un factorial completo, un análisis Sobol ni una búsqueda de ganadores. Los niveles son supuestos teóricos ilustrativos. σ modifica conjuntamente dispersión latente e incertidumbre predictiva; cero ruido no elimina la variación del valor previsto.

## Medición y comparación

Resultados: conocimiento, adopción final, adopción en meses 12 y 30, media de adopción en meses 1–60, alcance y redundancia, ingresos, utilidad, concentración por raíz y métricas predictivas condicionales. Saturación: adopción final ≥95%.

Tiempos no alcanzados quedan vacíos. Para contrastes, `restricted_t50` usa 61 cuando no se alcanza el 50%, únicamente como puntuación acotada, nunca como mes observado. Se acompaña de `reached_50`.

Las diferencias escenario–base y política–aleatoria se emparejan por repetición. Intervalos puntuales de 95%: 4.000 remuestreos bootstrap, semilla 20260927. La unidad es la repetición; para promediar políticas se promedia antes dentro de cada bloque. No se ajusta por multiplicidad: alcance exploratorio, no inferencia confirmatoria sobre empresas reales. Métricas predictivas indefinidas se excluyen con n efectivo explícito.

## Reproducción

```bash
python -m pip install -r requirements-lock.txt
python -m pip install -r requirements-pilot.txt
python -m pytest -q tests
python run_pilot.py --out outputs/pilot_v01 --workers 4
python analyze_pilot.py --input outputs/pilot_v01
```

Usar carpetas nuevas. `run_pilot.py --design-only --out outputs/design_only` guarda el diseño sin simular. La cantidad de procesos solo cambia tiempo de ejecución, no semillas o resultados. Con una máquina de poca memoria, usar `--workers 1`.

## Datos conservados

Cada repetición tiene `campaigns.csv`, `monthly.csv`, `completion.json` y `records.zip`. El ZIP conserva poblaciones, aristas, selección, estados finales por difusión única, compras por evaluación, cuentas de raíces y referencias. Cada tabla incluye los identificadores pertinentes; `diffusion_id` y `population_id` se interpretan dentro de una repetición, no globalmente.

Las trazas individuales mensuales y todos los eventos de M2 se conservan para cuatro campañas fijadas de antemano: repetición 0, política aleatoria, base, intercepto −3, umbral 0,70 y su cruce. Para las demás campañas se conservan series agregadas, estados finales y libro económico; las historias completas pueden regenerarse sin pérdidas de semillas. No se afirma que el paquete contenga todas las historias mensuales individuales de las 1.960 difusiones.

El análisis produce tablas por escenario/política, contrastes emparejados, interacción, estabilidad de rankings, trayectorias medias, gráficos e informe. Las comparaciones económicas no alteran difusión. No se analizan aquí pérdida de actores, resiliencia, correlación de roles, presupuestos igualados o tamaño de red.

El piloto orienta el diseño principal. No sustituye las ≥100 repeticiones por condición solicitadas en la guía. Se debe conservar la base de referencia y justificar teóricamente cualquier cambio posterior antes de volver a ejecutar.
