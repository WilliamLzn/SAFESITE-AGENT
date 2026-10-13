# AGENTS.md — Convenciones para agentes de IA en este repositorio

**Proyecto:** SAFESITE-AGENT — agente de monitoreo de EPP en obra (detección YOLO + reglas + WhatsApp).
**Idioma de trabajo:** español (documentación, commits, informes).

## Mapa del repositorio

```
SAFESITE-AGENT/
├── AGENTS.md                      # este archivo
├── README.md                      # visión del proyecto y del agente
├── construction-ppe.ndjson        # metadatos oficiales del dataset (11 clases, 1,416 imágenes)
├── image_downloader.py            # pipeline de descarga + etiquetas YOLO (OBSOLETO: sus URLs CDN expiraron — ver BITACORA E13)
├── safesite_dataset/              # DATO CRUDO: train/ (1,129 jpg+txt) y test/ (284 jpg)
├── dataset_v2/                    # re-split OFICIAL para entrenar (1,413 imgs; images/+labels/+dataset.yaml)
├── eda/                           # análisis derivados (scripts + salidas + figuras)
│   ├── 01…06_*.py                 # scripts del EDA + re-split oficial (reproducibles, seed 42)
│   ├── salidas/                   # resumen_eda.json, resumen_imagenes.json, resumen_fase0.json, metricas_baseline_v1.json
│   └── figuras/                   # fig1…fig6 *.png
├── src/
│   └── entrenamiento/
│       └── entrenar_baseline.py   # entrenamiento YOLOv8n (seed 42, workers=0 en Windows, ver BITACORA E15)
├── runs/
│   ├── safesite/baseline_v1/      # RUN COMPLETO: best.pt, results.csv, confusion_matrix.png, args.yaml
│   └── detect/val{,-2}            # plots de evaluación val/test
├── Documentation/
│   ├── EDA_SAFESITE_DATASET.md    # informe EDA (hallazgos F1–F10)
│   ├── ROADMAP_AGENTE.md          # plan de ejecución del agente (Fases 0–5)
│   ├── SKILLS.md                  # skills instaladas y su procedencia
│   ├── BITACORA.md                # registro de ejecuciones y resultados (¡mantener al día!)
│   └── Diseño_Agente_SafeSite.pdf # documento académico de diseño
├── .venv/                         # entorno de entrenamiento: torch 2.14.1+cu130 + ultralytics 8.4.176
└── .opencode/skills/              # skills instaladas (exploratory-data-analysis, pytorch-lightning)
```

## Reglas no negociables

1. **Datos crudos en solo lectura:** no modificar, mover ni borrar nada dentro de `safesite_dataset/` ni el `.ndjson` sin confirmación explícita del usuario. Todo artefacto nuevo (splits, etiquetas regeneradas, informes) se escribe en carpetas derivadas (`eda/`, `dataset_v2/`, etc.).
2. **Bitácora obligatoria:** cada ejecución relevante (entrenamiento, evaluación, cambio de datos) se registra en `Documentation/BITACORA.md` con fecha, comando exacto, semillas y resultados.
3. **Reproducibilidad:** semilla fija (42 por defecto) en todo muestreo/entrenamiento; reportar versiones de librerías clave en resultados.
4. **Trazabilidad de experimentos:** cada entrenamiento lleva nombre (`baseline_v1`, …), config guardada y métricas por clase (`no_*` incluidas), siguiendo las prácticas de la skill `pytorch-lightning`.

## Skills disponibles (cargarlas cuando aplique)

| ID | Cuándo usarla |
|---|---|
| `exploratory-data-analysis` | Antes de modelar o al inspeccionar datos nuevos; contratos: solo lectura, alcances reportados, hallazgos exploratorios marcados |
| `pytorch-lightning` | Entrenamiento/reproducibilidad/tracking (MLflow, TensorBoard, W&B), checkpoints, criterios de parada |

Documentación completa de las skills (procedencia, licencias, contenido): `Documentation/SKILLS.md`.

## Estado actual y contexto clave (leer antes de trabajar)

- **Fase 0 y Fase 1 del roadmap COMPLETADAS** (13-oct-2026). Resumen:
  - `dataset_v2/` = re-split OFICIAL (corrige contaminación F2–F4 del EDA): train 1,130 / val 143 / test 140, todo etiquetado. `safesite_dataset/` queda como respaldo crudo (sus URLs CDN expiraron — **no es regenerable desde internet**).
  - **baseline_v1 entrenado** (YOLOv8n, batch 8, workers 0, seed 42, 72 épocas, ~37 min, `runs/safesite/baseline_v1/weights/best.pt`): val mAP50 **0.580** / test mAP50 **0.520**. Clases positivas fuertes (helmet AP50 0.93 en test) pero **`no_*` débiles** (recall `no_helmet` 0.47 val / 0.15 test) → **criterio pre-registrado NO cumplido**, tal como anticipó el EDA (hallazgo F5).
  - Inferencia: ~5.4 ms/imagen en la RTX 4050 → percepción sobrada para el objetivo de alerta <10 s.
- Hallazgos del EDA que siguen vigentes para todo trabajo futuro:
  - Etiquetas YOLO correctas (formato centro verificado, 0 discrepancias) — no regenerar.
  - Desbalance severo en `no_*` (solo 20.3% de imágenes de train con incumplimiento) — evaluar siempre **recall por clase `no_*`**; soporte de `no_boots` en val es de 4 instancias (métricas poco fiables).
  - La regla "casco anidado en persona" falla 38.2% — las decisiones del agente usan las clases `no_*` explícitas.
- **Fase 2 COMPLETADA (E21–E23):** la replicación de datos (dataset_v3) no subió el recall por fotograma con yolov8n (hallazgo negativo), PERO con **yolov8s** sí funcionó: el límite era parcialmente capacidad del modelo. **Checkpoint de despliegue (P8): `runs/safesite/tuned_v2_s/weights/best.pt`** — el mejor en todas las métricas.
- **Fase 3 COMPLETADA (E22–E23): núcleo del agente funcionando end-to-end** (`src/safesite/`): percepción → confirmación temporal (K=3 frames) → cooldown → alerta (consola + payload WhatsApp DRY-RUN) → historial. **Métrica de incidente con el modelo de despliegue:** recall `no_helmet` = **96.3% val / 83.3% test** y **96.4% val / 96.2% test** a nivel de escena, con 2.6–3.5% de falsas alarmas y **31.5 ms/frame en GPU**. El criterio pre-registrado (≥0.70) se cumple con holgura. Demo reproducible: `.venv\Scripts\python.exe -m src.safesite.demo` (acepta `--modelo` y `--device`; guarda `eda/salidas/resumen_fase3_demo_<run>.json`).
- **Fase 4 (partes 1–3) COMPLETADA (E24–E26): WhatsApp bidireccional funcionando.**
  - **Alertas naturales CONSOLIDADAS**: un mensaje por frame con todas las faltas listadas + UNA foto ("Detectamos varios incumplimientos: • Sin Casco • Sin Guantes…"); métricas técnicas bajo demanda respondiendo **INFO**.
  - **Circuito conversacional completo** vía `servidor_webhook.py` (stdlib) + túnel cloudflared http2 + **`piloto.py`** = arranque 100% autónomo (limpia procesos → túnel → espera DNS → auto-registra webhook en Meta (2 objetos) → suscribe app→WABA → auto-prueba). Ya NO hay pasos manuales en el panel.
  - Credenciales en `.env` (gitignored): token, phone_id, destinatario, app_id, app_secret, waba_id.
  - **Piloto en ejecución:** `.venv\Scripts\python.exe -m src.safesite.piloto` (deja el webhook+ túnel activos; `Ctrl+C` detiene). Prueba de alertas rotativas: `.venv\Scripts\python.exe -m src.safesite.prueba_whatsapp --escenas 3 --device 0` (¡envía mensajes REALES y rota las escenas en cada corrida!).
- **Próximas tareas:** (1) **Fase 4 (final): fuente de video real** — webcam (`cv2.VideoCapture(0)`) o RTSP de cámara IP vía `percepcion.py`; (2) calibrar `UMBRAL_INCUMPLIMIENTO` según falsas alarmas del piloto; (3) human-in-the-loop con retroalimentación de supervisores; (4) túnel estable para producción (named tunnel de Cloudflare o servidor con dominio — el quick tunnel cambia de URL en cada reinicio, pero el piloto se auto-registra solo).
- **Regla operativa (lección E15/E16 de la bitácora):** una sola sesión de agente a la vez sobre este repositorio. En Windows usar `workers=0` en DataLoader (riesgo WinError 1455) y **verificar** la identidad de procesos antes de matarlos.
- Comandos de entrenamiento: desde la raíz, `.venv\Scripts\python.exe src\entrenamiento\entrenar_baseline.py --name <nuevo_run>` (el script se niega a sobrescribir runs existentes — usar nombre nuevo por experimento).

## Comandos útiles

```powershell
# reproducir el EDA completo
python eda\01_inspeccion_ndjson.py
python eda\02_analisis_etiquetas.py
python eda\03_analisis_imagenes.py
python eda\04_figuras.py
python eda\05_complementos.py

# regenerar el dataset (¡solo con confirmación! sobrescribe safesite_dataset/)
# python image_downloader.py
```
