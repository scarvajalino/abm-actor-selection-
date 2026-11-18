# Artículo 9. Comprobación 60 → 120 meses

Extensión exploratoria del piloto v0.1 sobre M3 v0.3, sin modificar ecuaciones.

## Diseño fijado antes de ejecutar

| Condición | Intercepto adopción | Umbral satisfacción |
|---|---:|---:|
| Base | −2 | 0,60 |
| Intercepto −3 | −3 | 0,60 |
| Satisfacción 0,70 | −2 | 0,70 |
| Combinación | −3 | 0,70 |

Cuatro condiciones × siete políticas × 20 repeticiones = 560 campañas de 120 meses. N=600, seis comunidades, k=20, semilla maestra 20260925 y repeticiones 0–19, iguales al piloto. Se cambia exclusivamente el horizonte de difusión; los sorteos se indexan por evento, mes y actor y no se reinician en el mes 61. Economía base sin recompra: servicio proporcional 20%, fijo cero y activación uno por seleccionado.

La configuración M1 conserva su campo de horizonte documental de 60, que no interviene en inicialización/selección. El horizonte operativo de esta extensión lo determina M2 (120), y M3 lo infiere de sus períodos. El diseño conserva además la configuración base previa como referencia, sin sobrescribirla.

## Verificación contra el piloto

En cada campaña: igualdad exacta de población, red, seleccionados, series mensuales 0–60, estado individual al mes 60 y compras hasta 60. Para las cuatro campañas de muestra (repetición 0, política aleatoria), igualdad adicional de historias individuales, mensajes, evaluaciones y registro de emisores hasta 60. Cualquier diferencia detiene la ejecución.

## Mediciones

Adopción, conocimiento, emisores elegibles, ingresos, utilidad y alcance de umbrales en meses 60, 90 y 120; ganancias 60→120 y 108→120; medias de adopción en ventanas 1–60, 61–120 y 1–120 separadas. Saturación: adopción ≥95%. Absorción: cero emisores elegibles después de la evaluación inicial (mes ≥1), comprobando que no reaparezcan mensajes ni adopciones. Un mes sin eventos no demuestra absorción.

Contrastes emparejados e interacción del cruce 2×2. Intervalos bootstrap percentil de 95%, 4.000 remuestreos, semilla 20260927. Unidad: repetición; primero se promedian las siete políticas dentro de cada bloque para el resumen general. Veinte bloques, no 140 observaciones independientes. No ajuste por multiplicidad; incertidumbre Monte Carlo, no validación empírica.

## Reproducción

```bash
python -m pip install -r requirements-lock.txt
python -m pip install -r requirements-pilot.txt
python -m pytest -q tests
python run_horizon120.py --reference /ruta/Article_9_Piloto_Datos_v0.1 --out outputs/horizon120 --workers 4
python analyze_horizon120.py --input outputs/horizon120
```

Extraer las cinco partes del piloto previo en el mismo directorio de referencia. Usar salida nueva; no se sobrescriben datos previos. Reducir `--workers` a 1 si la memoria es limitada. Cambiar trabajadores no cambia semillas ni resultados. Las muestras de trazas son las mismas cuatro fijadas en el piloto, no escogidas por su resultado.

## Alcance

Los 120 meses sirven para distinguir lentitud de difusión de agotamiento bajo supuestos estáticos. No implican una predicción de mercado a diez años. El piloto conserva solo 20 repeticiones por condición y política; el experimento principal requiere al menos 100 y un diseño fijado antes de ejecutarlo. No seleccionar parámetros por cuál política gana.
