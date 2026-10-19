# Bitácora de uso de IA — SafeSite-Agent

## 1. Herramientas de IA utilizadas

| Herramienta | Uso que se le dio |
|---|---|
| OpenCode (agente de código) | Asistente de programación durante gran parte del desarrollo del proyecto: EDA del dataset, re-split oficial, scripts de entrenamiento YOLO, núcleo del agente (`src/safesite/`), integración con WhatsApp Cloud API, panel web, suite de pruebas, aplicación de demostración con su contenedor Docker y publicación en la nube, y documentación técnica |
| Ultralytics YOLOv8 | **Componente del agente**, no herramienta de asistencia: red de detección entrenada por nosotros (épocas y semilla fijas, dataset Construction PPE) |

**No se usaron LLM** en ninguna parte del ciclo de decisión del agente: el razonamiento (umbrales por clase, confirmación temporal K=3, cooldown, consolidación de alertas en lote) está implementado con reglas deterministas escritas por nosotros en `src/safesite/razonamiento.py`.

## 2. Qué hizo la IA y qué hicimos nosotros

- **La IA (OpenCode) hizo:** acompañar gran parte del proceso de construcción. Escribió el código fuente a partir de especificaciones nuestras; ejecutó experimentos de entrenamiento y evaluación; midió y registró resultados; detectó el sesgo de etiquetas del dataset a partir de nuestra observación del panel en vivo; construyó la aplicación de demostración (interfaz Gradio, imagen Docker y despliegue en la nube) y generó borradores de documentación técnica. Todo su trabajo fue supervisado y revisado por nosotros antes de incorporarlo al repositorio.
- **Nosotros hicimos:** definir el problema, el diseño del agente y las medidas de desempeño; decidir en cada bifurcación del proyecto (qué modelo desplegar, qué medida reformular, cómo corregir el sesgo visual sin arriesgar las métricas validadas); crear la cuenta de Meta/WhatsApp y sus credenciales; probar el sistema en vivo con personas reales; y verificar cada resultado contra el enunciado del curso.

## 3. Decisiones más relevantes asistidas por IA

| Decisión | Papel de la IA |
|---|---|
| Re-split oficial del dataset para eliminar la contaminación train/test detectada en el análisis exploratorio | Propuso y ejecutó el re-split; nosotros validamos las cifras resultantes (train/val/test) antes de entrenar |
| Elegir el modelo de despliegue final entre los experimentos entrenados | Ejecutó la comparación de experimentos sobre la métrica de incidente; nosotros aplicamos el criterio pre-registrado y confirmamos la elección |
| Corregir las cajas de gafas ancladas por debajo del rostro (observación nuestra en el panel en vivo) | Midió el sesgo sobre las cajas del ground truth, identificó que era heredado del dataset fuente y calculó el anclaje anatómico calibrado; nosotros elegimos la corrección cosmética (sin reentrenar) para no arriesgar las métricas ya validadas |
| Suite de pruebas con medidas de desempeño pre-registradas | Implementó los escenarios y la recolección de logs a partir de los requisitos del enunciado; nosotros validamos los umbrales y los resultados |
| Aplicación de demostración publicada en la nube (contenedor con la demo completa, disponible en todo momento) | Construyó la interfaz, la imagen Docker y el flujo de publicación; nosotros elegimos la plataforma, configuramos el presupuesto y verificamos el despliegue con pruebas reales |
