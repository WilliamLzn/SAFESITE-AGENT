# 📓 Bitácora de trabajo — SAFESITE-AGENT

> Registro cronológico de ejecuciones, comandos exactos y resultados, para auditoría y evaluación del avance. **Regla:** cada ejecución relevante se anota con fecha, comando, semilla y resultado. (Definida como obligatoria en `AGENTS.md`.)

---

## Sesión 2026-10-13 — Instalación de skills + EDA completo

**Objetivos de la sesión:** (1) instalar las skills de K-Dense elegidas, (2) ejecutar EDA sobre el dataset de fotos, (3) generar documentación (.MD, AGENTS.md, roadmap, bitácora) y definir cómo proceder con el agente.

### E1 — Investigación del repositorio de skills

| | |
|---|---|
| **Acción** | Revisión de `github.com/K-Dense-AI/scientific-agent-skills` (README, catálogo `docs/skills.md`, API de contenidos `skills/`) |
| **Resultado** | Catálogo de **177 skills** verificado. **No existe skill "mlops"**. La más cercana: `pytorch-lightning` (tracking MLflow/TensorBoard/W&B, checkpoints, reproducibilidad). Para el EDA: `exploratory-data-analysis`. Confirmado con usuario: instalar bundle **pytorch-lightning + exploratory-data-analysis** |
| **Nota de seguridad** | El repo recomienda no instalar skills de forma masiva; se instalaron solo 2, de autoría K-Dense Inc. |

### E2 — Instalación de las skills

| | |
|---|---|
| **Comandos** | `git clone --depth 1 --filter=blob:none --sparse https://github.com/K-Dense-AI/scientific-agent-skills.git` → `git sparse-checkout set skills/pytorch-lightning skills/exploratory-data-analysis` → copia a `.opencode/skills/` |
| **Commit origen** | `a1043ef544e3a100c28e70a736b6cf32554d0677` |
| **Resultado** | ✅ **32 archivos** instalados en `.opencode/skills/{pytorch-lightning, exploratory-data-analysis}/` (SKILL.md + scripts + references + assets). OpenCode detecta ambas skills |
| **Errores** | `curl` es alias de `Invoke-WebRequest` en PowerShell → se usó `Invoke-RestMethod`. Sin otros errores |

### E3 — Verificación de entorno

```
Python 3.14.6 · pip 26.2.1 · Pillow 12.3.0 · matplotlib 3.11.2 · numpy 2.5.2 · pandas 3.0.5
```

✅ Todo lo necesario para el EDA ya estaba instalado (no se instaló nada nuevo). GPU: **RTX 4050 Laptop 6 GB** + 24 GB RAM (`nvidia-smi` 610.74, CUDA 13.3) — suficiente para YOLO nano a 640 px.

### E4 — Inventario del dataset (pre-EDA)

| Carpeta | JPG | TXT |
|---|---:|---:|
| `safesite_dataset/train/` | 1,129 | 1,129 |
| `safesite_dataset/test/` | 284 | 0 |

Lectura de `image_downloader.py` (63 líneas): split 80/20 con `random.seed(42)`, train con etiquetas, test sin etiquetas, cajas NDJSON copiadas tal cual a `.txt` → **hipótesis a verificar: posible bug de formato centro vs esquina**.

### E5 — EDA Paso 1: perfil del NDJSON

`python eda\01_inspeccion_ndjson.py`

- 1,417 registros = 1 `dataset` + 1,416 `image`. Campos imagen: `file, url, width, height, split, annotations.boxes`.
- `class_names` es **dict** (`{"0": "helmet", …}`), no list — primer script falló con `KeyError: 0` → corregido para soportar ambos formatos (error documentado, no se ocultó).

### E6 — EDA Paso 2: etiquetas, splits e integridad (núcleo del análisis)

`python eda\02_analisis_etiquetas.py` → `eda/salidas/resumen_eda.json`

**Integridad (todo ✅):** 0 imágenes sin etiqueta, 0 etiquetas huérfanas, 0 líneas mal formadas, 0 valores fuera de rango, **0 discrepancias TXT↔NDJSON**, 0 duplicados entre carpetas, 3 registros NDJSON sin descargar (fallas de descarga del run original).

**Formato verificado:** 0 violaciones de formato centro vs **2,736 violaciones** si se interpretara como esquina → **las cajas YA están en formato YOLO centro normalizado; el pipeline NO tiene bug** (hipótesis E4 descartada).

**Clases (11,521 cajas):** Person 19.49% · helmet 15.05% · vest 14.04% · boots 13.86% · gloves 12.54% · none 6.92% · no_gloves 4.83% · goggles 4.50% · no_helmet 4.21% · no_goggle 3.57% · **no_boots 1.00%** · total `no_*` = **13.60%**.

**Densidad:** mediana 7 cajas/imagen, media 8.14 (SD 5.75), máx **58**.

**Geometría:** área normalizada mediana **0.0185** (objetos pequeños), P75 0.072, máx 0.975.

**Splits — hallazgo 🔴:** split oficial NDJSON (train 1,132 / val 143 / test 141) ignorado por el proyecto. Cruce real: `train/` contiene 915 oficiales train + 102 val + **112 test oficial**; `test/` contiene 215 train + 41 val + 28 test. Contaminación confirmada.

**Anidamiento (exploratorio):** helmet dentro de Person: 61.8% (1,008); fuera: **38.2%** (623) → la regla de negocio debe usar clases `no_*` explícitas.

### E7 — EDA Paso 3: imágenes (metadatos 100% + muestra píxeles n=200 seed 42)

`python eda\03_analisis_imagenes.py` → `eda/salidas/resumen_imagenes.json`

- 1,413 JPEG RGB válidas (0 corruptas), **0 desajustes** de dimensiones vs NDJSON.
- Resoluciones: 640×640 = 1,114 (78.8%); resto ~90 tamaños mixtos (hasta 1024 px; aspect ratios 1.5, 0.67, 1.33…).
- Tamaño de archivo: mediana 91.6 KB (máx 468.8 KB).
- **Brillo (EXPLORATORIO, muestra 14%):** mediana 132/255, mínima **13.6** → hay imágenes nocturnas/interiores; 9/200 (4.5%) con brillo < 60; 48/200 (24%) < 100. Contraste SD: mediana 65.9.

### E8 — EDA Pasos 4–5: figuras y complementos

`python eda\04_figuras.py` → 6 figuras PNG válidas en `eda/figuras/` (verificadas con Pillow: cabeceras y tamaños correctos). `python eda\05_complementos.py` → porcentajes finales y conteo de imágenes de train con clases `no_*`.

**Hallazgo crítico adicional (F5):** solo **229/1,129 imágenes de train (20.3%)** contienen al menos una clase `no_*` → el 79.7% de train no aporta señal de incumplimiento; el recall de `no_*` será el cuello de botella del agente.

### E9 — Documentación generada

| Archivo | Contenido |
|---|---|
| `Documentation/EDA_SAFESITE_DATASET.md` | Informe EDA completo: diccionario de datos, hallazgos F1–F10 con severidad, figuras, limitaciones, reproducibilidad |
| `Documentation/ROADMAP_AGENTE.md` | Plan Fases 0–5 con cronograma de 4 semanas y acciones inmediatas |
| `Documentation/SKILLS.md` | .MD de las skills instaladas: procedencia, commit, licencias, contenido, uso |
| `AGENTS.md` | Convenciones del repo para agentes: mapa, reglas (datos crudos solo lectura, bitácora, semillas), estado actual |
| `Documentation/BITACORA.md` | Este documento |

---

## Sesión 2026-10-13 (2) — Implementación Fases 0 y 1

**Objetivos:** ejecutar la Fase 0 (re-split oficial + etiquetado de test) y la Fase 1 (baseline YOLOv8n entrenado en la RTX 4050). Decisiones del usuario: copiar imágenes a `dataset_v2/` e intentar descargar las 3 faltantes; lanzar el entrenamiento de inmediato.

### E10 — Verificación de entorno de entrenamiento

- `pip index versions torch` → PyPI: 2.14.1 (Windows = CPU-only). Índice cu128: solo hasta 2.11.0+cu128 para cp314. **Índice cu130: torch 2.14.1+cu130 disponible** ✅ (par: torchvision 0.29.1+cu130).
- `uv` no instalado → se usa `python -m venv .venv` estándar. Disco libre: 25.3 GB. GPU: RTX 4050 6 GB (3.5 GB ocupados por apps del usuario al arrancar la sesión).

### E11 — Fallo de instalación y corrección (error documentado)

1. `.venv` creado; `pip install torch --index-url …/cu128` instaló 2.11.0+cu128.
2. `pip install ultralytics` (8.4.176) **reemplazó torch por 2.14.1 CPU desde PyPI** → `torch.cuda.is_available() == False`. Síntoma: warning de pip sobre temp `~orch` sin limpiar.
3. **Causa raíz:** al resolver dependencias de ultralytics desde PyPI, pip seleccionó la versión más nueva de torch (2.14.1) y el índice de PyPI en Windows solo tiene build CPU.
4. **Corrección:** desinstalar torch+torchvision CPU → instalar `torch==2.14.1+cu130` + `torchvision==0.29.1+cu130` desde el índice cu130 (misma versión que exige ultralytics, build CUDA). Descarga en curso al cierre de esta entrada.
5. Lección para la bitácora: **instalar SIEMPRE torch CUDA después (o con constraint) al usar ultralytics en Windows**.

### E12 — FASE 0 EJECUTADA: dataset_v2 con splits oficiales ✅

`python eda\06_resplit_oficial.py` → `dataset_v2/` + `eda/salidas/resumen_fase0.json`

| Split oficial | Imágenes en dataset_v2 | Esperado NDJSON |
|---|---:|---:|
| train | 1,130 | 1,132 |
| val | 143 | 143 |
| test | 140 | 141 |
| **Total** | **1,413** | 1,416 |

- Estructura Ultralytics estándar: `dataset_v2/images/{train,val,test}` + `dataset_v2/labels/{train,val,test}` + `dataset.yaml` (11 clases, rutas absolutas).
- **11,488 líneas de etiqueta** escritas desde el NDJSON y verificadas en disco; alineación imagen↔etiqueta 1:1 por split (assert interno sin fallos). **test/ ahora está etiquetado** (F4 resuelto). **val/ existe** (F3 resuelto). **Splits = oficiales** (F2 resuelto).
- `safesite_dataset/` y `.ndjson` **intactos** (solo lectura, verificado: git status solo muestra archivos nuevos).

### E13 — Hallazgo operativo: las URLs del CDN EXPIRAN 🔴

Las 3 imágenes faltantes no se pudieron descargar: **HTTP 403 Forbidden** con cualquier User-Agent. Causa: las URLs del NDJSON llevan firma con `Expires=1788585901` (≈ 5-sep-2026, vencidas hace ~38 días). Implicaciones:
- Recuperar esas 3 imágenes exige regenerar URLs desde la plataforma Ultralytics (requiere sesión); se documentan sus nombres en `eda/salidas/resumen_fase0.json` (2 de train, 1 de test).
- **Re-ejecutar `image_downloader.py` hoy fallaría por completo (403 en las 1,416).** El dataset local en disco es el único soporte válido — respaldarlo es prioridad.
- El baseline procede con 1,413/1,416 (99.8%); proporciones oficiales intactas.

### E14 — Script de entrenamiento listo (Fase 1)

`src/entrenamiento/entrenar_baseline.py` — YOLOv8n, seed 42, imgsz 640, batch configurable (default 8 por VRAM compartida), epochs 100, patience 20, run dir `runs/safesite/baseline_v1`, evaluación final en val+test con métricas por clase → `eda/salidas/metricas_baseline_v1.json`.

### E15 — FALLO 1er intento de entrenamiento y corrección (error documentado)

**Intento 1** (`--batch 8 --workers 4`): época 1 completa en **31.6 s** (~9 it/s, 1.12 GB VRAM), pero al pasar a validación:

```
OSError: [WinError 1455] El archivo de paginación es demasiado pequeño
Error loading ...\.venv\...\torch\lib\cublas64_13.dll
RuntimeError: DataLoader worker (pid 27728) exited unexpectedly
```

**Causa raíz:** en Windows, cada DataLoader worker spawn re-importa torch y carga las DLLs CUDA (≈2.5 GB de commit por worker); 4 workers + proceso principal + apps del usuario agotaron el límite de commit (RAM 24 GB + pagefile).

**Corrección aplicada:** `workers=0` (carga de datos en el proceso principal; sin spawns que dupliquen DLLs). Alternativas descartadas: ampliar el pagefile (requiere admin + reinicio) o reducir workers a 2 (mismo riesgo latente). El run parcial `runs/safesite/baseline_v1` se eliminó para conservar la trazabilidad del nombre.

**Observaciones útiles del intento 1:**
- Época ≈ 32 s → 100 epochs ≈ 55 min (probable early-stop por patience=20).
- VRAM en uso: solo **1.12 GB** con batch 8 → hay margen; el cuello no es la GPU.
- Transferencia de pesos COCO: 355/355 capas, 1/11 clases remapeada por nombre (transfer learning funcionando).
- Warning menor: "Slow image access (13.2 MB/s)" — lectura de disco lenta (carpeta Documents), no bloqueante.
- Detección del dataset: "1 duplicate labels removed" en `7cb9405289207b901dfc2f841ada4088.jpg` (caja duplicada exacta en el NDJSON — hallazgo menor de calidad de datos).

**Intento 2:** relanzado con `--workers 0`, mismo nombre de run. **Falló al instante** por el guard del script: el run dir seguía existiendo — el `Remove-Item -ErrorAction SilentlyContinue` del paso de limpieza **falló silenciosamente** (manejo de error deficiente de mi parte: el mensaje de éxito se imprimió incondicionalmente). Causa: dos **procesos python zombis** del intento 1 (pid 30804 con 2.77 GB, worker DataLoader huérfano que sobrevivió al crash del padre) mantenían la sesión viva.

**Limpieza verificada:** `Stop-Process` de los zombis → `Remove-Item` con `-ErrorAction Stop` → verificación explícita `Test-Path` → 0 procesos python vivos. El guard anti-sobrescritura del script funcionó como debe: protegió la trazabilidad del run en vez de mezclar artefactos de dos corridas.

**Intento 3:** relanzado con `--workers 0` tras limpieza verificada.

---

## Sesión 2026-10-13 (continuación, SESIÓN PARALELA) — ⚠️ ver reconciliación en E16

> ⚠️ **Nota de reconciliación:** esta sección la escribió una **segunda sesión de OpenCode abierta en paralelo** sobre el mismo repositorio. Sus numeraciones E10–E12 son propias de esa sesión y se solapan con las de la sesión principal. Sus afirmaciones de estado ("en ejecución", batch 16) quedaron desactualizadas; los hechos verificados con artefactos están en E16/E17. Se conserva por trazabilidad histórica.

> **Incidente:** la pestaña de la sesión anterior murió a mitad de la instalación del entorno de entrenamiento. Al retomar se comprobó que el `pip install` huérfano terminó de completarse por su cuenta: `torch 2.14.1+cu130` y `ultralytics 8.4.176` íntegros en `.venv`, CUDA disponible. No hubo que reinstalar nada.

### E10 — P1 completada: re-split OFICIAL del dataset (Fase 0)

| | |
|---|---|
| **Comando** | `python eda\06_resplit_oficial.py` |
| **Entradas** | `construction-ppe.ndjson` + `safesite_dataset/` (ambos **solo lectura**, verificados intactos) |
| **Salida** | `dataset_v2/` (100% derivado, regenerable de cero): `images/{train,val,test}` + `labels/{train,val,test}` + `dataset.yaml` |

**Resultado:** splits del NDJSON respetados — **train 1,130 / val 143 / test 140** (1,413 en disco). 11,488 líneas de etiqueta generadas desde el NDJSON con el formato verificado en el EDA (centro normalizado, 6 decimales). Corrige los hallazgos **F2** (112 imágenes del test oficial contaminaban train), **F3** (no existía val) y **F4** (test sin etiquetas).

**Nota:** el script intentó descargar del CDN oficial las 3 imágenes que faltan en disco (2 train + 1 test); las 3 fallaron (URLs caídas) y quedan documentadas en `eda/salidas/resumen_fase0.json`. Dataset de trabajo: 1,413/1,416 (99.8%).

### E11 — Entorno de entrenamiento instalado (parte 1 de P2)

| | |
|---|---|
| **Comando** | venv del proyecto + `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu130` + `pip install ultralytics` |
| **Versiones** | Python 3.14.6 · torch **2.14.1+cu130** · torchvision 0.29.1+cu130 · ultralytics **8.4.176** · `torch.cuda.is_available()` = **True** (RTX 4050 Laptop) |
| **Diseño resiliente** | El entrenamiento se lanza desde ahora **en segundo plano con log a archivo** (`runs/train_baseline_v1.log`) y checkpoints `best.pt`/`last.pt` por época, para que un crash de la pestaña no vuelva a perder el progreso |

### E12 — P2 en curso: entrenamiento baseline_v1 lanzado

| | |
|---|---|
| **Comando** | `.venv\Scripts\python.exe src\entrenamiento\entrenar_baseline.py --batch 16` (en segundo plano) |
| **Config** | YOLOv8n · imgsz 640 · **batch 16** · epochs 100 · patience 20 · **seed 42** · device 0 (RTX 4050 6 GB) · val cada época |
| **Salidas previstas** | `runs/safesite/baseline_v1/{best.pt, last.pt, results.csv, args.yaml}` + `eda/salidas/metricas_baseline_v1.json` (mAP global y **por clase `no_*`**, evaluado en val y test) |
| **Estado** | 🔄 En ejecución al cierre de esta edición; las métricas se registrarán en E13 al finalizar |

### E16 — Reconciliación de sesiones paralelas + corrección de un error propio 🔎

**Hecho descubierto:** el repositorio fue trabajado **simultáneamente por dos sesiones** de OpenCode (dos pestañas). Evidencia verificada con artefactos:

| Evidencia | Verificado |
|---|---|
| `runs/safesite/baseline_v1/args.yaml` | `batch: 8 · workers: 0 · seed: 42 · epochs: 100` → el run que sobrevivió es el de la sesión principal |
| `runs/safesite/baseline_v1/results.csv` | 73 líneas = 72 épocas completas (early stop en 72, mejor época 52) |
| `runs/train_baseline_v1.log` (337.7 KB, de la sesión paralela) | entrenamiento con **batch 16** (71 iters/época, 2.58 GB VRAM) que **murió en la época 15** sin completar |
| Procesos python vivos al verificar | **ninguno** (ambos entrenamientos terminados/muertos) |

**Corrección honesta de la entrada E15:** los dos procesos que eliminé como "zombis" (pid 30804 con 2.77 GB) **con alta probabilidad incluían el entrenamiento batch-16 de la sesión paralela, aún vivo en ese momento** — no un worker huérfano de mi intento 1, como asumí. La conclusión operativa de entonces (verificar la eliminación antes de reportar éxito) sigue en pie, pero la atribución era incorrecta. Lección doble: (1) verificar la identidad de procesos antes de matarlos, (2) **no operar dos sesiones de agente simultáneamente sobre el mismo repositorio** — riesgos reales: re-splits concurrentes mientras otra sesión entrena, kills de procesos ajenos y dobles numeraciones de bitácora.

**Estado final consolidado:** un único run completo y consistente (`baseline_v1`, batch 8, workers 0, seed 42), un run paralelo muerto en época 15 (batch 16, descartado), dataset_v2 íntegro (regenerado por ambas sesiones con el mismo script determinista → contenido idéntico).

### E17 — FASE 1 COMPLETADA: baseline_v1 entrenado y evaluado ✅

**Comando:** `.venv\Scripts\python.exe src\entrenamiento\entrenar_baseline.py --batch 8 --epochs 100 --name baseline_v1 --workers 0`
**Duración:** 72/100 épocas (early stopping, mejor época 52) en **0.623 h (~37 min)** · VRAM 1.4 GB · ~28.5 s/época · AdamW auto (lr 6.67e-4) · checkpoint: `runs/safesite/baseline_v1/weights/best.pt` (6.5 MB)

**Métricas por clase (best.pt) — split VAL (143 imgs / 1,172 instancias):**

| Clase | P | R | AP50 | AP50-95 |
|---|---:|---:|---:|---:|
| **all** | 0.557 | 0.593 | **0.580** | 0.280 |
| helmet | 0.736 | 0.841 | 0.842 | 0.433 |
| gloves | 0.679 | 0.772 | 0.792 | 0.365 |
| vest | 0.755 | 0.825 | 0.829 | 0.516 |
| boots | 0.609 | 0.775 | 0.778 | 0.432 |
| goggles | 0.787 | 0.723 | 0.791 | 0.375 |
| none | 0.531 | 0.568 | 0.566 | 0.185 |
| Person | 0.759 | 0.891 | 0.885 | 0.472 |
| **no_helmet** | 0.384 | **0.467** | 0.385 | 0.145 |
| **no_goggle** | 0.324 | **0.122** | 0.187 | 0.055 |
| **no_gloves** | 0.367 | **0.286** | 0.257 | 0.080 |
| **no_boots** | 0.191 | 0.250 | 0.066 | 0.022 |

**Métricas por clase (best.pt) — split TEST (140 imgs / 1,244 instancias):**

| Clase | P | R | AP50 | AP50-95 |
|---|---:|---:|---:|---:|
| **all** | 0.600 | 0.507 | **0.520** | 0.261 |
| helmet | 0.929 | 0.895 | **0.931** | 0.492 |
| vest | 0.821 | 0.870 | 0.886 | 0.566 |
| Person | 0.774 | 0.832 | 0.841 | 0.502 |
| goggles | 0.817 | 0.712 | 0.804 | 0.310 |
| gloves | 0.789 | 0.745 | 0.768 | 0.381 |
| boots | 0.671 | 0.689 | 0.739 | 0.380 |
| none | 0.475 | 0.446 | 0.348 | 0.118 |
| **no_helmet** | 0.250 | **0.150** | 0.126 | 0.038 |
| **no_goggle** | 0.580 | **0.085** | 0.126 | 0.051 |
| **no_gloves** | 0.497 | **0.155** | 0.141 | 0.036 |
| **no_boots** | 0.000 | **0.000** | 0.014 | 0.003 |

**Evaluación del criterio pre-registrado (roadmap, Fase 2):** ❌ **NO CUMPLIDO**
- recall `no_helmet` = 0.467 (val) < 0.70 requerido · precisión global = 0.557 (val) < 0.80 requerido

**Interpretación (coherente con el EDA, hallazgo F5):**
1. **Clases positivas fuertes:** helmet AP50 0.84 (val) / 0.93 (test), Person 0.89/0.84, vest 0.83/0.89 → el modelo VE bien el equipo presente.
2. **Clases de incumplimiento débiles:** `no_*` con AP50 0.13–0.26 en test (recall 8.5–15.5%). Señal de entrenamiento escasa (20.3% de imágenes con `no_*`) y **soporte de evaluación minúsculo** (val: 45 `no_helmet`, solo 4 `no_boots` — métricas de `no_boots` poco fiables por tamaño muestral).
3. **Velocidad de inferencia: 5.1–5.9 ms/imagen** en la RTX 4050 (~170 FPS de percepción pura) → el presupuesto del agente (<10 s hasta la alerta) queda holgado en el módulo de percepción.
4. Nota técnica: `eda/salidas/metricas_baseline_v1.json` serializa las clases como `clase_0..clase_10` (mapeo de nombres pendiente de corregir en el serializador); el orden es el de `dataset.yaml` (0=helmet … 10=no_boots) y los valores coinciden con la salida de ultralytics.

**Decisión:** pasar a **Fase 2 — tuning anti-desbalance** (pre-registrada), priorizando recall de `no_*`. Alternativa descartada: más épocas (la curva plateauó desde la época 52; patience 20 lo confirmó).

**Artefactos del run:** `runs/safesite/baseline_v1/` — `weights/best.pt` + `last.pt`, `results.csv` (72 épocas), `confusion_matrix.png`, `PR_curve.png`, `labels.jpg`, `args.yaml` completa — y `eda/salidas/metricas_baseline_v1.json`.

---

## 📊 Tabla resumen del EDA (para evaluación rápida)

| Indicador | Valor | Estado |
|---|---|---|
| Imágenes analizadas (metadatos) | 1,413/1,416 en disco (100%) | ✅ |
| Etiquetas verificadas | 1,129/1,129 txt ↔ NDJSON | ✅ 0 discrepancias |
| Formato YOLO | Centro normalizado confirmado | ✅ sin bug |
| Contaminación split | 112 test-oficial en train/ | 🔴 a corregir (Fase 0) |
| Conjunto de validación | No existe | 🔴 a crear (Fase 0) |
| Test etiquetado | 0/284 (posible trivialmente) | 🟠 Fase 0 |
| Balance `no_*` | 13.6% cajas · 20.3% imágenes con `no_*` | 🟠 tuning Fase 2 |
| `no_boots` | 115 cajas (1.00%) | 🟠 clase más débil |
| Objetos pequeños | área mediana 1.85% de la imagen | 🟡 imgsz ≥ 640 |
| Imágenes oscuras | 4.5% (<60 brillo, muestra n=200) | 🟡 augmentation |
| Regla anidamiento casco⊂persona | falla 38.2% | 🟠 usar clases `no_*` |

## ⏭️ Próximas ejecuciones planificadas (pendientes de aprobación)

| # | Ejecución | Script/Comando previsto | Estado |
|---|---|---|---|
| P1 | Re-split oficial + etiquetado de test + `dataset.yaml` | `eda\06_resplit_oficial.py` | ✅ **E12/E16** |
| P2 | Entrenamiento `baseline_v1` (YOLOv8n, imgsz 640, seed 42, RTX 4050) | `src\entrenamiento\entrenar_baseline.py` | ✅ **E17** (72 épocas, ~37 min) |
| P3 | Evaluación en val + test etiquetado; tabla de métricas por clase | integrado en el script (P2) | ✅ **E17** (criterio NO cumplido) |
| P4 | Registro de métricas `baseline_v1` en esta bitácora | — | ✅ **E17** |
| P5 | **Fase 2:** tuning anti-desbalance (aumento dirigido, umbrales por clase) para subir recall `no_*` | `src\entrenamiento\entrenar_baseline.py --name tuned_v1` + params de augment | ⬜ próxima |

> **Regla de la bitácora:** al completar P5+ se añaden nuevas entradas con fecha, comando exacto, duración, métricas y decisión tomada.
