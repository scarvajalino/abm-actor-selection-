# Reach, Credibility, or Revenue?
**An Agent-Based Model of Strategic Actor Selection in Entrepreneurial Word of Mouth**  
Article 9 · The 22 Manuscripts – Season II · Universidad Nacional de Colombia, Sede de La Paz

¿Cómo cambia el desempeño de una campaña de boca a boca cuando un emprendimiento solo puede activar a 20 de los 600 actores de una red? Este modelo en Python compara siete políticas bajo ocho condiciones y distingue alcance, adopción e ingresos. Los líderes de ingresos previstos se seleccionan con información anterior a la campaña; su desempeño realizado se observa después. Los resultados describen el modelo bajo supuestos ilustrativos, sin calibración con datos de empresas.

## Cómo recorrer el repositorio

| Recurso | Qué contiene |
|---|---|
| [Código Python](Article_9_Principal_Python/article9/) | Red y atributos, selección de actores, difusión y cuentas económicas |
| [Especificaciones](Article_9_Principal_Python/docs/) | Definiciones de los módulos M1, M2 y M3 |
| [Protocolo principal](Article_9_Principal_Python/MAIN_README.md) | Condiciones, políticas, semillas, horizontes y comandos de reproducción |
| [Pruebas](Article_9_Principal_Python/tests/) y [validación archivada](Article_9_Principal_Python/validation/) | Pruebas del modelo y registros de la ejecución original |
| [Diccionario de datos](Article_9_Principal_Python/DATA_DICTIONARY_MAIN.md) | Campos, unidades y organización de las salidas |
| [Índice de la entrega en Drive](https://drive.google.com/file/d/1cPMziqq-xPuGRd-ES5-6MB0zGJg-ckYE/view) | Informe, tablas, figuras, diseño y 21 partes de datos; acceso sujeto a los permisos del proyecto |

## Reproducción

Desde la raíz del repositorio, en un entorno virtual de Python:

```bash
cd Article_9_Principal_Python
python -m pip install -r requirements-lock.txt -r requirements-pilot.txt
python -m pytest -q tests
```

Para consultar resultados sin repetir simulaciones, abre el informe o el paquete de análisis desde el índice. El experimento archivado comprende 5.600 campañas (8 condiciones × 7 políticas × 100 repeticiones); el horizonte principal es de 60 meses y la sensibilidad temporal se evalúa a 120. Los pilotos se documentan por separado. Para regenerar las salidas, sigue el protocolo principal y utiliza un directorio nuevo.

## Procedencia

La distribución de código original está en [Article_9_Principal_Codigo_Python_v1.0.zip](https://drive.google.com/file/d/1vcVoplEM91q91WKxclshf7jzN0tsxj0H/view). Se conservan sus rutas relativas para que los scripts y el manifiesto de integridad sean utilizables sin adaptar el código.
