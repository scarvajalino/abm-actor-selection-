# Article 9 M1 en Python

Módulo 0.1.0 de red sintética, atributos y selección de actores. Implementa la especificación M1 v0.1 con siete políticas y pruebas T01–T19. Es un ejercicio teórico no calibrado con datos reales.

## Inicio rápido

Se verificó con CPython 3.12.14. En una carpeta local, descomprima este paquete, abra una terminal y ejecute:

```bash
python -m venv .venv
# Linux o macOS
source .venv/bin/activate
# En Windows PowerShell, en lugar de la línea anterior
# .venv\Scripts\Activate.ps1
python -m pip install -r requirements-lock.txt
python scripts/run_verification.py --out outputs/verification
```

El último comando ejecuta 19 pruebas con pytest, exporta diez poblaciones de 600 personas y sus 70 selecciones, y genera informe Markdown, JSON, JUnit y registro de consola. El código de salida es cero únicamente si todas las pruebas pasan. Use una carpeta nueva/vacía de salida en cada ejecución.

Para una sola inicialización y las siete políticas:

```bash
python run_m1.py --out outputs/example --repetitions 1
```

Para diez inicializaciones usando una configuración explícita:

```bash
python run_m1.py --config config_base.json --out outputs/batch --repetitions 10
```

El archivo `config_base.json` incluido se puede editar para experimentos posteriores. El archivo de configuración ampliada y semillas entregado separadamente documenta la verificación; para `--config` utilice el objeto simple de `config_base.json`, no el manifiesto ampliado.

## Qué contiene

| Archivo o carpeta | Función |
|---|---|
| `article9/config.py` | Validación de tamaños, probabilidades, costos y ponderaciones |
| `article9/randomness.py` | Flujos PCG64 con identificadores estables |
| `article9/network.py` | Red fija de bloques estocásticos y tablas estructurales |
| `article9/attributes.py` | Atributos previos, valores latentes separados y estados iniciales |
| `article9/scores.py` | Puntajes previos sin resultados posteriores |
| `article9/selection.py` | Siete políticas, cuotas, empates y auditoría |
| `article9/diagnostics.py` | Red, audiencias potenciales, correlaciones y solapamiento |
| `article9/model.py` | Inicialización común y copias independientes de estados |
| `article9/export.py` | CSV, JSON, entorno y huellas SHA-256 |
| `run_m1.py` | Ejecución por configuración y repetición |
| `scripts/run_verification.py` | Verificación completa e informes |
| `tests/` | Casos manuales, extremos, invariantes y diez poblaciones |
| `docs/` | Copia de la especificación de referencia |

## Convenciones que deben conservarse

- Semilla maestra base: 20260925. Repeticiones de verificación: 0–9.
- Cada flujo se identifica por `[master_seed, repetition, component_id]`; los códigos están en `randomness.py` y las semillas se exportan en cada `config.json`.
- Personas 0–599, comunidades 0–5. Los identificadores se distribuyen entre grupos mediante una permutación reproducible.
- La función de selección recibe solamente una proyección de información previa. Nunca recibe valores latentes ni estados comerciales.
- Todas las políticas comparten población, costos y red dentro de una repetición. El orden de políticas no cambia los datos.
- El índice de ingresos previstos es un puntaje entre 0 y 1, no una predicción en moneda.
- `require_modular=False` permite controles extremos; no cambia el escenario base.
- Una red poco conectada produce una advertencia y se conserva. No se sortean redes de nuevo para eliminar resultados desfavorables.
- La audiencia potencial excluye a los propios actores seleccionados. No es alcance observado.
- Los ingresos del estado inicial son cero porque todavía no hay proceso comercial; no se exportan resultados ficticios de campaña.

## Salidas y comprobación

Cada directorio `rep_000`, `rep_001`, etc. contiene configuración, nodos, enlaces, valores latentes, selección, auditoría, estados iniciales, diagnósticos y un manifiesto. Los CSV emplean UTF-8, coma como separador y punto decimal. La modularidad sin enlaces y las correlaciones con variables constantes se representan como celdas vacías con una razón.

Las tablas `network_diagnostics_all.csv` y `policy_diagnostics_all.csv` se generan al verificar T19. El JSON de verificación contiene el resultado y la evidencia de cada prueba. El informe general no se duplica por repetición. Se preservan datos por réplica para que los promedios no reemplacen la inspección de realizaciones individuales.

## Alcance científico

Este paquete no implementa todavía adopción, satisfacción, difusión, compras, ingresos atribuidos ni resiliencia. Las diez inicializaciones no cuentan como campañas dentro de las 700 simulaciones previstas. Las diferencias entre políticas observadas en M1 son diferencias de selección y oportunidad estructural, no evidencia de desempeño comercial.

Los profesores deben revisar la plausibilidad de supuestos y escalas; Santiago puede reproducir los ejemplos, examinar las selecciones y documentar las decisiones. La siguiente etapa es especificar e implementar M2, manteniendo el mismo control de semillas y la separación entre información previa y resultados.

## Referencias de implementación

- [NumPy random sampling](https://numpy.org/doc/stable/reference/random/index.html)
- [NetworkX average clustering](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.cluster.average_clustering.html)
- [NetworkX modularity](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.community.quality.modularity.html)
