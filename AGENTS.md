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
├── runs/                           # artefactos de ejecución (gitignored; depurado en E39)
│   ├── safesite/baseline_v1/        # entrenamientos: baseline_v1, tuned_v1 (hallazgo negativo) y
│   │                               # tuned_v2_s/weights/best.pt = CHECKPOINT DE DESPLIEGUE (P8)
│   └── agente/                     # pruebas/ y validacion_anclaje/ (evidencia bitácora), banco_vivo/, alertas/ (se vacía)
├── deploy/                         # página de demostración Gradio: app.py (demo,
│                                   # fallas del sensor, pruebas M1–M4, resultados,
│                                   # EDA y métricas) + demo_publica.py (emergencia)
│                                   # + .devcontainer (demo gratis en Codespaces)
├── tests/                          # tests del núcleo sin modelo ni dataset (13 pruebas; CI: .github/workflows/)
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
- **Fase 4 COMPLETADA (E24–E27), incluida la final: PANEL EN VIVO POR WEBCAM.**
  - `panel.py` (Flask + MJPEG): http://localhost:5000 con video anotado en tiempo real, tarjetas EPP por clase, log de incidentes y WhatsApp asíncrono (el video no se congela al enviar). Ejecutar: `.venv\Scripts\python.exe -m src.safesite.panel [--zona X --device 0 --sin-whatsapp]`.
  - Arquitectura de sesión en vivo: `piloto.py` (webhook+túnel, puerto 8000) y `panel.py` (webcam+video, puerto 5000) corren EN PARALELO → alertas con foto + INFO conversacional durante la sesión en vivo.
- **Todas las fases del roadmap (0–4) cerradas.** Pendientes opcionales: calibrar `UMBRAL_INCUMPLIMIENTO` según falsas alarmas del piloto real, human-in-the-loop con retroalimentación, y túnel con nombre/dominio para producción. **Push a GitHub hecho en E39.**
- **Entrega final del curso (14-oct, E30–E31):** artefactos para el enunciado de la entrega:
  - **Suite de pruebas Fase 3** (`src/safesite/pruebas_medidas.py`): 4 medidas pre-registradas (M1 recall incidente ≥0.70, M2 falsas ≤0.10, M3 alerta <10 s, M4 cooldown), 13 escenarios (normales/límite/falla esperada) × 5 reps, logs en `runs/agente/pruebas/` (log_ejecucion.jsonl + CSV + JSON + tabla MD).
  - **Anclaje visual E30→E34 (consciente del régimen):** `goggles`/`no_goggle` se re-anclan a nivel de ojos con regla por régimen — full-body (dataset MOCS): centro de la caja del casco − 15 % su altura; primer plano (webcam): borde inferior del casco + 20 % de la caja de gafas; cabeza descubierta: mitad superior de la cabeza. Con zona muerta y clamp anatómico [3–45 %]. Clase `none` ya no se dibuja (ruido). Corrección cosmética; métricas intactas.
  - **Documentos de la entrega:** `Documentation/MATRIZ_DECISION.md` (Fase 1: SAFESITE 4.85 vs PredictMaint 2.90, sensibilidad incluida), `Documentation/TABLA_CAMBIOS.md`, `Documentation/DESARROLLO_AGENTE.md` (sección 9 completa con UML Mermaid), `Documentation/GUION_VIDEO.md`, `requirements.txt`, `.env.example`.
  - `agente.procesar_frame` valida frames inválidos (None/1 canal) → `frames_fallidos` (requisito "sensor sin dato" del enunciado); `agente.reset()` para repeticiones de pruebas.
  - **Anti-spam del canal + control manual (E32):** `COOLDOWN_GLOBAL_S=60` y `MAX_MENSAJES_HORA=20` en `ActuadorWhatsApp` (solo el canal externo); panel con botones **Pausar WhatsApp** y **Enviar alerta ahora** (`POST /whatsapp/toggle`, `POST /alerta/manual`); `forzar=True` para envíos deliberados (botón manual, `prueba_whatsapp.py`). Lección de E32: en PowerShell, `$env:VAR=''` ELIMINA la variable (el cargador de .env la re-pobla) — para forzar DRY-RUN usar nombres de env inexistentes, nunca variables vacías.
  - **Perfil VIVO de umbrales + coherencia (E33/E35, resuelve P10 parcialmente):** dos perfiles documentados — `evaluacion` (umbral global `no_*` 0.15, default de suite/demo; métricas E31 intactas) y `vivo` (default del panel; por clase: no_helmet 0.18, no_goggle 0.18, no_gloves 0.25, no_boots 0.15, **más `REGLA_COHERENCIA_VIVO`**: positivo detectado en la misma persona suprime su `no_*` contradictorio, p.ej. un guante visto + no_gloves de la otra mano). `SafeSiteAgent(perfil_umbrales=..., coherencia=...)` + `panel.py --perfil {vivo,evaluacion}`.
  - **Banco de pruebas en vivo (E36, en curso):** diagnóstico cuantitativo del dominio webcam — `no_goggle` es el eslabón débil (recall incidente 0.44 val / 0.54 test) y **no existe clase `no_vest`** (el agente no puede alertar "SIN CHALECO" por diseño). Herramientas: `python -m src.safesite.capturar_banco --device 0` (captura por escenario, frames crudos a `runs/agente/banco_vivo/capturas/` — insumo también del fine-tune) y `python -m src.safesite.banco_vivo --device 0` (evalúa ambos perfiles, reportes en `eda/salidas/banco_vivo_*.{json,md}`; sin actuadores). Plan E37+: capturas → banco → decidir chaleco (clase 12 `no_vest` vs regla) → etiquetar → fine-tune desde `tuned_v2_s` → re-banco antes/después.
  - **Regla operativa WhatsApp (E37/E38, resuelto):** la API acepta el envío (200+wamid) pero falla silenciosamente si la **ventana de 24 h** está cerrada (error 131047, visible solo en los `statuses` del webhook — ya se loguean). Si pasan >24 h sin actividad, el supervisor debe **escribir primero** al número de prueba (+1 555-667-8447) para abrir la ventana; fuera de ventana en producción, usar plantilla `alerta_epp` (`construir_payload`). Diagnóstico: `prueba_whatsapp.py --rutas <img>` prueba escenas concretas; `ActuadorWhatsApp._post` ahora loguea el cuerpo del error de Meta.
- **Demo web (E40–E51):** `deploy/app.py` (Gradio, 6 pestañas). Publicación **permanente y gratis: Claw Cloud** — imagen Docker lista (`deploy/Dockerfile`; validada end-to-end: build 2.84 GB, HTTP 200 y verificación real por API) con `ENV SAFESITE_PUERTO=8788, SAFESITE_SERVIDOR=publico`. **Requisito medido: pico 677 MB → 2 GB de RAM en el App (mínimo 1 GB); con 512 MB muere OOM (E51)** — Render free/Starter descartado por experimento (OOM real a los 512 MB); el 503 de un App de Claw apunta a RAM insuficiente o puerto ≠ 8788. HF Spaces descartado (cpu-basic pasó a PRO de pago, E48). Codespaces (devcontainer) para demo puntuales; `demo_publica.py` de emergencia.
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
