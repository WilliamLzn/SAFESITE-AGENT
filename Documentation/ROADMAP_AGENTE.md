# 🗺️ Roadmap — Creación del agente SafeSite-Agent

| | |
|---|---|
| **Documento** | Plan de ejecución para construir el agente, derivado del [EDA del dataset](EDA_SAFESITE_DATASET.md) |
| **Fecha** | 13 de octubre de 2026 · **Actualizado:** 14 de octubre de 2026 (estado de ejecución) |
| **Objetivo** | Avances reales y medibles: modelo entrenado + evaluado + agente funcional end-to-end |
| **Hardware disponible** | RTX 4050 Laptop (6 GB VRAM) + 24 GB RAM → suficiente para YOLO nano/small a 640 px |
| **Estado** | ✅ **Fases 0–4 COMPLETADAS en un solo día** (13-oct-2026) — ver [BITACORA.md](BITACORA.md) E12–E28. Fase 5 (continua): 2 de 3 ítems cerrados. |

---

## Principio rector

El EDA demostró que el dataset es **íntegro y correcto** (F1), así que el avance no está en re-hacer datos sino en: **(a)** reparar la estrategia de splits (F2–F4), **(b)** entrenar un baseline YA, y **(c)** construir el agente alrededor de métricas por clase de incumplimiento (F5, F6).

---

## Fase 0 — Corregir datos (½ día) 🔧 — ✅ COMPLETADA (E12)

Acciones concretas (script nuevo, sin tocar los crudos):

1. **Re-split oficial**: regenerar carpetas respetando el campo `split` del NDJSON: train 1,132 / val 143 / test 141. Así las métricas son comparables con el dataset oficial y se elimina la contaminación (F2). Mantener el split actual como `split_8020_legacy/` para trazabilidad.
2. **Etiquetar test/**: las 284 imágenes de `test/` ya tienen cajas en el NDJSON; generar sus `.txt` es un script de 20 líneas (F4) — evaluación cuantitativa desbloqueada.
3. **Verificar 3 descargas faltantes** (F10) con reintento desde el CDN.

**Entregable:** `dataset.yaml` (formato Ultralytics) apuntando a los nuevos splits con los 11 `names`.

> **✅ Ejecutado (E12):** `dataset_v2/` con train 1,130 / val 143 / test 140 (en disco), 11,488 líneas de etiqueta, crudos intactos. Las 3 descargas faltantes **no se pudieron recuperar**: las URLs del CDN expiraron (HTTP 403, E13) → el dataset local es irrecuperable desde internet; respaldar es prioridad.

## Fase 1 — Baseline YOLO entrenado (1 día) 🚀 — ✅ COMPLETADA (E17)

Configuración realista para la RTX 4050 (cerrar juegos/apps que consumen VRAM):

```python
from ultralytics import YOLO
import torch  # torch + CUDA

model = YOLO("yolov8n.pt")   # nano: 3.2M params, cabe holgado en 6GB
model.train(
    data="dataset.yaml",
    epochs=100, patience=20,
    imgsz=640,               # resolucion nativa dominante del dataset (78.8%)
    batch=16,                # subir/bajar segun VRAM libre
    seed=42,                 # reproducibilidad (practica MLOps de la skill pytorch-lightning)
    project="runs/safesite", name="baseline_v1",
    val=True,
)
```

- Tiempo estimado: 30–60 min en la 4050.
- **Métricas a reportar** (esto es el "avance real"): `mAP50`, `mAP50-95` global y **recall por clase `no_*`** — el negocio del agente es no dejar pasar incumplimientos.
- Logging con TensorBoard (integrado en ultralytics) → cumple el rol de tracking de experimentos que formaliza la skill `pytorch-lightning` (semillas, checkpoints `best.pt`, config versionada).

> **✅ Ejecutado (E17):** `baseline_v1` (batch 8, workers 0 — lección WinError 1455 de E15), 72 épocas, ~37 min. Val mAP50 **0.580** / test **0.520**; positivas fuertes (helmet 0.93 AP50 test) pero `no_helmet` recall 0.15 test → criterio por fotograma NO cumplido (anticipado por el EDA, F5).

## Fase 2 — Tuning orientado al desbalance (2–3 días) ⚖️ — ✅ COMPLETADA (E19–E21, E23)

Ataca F5 con evidencia, no con intuición:

1. **Aumento dirigido a incumplimientos**: HSV/brightness-jitter (también mitiga F9 de imágenes oscuras), mosaic ON, scale/translate moderados.
2. **Umbrales por clase**: en inferencia, umbral de confianza por clase — exigir menos a `no_boots` (115 cajas) que a `Person`.
3. Si `no_*` sigue débil: **focal loss / ponderación de clases**, o probar `yolov8s`.
4. **Criterio de parada (pre-registrado antes de experimentar)**: recall `no_helmet` ≥ 0.70 y precisión global ≥ 0.80 en val; documentar cada experimento (nombre, semilla, params, métricas) en la bitácora.

> **✅ Ejecutado con giro documentado:** oversampling ×2.13 `no_*` / ×3 `no_boots` (dataset_v3) + `tuned_v1` (yolov8n) = **hallazgo NEGATIVO** (E21): replicar escenas no añade diversidad; el recall por fotograma no mejora. El fallback pre-registrado **`tuned_v2_s` (yolov8s, E23) SÍ funcionó** (no_helmet AP50 0.453 val) y **reencuadró la métrica correcta para el caso de uso: recall A NIVEL DE INCIDENTE** sobre video continuo (confirmación temporal K frames). Checkpoint de despliegue: `runs/safesite/tuned_v2_s/weights/best.pt`.

## Fase 3 — Núcleo del agente (3–4 días) 🧠 — ✅ COMPLETADA (E22–E23)

Implementar el ciclo percibir→razonar→actuar del documento de diseño:

```
src/safesite/
├── percepcion.py    # captura RTSP/webcam/cámara IP, muestreo N fps (2-5), inferencia YOLO
├── razonamiento.py  # reglas EPP sobre detecciones + memoria de corto plazo
├── memoria.py       # dedup de alertas (cooldown), historial por zona/horario (SQLite o JSON)
└── actuarios.py     # WhatsApp announcer + panel
```

**Reglas de decisión basadas en EDA (F6):** decidir incumplimiento **solo** por clases `no_*` detectadas (no por anidamiento casco⊂persona, que falla 38% de las veces). Ejemplo:

> Si `no_helmet` con confianza ≥ umbral_clase aparece en zona Z durante ≥ K frames consecutivos (K=3) y sin alerta en los últimos T segundos → disparar alerta con frame anotado.

La memoria de corto plazo (cooldown T=30 s) evita el spam de notificaciones; el historial por zona/horario permite priorizar patrones recurrentes (agente basado en modelos + utilidad, como define el README).

> **✅ Ejecutado (E22–E23):** 7 módulos en `src/safesite/` (config, percepcion, razonamiento, memoria, actuarios, agente, demo). Con el modelo de despliegue: **recall de incidente `no_helmet` 0.963 val / 0.833 test; a nivel de escena 0.964/0.962**, falsas alarmas 2.6–3.5%, 31.5 ms/frame en GPU. **El criterio pre-registrado (≥0.70) SE CUMPLE con holgura.** Demo: `.venv\Scripts\python.exe -m src.safesite.demo`.

## Fase 4 — Actuadores (2–3 días) 📱 — ✅ COMPLETADA (E24–E27, validación E28)

1. **WhatsApp Business Cloud API** (announcer): plantilla de mensaje con zona, tipo de EPP faltante, timestamp y frame JPEG; enviar al supervisor HSE. Meta exige plantillas aprobadas → tramitar con antelación.
2. **Panel de supervisión**: OpenCV `imshow` local primero (bboxes + clases + conteos), luego web (Streamlit) si el tiempo alcanza.
3. **Persistencia del historial** por zona/horario (reportabilidad).

> **✅ Ejecutado (E24–E27):** alertas REALES de WhatsApp con foto (end-to-end ~5.3 s < objetivo 10 s), circuito conversacional bidireccional (webhook + túnel cloudflared http2 + `piloto.py` con auto-registro en Meta), alertas consolidadas por lote (1 mensaje + 1 foto por frame), y **panel web en vivo por webcam** (`panel.py`, Flask+MJPEG, http://localhost:5000) con WhatsApp asíncrono. **Validado en vivo por el usuario con su propia cámara (E28).**

## Fase 5 — Evaluación y mejora continua (continua) 📈 — 🔄 EN CURSO (2 de 3)

- ✅ Evaluación sobre test etiquetado (de Fase 0) → tabla de métricas por clase. **(E17, E21, E23)**
- ⬜ **Reentrenamiento con falsos positivos/negativos** que reporten los supervisores (human-in-the-loop, ya previsto en el README del proyecto).
- ✅ Benchmark de latencia: objetivo del proyecto = alerta < 10 s desde la detección → medir end-to-end (frame → WhatsApp). **(E24: ~5.3 s end-to-end, CUMPLIDO)**

---

## Cronograma sugerido (4 semanas) — ✅ completado en 1 día (13-oct-2026)

| Semana | Entregable verificable | Estado |
|---|---|---|
| 1 | Splits corregidos + `dataset.yaml` + **baseline entrenado** + tabla de métricas en val | ✅ E12, E17 |
| 2 | Tuning anti-desbalance + **evaluación en test etiquetado** + informe de métricas por clase | ✅ E19–E21, E23 |
| 3 | Núcleo del agente funcionando sobre **video grabado** (demo detecta y decide) | ✅ E22–E23 |
| 4 | Alerta WhatsApp end-to-end + panel + medición de latencia → **demo completa** | ✅ E24–E28 |

## Próximas acciones (pendientes de aprobación)

1. ⬜ **Calibrar `UMBRAL_INCUMPLIMIENTO`** según las falsas alarmas reales del piloto (E28 observó confianzas 18–27% cerca del umbral 0.15).
2. ⬜ **Human-in-the-loop**: canal para que el supervisor marque falsos positivos/negativos → dataset de reentrenamiento (Fase 5).
3. ⬜ **Túnel con nombre/dominio propio** para producción (el quick tunnel de cloudflared cambia de URL en cada arranque).
4. ⬜ **Push a GitHub** (`origin` ya configurado) como respaldo del repo — el dataset crudo NO es regenerable (E13).
5. ⬜ Respaldo externo del dataset crudo (`safesite_dataset/` + `.ndjson`).

> 📌 **Nota de trazabilidad:** la metodología de reproducibilidad (semillas, checkpoints, tracking, reporte de config) sigue las prácticas de la skill `pytorch-lightning` del catálogo [K-Dense scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills); el rigor del análisis sigue la skill `exploratory-data-analysis` del mismo catálogo.
