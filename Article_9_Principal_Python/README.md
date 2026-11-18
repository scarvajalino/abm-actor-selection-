# Artículo 9: M1, M2 y M3 en Python

Paquete reproducible de red y selección (M1 v0.1), difusión (M2 v0.2) y economía (M3 v0.3). Los supuestos son teóricos, sin calibración empírica. No se presupone una política ganadora.

## Ejecución

Probado con Python 3.12.14. Instalar las versiones fijadas:

```bash
python -m pip install -r requirements-lock.txt
python run_m3.py --m1-config config_base.json --m2-config m2_config_base.json --m3-config m3_config_base.json --repetitions 3 --out outputs/m3_campaigns
```

Base: 600 personas, seis comunidades, 20 seleccionados, siete políticas y 60 meses. Tres repeticiones producen 21 campañas emparejadas, sin constituir el experimento principal. Usar una carpeta nueva o vacía. Por repetición se guardan `population/` y `<politica>/m2/`, `<politica>/m3/`. `summary_all.csv` compara campañas. `run_m1.py` y `run_m2.py` siguen disponibles.

## Pruebas y evidencia

```bash
python scripts/verify_m3.py --out outputs/m3_verification
```

Ejecuta 63 pruebas: 19 M1, 22 M2 y 22 M3. Conserva JUnit, JSON, informe, 21 campañas base y seis comprobaciones adicionales de recompra y atribución. Los casos pequeños tienen resultados manuales; las campañas usan sorteos normales. Para probar sin conservar el paquete completo de evidencia: `python -m pytest -q`.

## Reglas económicas

- Una compra inicial por adopción, valorada con el valor latente de M1.
- Activación en mes 0 para cada seleccionado, incluso si rechaza.
- Servicio: 20% de la compra; recompra desactivada en la base.
- Recompra opcional desde el mes posterior a adoptar, con probabilidad igual a intensidad base por satisfacción, solo para satisfechos.
- Vistas separadas por comprador, padre, raíz y reparto ponderado. Conservan los ingresos y no se suman entre sí.
- Evaluación de líderes dentro de los seleccionados: precisión, recall, Spearman y error de rango. No se infiere el rendimiento contrafactual de no seleccionados.

Los valores son unidades monetarias abstractas. Con costos base, utilidad = 0,8 × ingresos − 20; ambos rankings coinciden por construcción. α cambia el crédito ponderado, no el resultado de la empresa ni el ranking de raíces usado para evaluar predicción.

## Documentación

- `docs/Article_9_Especificacion_minima_M1_v0.1.md`
- `docs/Article_9_M2_Especificacion_v0.2.md`
- `docs/Article_9_M3_Especificacion_v0.3.md`
- `docs/README_M1.md` y `docs/README_M2.md` preservan alcances anteriores.

M3 conserva las reglas y parámetros de M2. Las 21 campañas previas terminaron con 589–598 adoptantes de 600. Antes del experimento principal corresponde un piloto de sensibilidad y revisión de trayectorias. Tres repeticiones no justifican un ranking robusto de políticas.
