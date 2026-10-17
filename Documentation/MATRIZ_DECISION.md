# Fase 1 — Selección justificada del agente

**Curso:** Inteligencia Artificial — Universidad Tecnológica de Bolívar
**Pareja:** William David Lozano Julio (T00078475) · Cristian Matteo Benitez Montes (T00078658)
**Fecha de la decisión:** octubre de 2026

La pareja recibió dos agentes diseñados en la Tarea 2:

- **Agente A — SAFESITE-AGENT** (Lozano): monitoreo de uso de EPP en obra mediante video + YOLO + alertas por WhatsApp.
- **Agente B — PredictMaint-Agent** (Benitez): mantenimiento predictivo industrial con sensores de vibración/temperatura/presión/corriente y generación automática de órdenes de trabajo.

Los criterios y pesos se definieron **antes** de puntuar, siguiendo la plantilla del enunciado.

## Paso 1 — Criterios y pesos

| Criterio | Peso (w) | Justificación del peso |
|---|---:|---|
| Viabilidad técnica | 25 % | Es el criterio más determinante en un curso de un corte: un agente que no corre no genera evidencia medible. |
| Disponibilidad de datos o entorno | 20 % | Sin datos/entorno reales o simulables no hay pruebas objetivas (Fase 3 obligatoria). |
| Medibilidad del desempeño | 20 % | El enunciado exige convertir cada medida SMART en una prueba numérica; una medida no probable invalida la Fase 3. |
| Complejidad de IA | 15 % | El agente debe exigir razonamiento real, no solo condicionales (Russell y Norvig). |
| Costo y recursos | 10 % | Presupuesto estudiantil: hardware, APIs pagas y sensores cuentan. |
| Valor del problema | 10 % | Utilidad real para un usuario identificable. |
| **Total** | **100 %** | |

## Paso 2 y 3 — Puntuación con evidencia y puntaje ponderado

Escala 1–5 por criterio. **Cada puntaje lleva su frase de evidencia** (un puntaje sin evidencia no cuenta, según el enunciado).

| Criterio | w | A: SAFESITE | A: evidencia | B: PredictMaint | B: evidencia | w·A | w·B |
|---|---:|---:|---|---:|---|---:|---:|
| Viabilidad técnica | 0.25 | **5** | 100 % de los componentes del diseño ya están implementados y funcionando end-to-end: percepción YOLOv8s (31.5 ms/frame en GPU), razonamiento temporal (K=3 frames + cooldown), WhatsApp Business Cloud bidireccional con foto y panel web en vivo (bitácora E22–E28). | **2** | Requiere 4 tipos de sensores físicos (acelerómetro, termopar, transductor de presión, pinza amperimétrica) que la pareja no posee; todo el entorno debería simularse y el modelo de pronóstico está diseñado pero sin implementar (0 componentes corriendo). | 1.25 | 0.50 |
| Disponibilidad de datos o entorno | 0.20 | **5** | Dataset Ultralytics *Construction PPE* (1,416 imágenes reales de obra) descargado, re-split oficial validado (`dataset_v2`) y entrenado; las cámaras se sustituyen por webcam real, ya validada en vivo (E28). | **3** | El dataset AI4I 2020 (UCI) existe y es descargable, pero es sintético, no contiene series temporales reales ni un historial de 12 meses de una línea piloto. | 1.00 | 0.60 |
| Medibilidad del desempeño | 0.20 | **5** | La medida reformulada (recall de incidente ≥ 0.70 a nivel de escena) ya está medida: 96.3 % val / 96.2 % test; la alerta < 10 s está medida: ciclo completo en vivo ~2.6 s (E24: envío HTTP 1.9 s). Umbrales pre-registrados en bitácora antes de las pruebas. | **2** | Su medida SMART central ("anticipar ≥ 70 % de las fallas con ≥ 48 h de antelación sobre el historial de 12 meses") no es probable con AI4I 2020: el dataset no tiene marcas de tiempo ni etiquetas de momento de falla; habría que reformular la medida por completo antes de poder probar nada. | 1.00 | 0.40 |
| Complejidad de IA | 0.15 | **4** | Agente basado en modelos con componente de utilidad (Russell y Norvig): percepción aprendida (YOLO, redes neuronales), estado interno (rachas + cooldown + historial) y reglas; no es un reflejo simple porque la decisión depende de la historia reciente. | **4** | Diseño basado en utilidad con aprendizaje: detección de anomalías entrenada con historial, ponderación de costos de falsos positivos/negativos y reentrenamiento con retroalimentación; razonamiento genuino, también. | 0.60 | 0.60 |
| Costo y recursos | 0.10 | **5** | Costo total en el corte: $0 COP — entrenamiento e inferencia en la GPU local (RTX 4050), Ultralytics open source, túnel cloudflared gratuito y tier de prueba de WhatsApp Cloud API gratuito. | **4** | El software (scikit-learn, pandas) es gratuito, pero los sensores industriales reales sí tienen costo y en su ausencia habría que simularlos. | 0.50 | 0.40 |
| Valor del problema | 0.10 | **5** | La construcción es uno de los sectores con más accidentalidad laboral; usuario identificable: supervisor HSE de obra; beneficio: detección continua de incumplimientos de EPP que un supervisor humano no puede observar en simultáneo. | **4** | Paradas de producción no planificadas y sobrecostos de reparación; usuario: equipo de mantenimiento; problema real, aunque el piloto físico no está al alcance de la pareja. | 0.50 | 0.40 |
| **Puntaje ponderado S** | **1.00** | | | | | **4.85** | **2.90** |

**S(SAFESITE-AGENT) = 4.85** · **S(PredictMaint-Agent) = 2.90** → **se elige SAFESITE-AGENT** (agente A).

## Paso 4 — Análisis de sensibilidad

El criterio más influyente es *Viabilidad técnica* (w = 0.25). Se varía ±10 puntos porcentuales (0.35 / 0.15), compensando en *Disponibilidad de datos* (0.10 / 0.30):

| Variación | S(SAFESITE) | S(PredictMaint) | ¿Cambia la decisión? |
|---|---:|---:|---|
| Viabilidad 35 % (datos 10 %) | 4.85 | 2.80 | No |
| Viabilidad 15 % (datos 30 %) | 4.85 | 3.00 | No |

SAFESITE obtiene 5 en todos los criterios excepto en complejidad (4 vs 4, empate), por lo que cualquier redistribución de pesos mantiene la decisión. Además, la brecha (4.85 − 2.90 = 1.95) es casi cuatro veces mayor que la máxima variación producida por la sensibilidad (±0.10). **La decisión es robusta.**

## Paso 5 — Justificación (una página)

Se elige **SAFESITE-AGENT** con un puntaje ponderado de **4.85 frente a 2.90**. La decisión no se tomó por preferencia: se construyó a partir de tres hechos verificables. Primero, la viabilidad técnica: el agente A ya está implementado de punta a punta (percepción con YOLOv8s, razonamiento temporal con confirmación de K frames y cooldown, alertas reales por WhatsApp Business con foto, panel web con detección en vivo por webcam), mientras que el agente B requeriría sensores industriales que la pareja no tiene, obligando a simular hasta el entorno completo. Segundo, la medibilidad: las medidas de desempeño del agente A, reformuladas y documentadas, ya producen números — recall de incidente de 96.3 % en validación (umbral pre-registrado ≥ 70 %) y ciclo de alerta de ~2.6 s medido en vivo (objetivo < 10 s) — mientras que la medida central del agente B (anticipar fallas 48 horas antes, sobre un historial de 12 meses) no puede probarse con el dataset AI4I 2020, que es sintético y no contiene marcas de tiempo. Tercero, la disponibilidad de datos: el dataset Construction PPE ya está descargado, re-splitado y entrenado, mientras que el entorno del agente B tendría que inventarse.

El análisis de sensibilidad confirma que la decisión es robusta: moviendo ±10 puntos el criterio más influyente, la brecha a favor de SAFESITE se mantiene (4.85 vs 2.80–3.00).

**Qué perdemos al descartar PredictMaint-Agent:** la clasificación teóricamente más pura de agente basado en utilidad con aprendizaje (la utilidad de A es un componente, no el núcleo), el dominio IoT industrial con sensores físicos y una medida de desempeño orientada a costos económicos. Lo ganado a cambio: un agente real, corriendo, conectado al mundo físico por webcam y a un canal de comunicación real, con evidencia medible y trazable para las tres fases de esta entrega. En un curso cuyo entregable exige demostración y pruebas, esa diferencia es la decisión.
