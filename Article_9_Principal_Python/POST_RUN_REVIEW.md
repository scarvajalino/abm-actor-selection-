# Revisión posterior a la ejecución

Las ecuaciones y los archivos originales de M3 no se cambiaron.

Una vez ejecutadas las 560 campañas y reconstruida la repetición 12, se endureció únicamente la creación del manifiesto de archivos en `run_horizon120.py`: la enumeración de todos los archivos presentes se sustituyó por `output_hashes`, una lista explícita de `campaigns.csv`, `monthly.csv`, `prefix_checks.csv` y `records.zip`. Así se excluye la autorreferencia de `completion.json` incluso si aparece una copia previa durante una recuperación.

La nueva prueba H06 comprueba esa exclusión. Las ocho pruebas iniciales de horizonte habían pasado antes de la ejecución; el conjunto final de 80 pruebas también pasó. El registro `source_manifest.json` conserva los hashes del código al iniciar las simulaciones; `recovery_log.json` registra los hashes posteriores del controlador y de sus pruebas. El manifiesto incluido en el paquete identifica la versión final entregada.

El analizador se mantuvo como se ejecutó. El informe entregado añade una conclusión interpretativa y una nota de recuperación escritas después de revisar los resultados, mientras las tablas, figuras y valores provienen del script. Volver a ejecutar el analizador reproduce esos valores y la parte automática del informe.

Los dos intentos de la repetición 12 conservan exactamente los mismos CSV de resultados; solo se reemplazó su archivo ZIP incompleto y se corrigió la autorreferencia en metadatos. La causa subyacente de estas incidencias de archivo no se ha establecido.
