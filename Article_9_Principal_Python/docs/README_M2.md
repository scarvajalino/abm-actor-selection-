# Article 9 M1 y M2 en Python

Paquete M2 v0.2.0 sobre M1 v0.1.0. Incluye las siete políticas de selección y una dinámica mensual de información, evaluación, adopción, satisfacción y WOM positivo. Los parámetros son supuestos teóricos ilustrativos sin calibración empírica.

## Reproducir la verificación

Se verificó con CPython 3.12.14. Descomprima el paquete, abra una terminal en esta carpeta y ejecute:

```bash
python -m venv .venv
# Linux o macOS
source .venv/bin/activate
# Windows PowerShell, en lugar de la línea anterior
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt
python scripts/verify_m2.py --out outputs/m2_verification
```

El último comando ejecuta **41 pruebas**: T01–T19 de M1 y U01–U22 de M2. Conserva diez inicializaciones de regresión de M1 y **21 campañas de verificación de M2**, con tres poblaciones, siete políticas, 600 personas y 60 períodos. Incluye trazas mensuales completas. El proceso termina con código cero solo cuando todas las pruebas pasan. Utilice una carpeta nueva/vacía de salida.

## Ejecutar campañas

Una población con las siete políticas:

```bash
python run_m2.py --m1-config config_base.json --m2-config m2_config_base.json --out outputs/example --repetitions 1
```

Solo una política:

```bash
python run_m2.py --out outputs/random_example --policies random --repetitions 1
```

El archivo ampliado `Article_9_M2_Configuracion_y_semillas_v0.2.json` documenta la entrega. Para los argumentos de configuración del ejecutor utilice los archivos simples `config_base.json` y `m2_config_base.json` incluidos en este paquete.

Para verificar o ejecutar solo M1 se mantienen:

```bash
python scripts/run_verification.py --out outputs/m1_verification
python run_m1.py --config config_base.json --out outputs/m1_example --repetitions 1
```

## Organización del código

| Componente | Función |
|---|---|
| `article9/config.py`, `network.py`, `attributes.py`, `scores.py`, `selection.py` | M1 y sus reglas originales |
| `article9/m2_config.py` | Parámetros ilustrativos y validación de M2 |
| `article9/event_random.py` | Sorteos reproducibles asociados a eventos |
| `article9/behavior.py` | Adopción, señal creíble, satisfacción, envío y capacidad |
| `article9/diffusion.py` | Secuencia mensual, mensajes simultáneos, estados y cascadas |
| `article9/m2_export.py` | Tablas, configuraciones y huellas de campañas |
| `run_m2.py` | Ejecución emparejada de políticas |
| `tests/test_acceptance.py` | Las 19 pruebas de M1 |
| `tests/test_m2.py` | Las 22 pruebas de M2 |
| `scripts/verify_m2.py` | Verificación conjunta e informe con evidencia |
| `docs/` | Especificaciones y documentación conservada de M1 |

M1 conserva su versión funcional 0.1.0. Los archivos de integración añaden el registro del código M2 y mantienen el ejecutor de verificación de M1 limitado a sus pruebas originales. M2 declara su versión 0.2.0 en `m2_config.py` y en las exportaciones.

## Reglas importantes

- Período 0: selección. Período 1: información directa y evaluación de seleccionados. WOM desde el período 2, siempre con al menos un período entre adopción y emisión.
- Cada emisor contacta una sola vez a cada vecino durante la campaña. Un receptor puede recibir recomendaciones de diferentes emisores.
- Cada receptor evalúa una vez por período con mensajes nuevos, usando la señal máxima actual y emisores distintos acumulados.
- Adopción no implica satisfacción y satisfacción no garantiza emisión.
- Un seleccionado que no adopta directamente puede adoptar después por WOM, heredando la cascada del recomendador.
- Los puntajes de selección y valores económicos latentes no entran en las reglas de adopción o satisfacción.
- El código de política no forma parte de las claves de los sorteos. El orden de las políticas o emisores no cambia las trayectorias comparables.
- La suma de `conversion_credit` cuenta adopciones WOM. No sumar `receiver_adopted_this_month` como si cada mensaje simultáneo originara un cliente independiente.

## Archivos de resultados

Cada repetición contiene `population/` con los insumos M1 comunes, y una carpeta por política con:

- `periods.csv`: conteos y fracciones mensuales, desde el período 0.
- `wom_events.csv`: cada mensaje, emisor, receptor, raíz, señal y atribución.
- `evaluations.csv`: probabilidad, sorteo y resultado de cada evaluación.
- `sender_months.csv`: capacidad, audiencia, sorteo y motivo de emisión o inactividad.
- `state_history.csv` y `final_states.csv`: estados de cada persona.
- `cascades.csv`: tamaño, profundidad, comunidades y emisores elegibles al cierre.
- `summary.csv` y `summary.json`: resultados finales y tiempos hasta umbrales.
- `config.json` y `manifest.json`: supuestos, semillas, entorno y huellas SHA-256.

Los CSV usan UTF-8, coma y punto decimal. Los valores no definidos quedan vacíos. Los ingresos y la utilidad no se rellenan con resultados ficticios: todavía no se calculan en M2.

## Interpretación

Los ejemplos base de verificación muestran una adopción final cercana a la saturación. Se registra esa alerta en el informe sin ajustar los parámetros para producir un ganador. Las 21 campañas comprueban integración y permiten inspeccionar trazas; tres repeticiones por política no establecen un ranking robusto.

Antes del experimento principal deben revisarse las trayectorias temporales y las sensibilidades. M3 incorporará ingresos, costos y atribución monetaria. La satisfacción de esta versión es una función simple de calidad y ajuste; todavía no hay experiencia repetida, aprendizaje, WOM negativo, fatiga ni cambios en la red.
