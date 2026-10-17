# Bitácora de uso de IA — SafeSite-Agent

> Documento requerido por las condiciones de entrega del curso. Los dos integrantes de la pareja deben revisarlo, completar los espacios marcados y firmarlo con sus nombres antes de entregar.

## 1. Herramientas de IA utilizadas

| Herramienta | Uso que se le dio | Verificaron el resultado |
|---|---|---|
| OpenCode (agente de código, modelo GLM) | Asistente de programación durante TODO el desarrollo del proyecto: EDA del dataset, re-split oficial, scripts de entrenamiento YOLO, núcleo del agente (`src/safesite/`), WhatsApp Cloud API, panel web, suite de pruebas, documentación técnica | ☐ Sí, código revisado línea a línea antes de cada commit *(completar)* |
| Ultralytics YOLOv8 | **Componente del agente**, no herramienta de asistencia: red de detección entrenada por nosotros (100 épocas, seed 42) con el dataset Construction PPE | ☐ Sí, métricas reproducidas con la suite propia |

**No se usaron LLM** en ninguna parte del ciclo de decisión del agente: el razonamiento (umbrales por clase, confirmación temporal K=3, cooldown, consolidación de lotes) está implementado con reglas deterministas escritas por nosotros en `src/safesite/razonamiento.py`. No se usó IA generativa para redactar el documento de diseño ni la matriz de decisión *(completar/ajustar según la realidad de cada integrante)*.

## 2. Qué hizo la IA y qué hicimos nosotros

- **La IA (agente de código) hizo:** escribir el código fuente a partir de especificaciones nuestras; ejecutar experimentos; medir y registrar resultados; detectar el sesgo de etiquetas del dataset (E30) a partir de nuestra observación del panel en vivo; generar borradores de documentación técnica (MATRIZ_DECISION, TABLA_CAMBIOS, DESARROLLO_AGENTE, GUION_VIDEO).
- **Nosotros hicimos:** definir el problema, el diseño del agente y las medidas de desempeño (Tarea 2); decidir en cada bifurcación del proyecto (qué modelo desplegar, qué measure reformular, cómo corregir el sesgo visual — opción cosmética vs. reentrenar); crear la cuenta de Meta/WhatsApp y las credenciales; probar el sistema en vivo con personas reales (E28); verificar cada resultado contra el enunciado; *(completar: reparto real dentro de la pareja)*.
- **Trazabilidad:** cada interacción relevante quedó registrada en `Documentation/BITACORA.md` (E1–E31): fecha, comando exacto, semillas, duración, resultados y decisión tomada.

## 3. Prompts/decisiones más relevantes asistidas por IA

| Fecha | Decisión | Papel de la IA |
|---|---|---|
| oct-2026 (E12) | Re-split oficial del dataset para eliminar contaminación train/test | Propuso y ejecutó el re-split tras el hallazgo del EDA; nosotros validamos las cifras (1,130/143/140) |
| oct-2026 (E23) | Elegir `tuned_v2_s` como checkpoint de despliegue | Ejecutó la comparación de experimentos; nosotros aplicamos el criterio pre-registrado (recall de incidente) |
| oct-2026 (E30) | Corregir cajas de gafas "a nivel de la boca" (observación nuestra) | Midió el sesgo en 509/405 cajas del GT, identificó que era heredado del dataset fuente y calculó el anclaje anatómico calibrado; nosotros elegimos la opción cosmética (sin reentrenar) para no arriesgar las métricas validadas |
| oct-2026 (E31) | Suite de pruebas de la Fase 3 | Implementó la suite a partir de los requisitos del enunciado; nosotros validamos los umbrales pre-registrados y los resultados |

## 4. Declaración

Declaramos que el uso de IA estuvo limitado a lo descrito arriba, que entendemos el funcionamiento de todo el código entregado y que las pruebas reportadas fueron ejecutadas por nosotros sobre este repositorio, con sus logs disponibles en `runs/agente/pruebas/`.

- Integrante 1: William David Lozano Julio — T00078475 — Firma: _________
- Integrante 2: Cristian Matteo Benitez Montes — T00078658 — Firma: _________
