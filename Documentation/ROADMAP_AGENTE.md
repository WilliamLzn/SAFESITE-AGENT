# 🗺️ Roadmap — Creación del agente SafeSite-Agent

| | |
|---|---|
| **Documento** | Plan de ejecución para construir el agente, derivado del [EDA del dataset](EDA_SAFESITE_DATASET.md) |
| **Fecha** | 13 de octubre de 2026 |
| **Objetivo** | Avances reales y medibles: modelo entrenado + evaluado + agente funcional end-to-end |
| **Hardware disponible** | RTX 4050 Laptop (6 GB VRAM) + 24 GB RAM → suficiente para YOLO nano/small a 640 px |

---

## Principio rector

El EDA demostró que el dataset es **íntegro y correcto** (F1), así que el avance no está en re-hacer datos sino en: **(a)** reparar la estrategia de splits (F2–F4), **(b)** entrenar un baseline YA, y **(c)** construir el agente alrededor de métricas por clase de incumplimiento (F5, F6).

---

## Fase 0 — Corregir datos (½ día) 🔧

Acciones concretas (script nuevo, sin tocar los crudos):

1. **Re-split oficial**: regenerar carpetas respetando el campo `split` del NDJSON: train 1,132 / val 143 / test 141. Así las métricas son comparables con el dataset oficial y se elimina la contaminación (F2). Mantener el split actual como `split_8020_legacy/` para trazabilidad.
2. **Etiquetar test/**: las 284 imágenes de `test/` ya tienen cajas en el NDJSON; generar sus `.txt` es un script de 20 líneas (F4) — evaluación cuantitativa desbloqueada.
3. **Verificar 3 descargas faltantes** (F10) con reintento desde el CDN.

**Entregable:** `dataset.yaml` (formato Ultralytics) apuntando a los nuevos splits con los 11 `names`.

## Fase 1 — Baseline YOLO entrenado (1 día) 🚀

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

## Fase 2 — Tuning orientado al desbalance (2–3 días) ⚖️

Ataca F5 con evidencia, no con intuición:

1. **Aumento dirigido a incumplimientos**: HSV/brightness-jitter (también mitiga F9 de imágenes oscuras), mosaic ON, scale/translate moderados.
2. **Umbrales por clase**: en inferencia, umbral de confianza por clase — exigir menos a `no_boots` (115 cajas) que a `Person`.
3. Si `no_*` sigue débil: **focal loss / ponderación de clases**, o probar `yolov8s`.
4. **Criterio de parada (pre-registrado antes de experimentar)**: recall `no_helmet` ≥ 0.70 y precisión global ≥ 0.80 en val; documentar cada experimento (nombre, semilla, params, métricas) en la bitácora.

## Fase 3 — Núcleo del agente (3–4 días) 🧠

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

## Fase 4 — Actuadores (2–3 días) 📱

1. **WhatsApp Business Cloud API** (announcer): plantilla de mensaje con zona, tipo de EPP faltante, timestamp y frame JPEG; enviar al supervisor HSE. Meta exige plantillas aprobadas → tramitar con antelación.
2. **Panel de supervisión**: OpenCV `imshow` local primero (bboxes + clases + conteo), luego web (Streamlit) si el tiempo alcanza.
3. **Persistencia del historial** por zona/horario (reportabilidad).

## Fase 5 — Evaluación y mejora continua (continua) 📈

- Evaluación sobre test etiquetado (de Fase 0) → tabla de métricas por clase.
- **Reentrenamiento con falsos positivos/negativos** que reporten los supervisores (human-in-the-loop, ya previsto en el README del proyecto).
- Benchmark de latencia: objetivo del proyecto = alerta < 10 s desde la detección → medir end-to-end (frame → WhatsApp).

---

## Cronograma sugerido (4 semanas)

| Semana | Entregable verificable |
|---|---|
| 1 | Splits corregidos + `dataset.yaml` + **baseline entrenado** + tabla de métricas en val |
| 2 | Tuning anti-desbalance + **evaluación en test etiquetado** + informe de métricas por clase |
| 3 | Núcleo del agente funcionando sobre **video grabado** (demo detecta y decide) |
| 4 | Alerta WhatsApp end-to-end + panel + medición de latencia → **demo completa** |

## Próximas acciones inmediatas (hoy)

1. ✅ EDA completado (este documento + [informe](EDA_SAFESITE_DATASET.md)).
2. ⬜ Script `06_reSplit_oficial.py`: re-split + etiquetado de test + `dataset.yaml`.
3. ⬜ Instalar `ultralytics` (+ PyTorch CUDA) y entrenar `baseline_v1` con seed 42.
4. ⬜ Registrar métricas de `baseline_v1` en la [bitácora](BITACORA.md) y decidir el tuning de la Fase 2 con datos.

> 📌 **Nota de trazabilidad:** la metodología de reproducibilidad (semillas, checkpoints, tracking, reporte de config) sigue las prácticas de la skill `pytorch-lightning` del catálogo [K-Dense scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills); el rigor del análisis sigue la skill `exploratory-data-analysis` del mismo catálogo.
