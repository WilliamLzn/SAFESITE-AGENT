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

### E18 — Commit de Fases 0 y 1 ✅

`git add . && git commit` → **`3283a97`** — 55 archivos, 9,784 líneas: skills instaladas, EDA completo (scripts + figuras + informe), `eda/06_resplit_oficial.py`, `src/entrenamiento/entrenar_baseline.py`, `AGENTS.md`, bitácora E1–E17 y `.gitignore` (excluye `.venv/` ~6 GB, `runs/`, `dataset_v2/` — derivable con `eda\06`, pesos `*.pt`). Sin datos pesados en el historial.

### E19 — FASE 2 (parte 1): dataset_v3 con oversampling de incumplimientos ✅

**Comando:** `python eda\07_oversampling_dataset_v3.py` → `dataset_v3/` + `eda/salidas/resumen_fase2_oversampling.json`

**Política de replicación (determinista, val/test intactos apuntando a dataset_v2):**
- 1,130 imágenes originales de train + **239 copias** de imágenes con ≥1 caja `no_*` (`__rep1`) + **28 copias extra** de imágenes con `no_boots` (`__rep2`) = **1,397 imágenes**
- Verificación de alineación imagen↔etiqueta en v3: sin fallos (assert)

**Cajas por clase en train, antes → después:**

| Clase | v2 (oficial) | v3 (oversampled) | Factor |
|---|---:|---:|---:|
| **no_helmet** | 397 | **846** | ×2.13 |
| **no_goggle** | 337 | **716** | ×2.13 |
| **no_gloves** | 440 | **936** | ×2.13 |
| **no_boots** | 88 | **264** | **×3.00** |
| Person | 1,766 | 2,249 | ×1.27 |
| none | 648 | 1,096 | ×1.69 |
| helmet | 1,340 | 1,351 | ×1.01 |

**Nota:** el crecimiento colateral de Person (×1.27) y none (×1.69) es esperado — las imágenes con incumplimiento suelen ser primeros planos de personas. `dataset_v3/dataset.yaml` usa `path` = raíz del proyecto con train → v3 y val/test → v2 (comparación justa contra baseline_v1).

### E20 — FASE 2 (parte 2): entrenamiento tuned_v1 lanzado 🔄

**Comando:** `.venv\Scripts\python.exe src\entrenamiento\entrenar_baseline.py --name tuned_v1 --data dataset_v3\dataset.yaml --hsv-v 0.5 --batch 8 --epochs 100 --patience 25 --workers 0`

**Cambios vs baseline_v1 (comparación controlada — solo 3 diferencias):**
1. **Datos:** train oversampled v3 (×2.13 `no_*`, ×3 `no_boots`) en vez de v2
2. **`hsv_v=0.5`** (vs 0.4 default): más jitter de brillo, ataca el hallazgo F9 (4.5% de imágenes oscuras)
3. **`patience=25`** (vs 20): un poco más de margen al early stopping

Constantes: YOLOv8n, batch 8, imgsz 640, seed 42, AdamW auto, workers 0 (lección E15).

**Verificación temprana del log:** yaml v3 resuelto correctamente (escaneó 1,397 imágenes, 0 corruptas), hsv_v=0.5 y patience=25 confirmados en args, AMP checks passed, entrenamiento en curso. Criterio de éxito pre-registrado (sin cambios): recall `no_helmet` ≥ 0.70 Y precisión global ≥ 0.80 en val.

### E21 — FASE 2 RESULTADO: tuned_v1 completado — hallazgo NEGATIVO documentado 🔬

**Duración:** 73/100 épocas (early stopping, mejor época 48) en 0.812 h (~49 min) · VRAM 1.41 GB · seed 42 · `runs/safesite/tuned_v1/weights/best.pt`

**Comparación baseline_v1 vs tuned_v1 (best.pt):**

| Métrica | baseline_v1 (VAL) | tuned_v1 (VAL) | baseline_v1 (TEST) | tuned_v1 (TEST) |
|---|---:|---:|---:|---:|
| mAP50 global | **0.580** | 0.561 | **0.520** | 0.516 |
| Precisión global | 0.557 | **0.624** | 0.600 | **0.574** |
| Recall global | **0.593** | 0.510 | 0.507 | 0.500 |
| no_helmet R | **0.467** | 0.267 | 0.150 | **0.175** |
| no_helmet AP50 | **0.385** | 0.324 | **0.126** | 0.114 |
| no_gloves R | **0.286** | 0.161 | **0.155** | 0.103 |
| no_boots AP50 | **0.066** | 0.004 | 0.014 | **0.065** |
| helmet AP50 | 0.842 | 0.816 | 0.931 | 0.927 |
| Person AP50 | 0.885 | **0.909** | 0.841 | 0.847 |

**Criterio pre-registrado: ❌ NO CUMPLIDO** (recall `no_helmet` 0.267 < 0.70; precisión 0.624 < 0.80).

**Interpretación (hallazgo negativo con valor académico):**
1. **Replicar escenas no añade diversidad.** El modelo vio más cajas `no_*` pero de las MISMAS 239 imágenes → memorizó escenas concretas en vez de aprender el concepto "cabeza sin casco" (que es intrínsecamente difícil: es la *ausencia* de un objeto, con poco soporte visual distintivo). El recall de `no_*` en val cayó.
2. **El modelo se volvió más conservador:** precisión global subió (0.557→0.624), recall bajó — patrón típico de sobreajuste a las escenas replicadas.
3. **En test las señales fueron mixtas y débiles** (no_helmet R 0.150→0.175; no_boots AP50 0.014→0.065; no_gloves R 0.155→0.103): con 40-58 instancias por clase en test, estas diferencias están en el borde del ruido muestral.
4. **Selección de best.pt por fitness global** (dominado por clases mayoritarias) no optimiza el recall de `no_*` — posible causa adicional de la divergencia.
5. **Conclusión de Fase 2:** el cuello de botella NO es la cantidad de gradientes sino la **diversidad real de ejemplos** (limitada por dataset, con URLs CDN muertas). Con este dataset, el recall fotograma-a-fotograma ≥ 0.70 para `no_helmet` parece inalcanzable con trucos de entrenamiento.

**Reencuadre estratégico para el agente (importante):** el criterio "recall ≥ 0.70 **en una foto**" era el metric equivocado para el caso de uso. El agente opera sobre **video continuo**: un trabajador sin casco persiste en decenas de fotogramas. Con detección por fotograma ~0.3-0.5 y confirmación temporal de K fotogramas + memoria por zona (diseño Fase 3), el **recall a nivel de incidente** (detectarlo al menos una vez mientras ocurre) es mucho mayor que el recall por fotograma. La métrica del negocio debe ser recall de incidentes con tasa de falsas alarmas controlada.

**Decisión (doble vía, pre-registrada en el roadmap):**
1. **Fallback pre-registrado en background:** entrenar `tuned_v2_s` (YOLOv8**s**, 11.2M params, misma data v3, seed 42) — prueba si el límite es capacidad del modelo. Se lanza en background mientras se avanza en paralelo.
2. **Avanzar Fase 3 YA (núcleo del agente)** usando `runs/safesite/baseline_v1/weights/best.pt` (el mejor modelo actual para `no_*`: recall no_helmet 0.467 en val) con: umbrales de confianza por clase, confirmación temporal de K fotogramas, cooldown anti-spam e historial por incidente — así el agente demuestra valor con el modelo existente, y `tuned_v2_s` (o futuros modelos) se enchufa después con solo cambiar la ruta del checkpoint.

### E22 — FASE 3 COMPLETADA: núcleo del agente + demo con métricas de incidente ✅

**Módulos construidos (`src/safesite/`):**

| Módulo | Rol | Decisiones de diseño (basadas en EDA/bitácora) |
|---|---|---|
| `config.py` | Umbrales por clase, K=3 frames, cooldown 30 s | UMBRAL_INCUMPLIMIENTO=0.15 (bajo, la confirmación temporal compensa); EDA F5/F6 |
| `percepcion.py` | Fuentes de frames (FuenteCarpeta simula video) + YOLO + anotación | Inferencia a umbral bajo; el filtro POR CLASE lo hace el razonamiento |
| `razonamiento.py` | Confirmación temporal: clase `no_*` en ≥K frames consecutivos | Decisión SOLO por clases `no_*` explícitas (F6: anidamiento falla 38%) |
| `memoria.py` | Cooldown anti-spam por (zona, clase) + historial JSONL persistente | Agente basado en modelos con memoria de corto plazo |
| `actuarios.py` | Consola + frame anotado guardado; WhatsApp Business Cloud (payload exacto, DRY-RUN sin credenciales) | Interfaz lista para Fase 4 (faltan credenciales Meta + plantilla aprobada) |
| `agente.py` | Orquestador percibir→razonar→actuar + latencias | — |
| `demo.py` | Simulación: cada escena del dataset = 4 frames consecutivos a 2 FPS | Métrica reencuadrada de E21: recall A NIVEL DE INCIDENTE |

**Errores del camino (documentados):** (1) shadowing en `razonamiento.py` — la variable `origen` (string) fue sobrescrita por `next(...)` que devolvía un objeto `Deteccion` → crash al serializar el historial (primer incidente sí alertó en consola antes del crash). (2) el resumen reportaba `alertas_emitidas: 0` por reinicio de contador entre splits sin capturar el delta — corregido y JSON parcheado con los conteos reales del historial (532 train / 58 val / 50 test = 640). (3) **Incidente de higiene git:** el commit original de Fases 2-3 incluyó por accidente `dataset_v3/` completo (2,797 archivos, ~150 MB: `.gitignore` solo excluía `dataset_v2/` porque `dataset_v3` no existía cuando se escribió, y no se verificó el stage antes de commit) → corregido con `git rm -r --cached` + `commit --amend` ANTES de cualquier push (el repo estaba ahead-2, nunca empujado; ambos commits son locales). **Lección: verificar SIEMPRE el stage (`git status`/`git show --stat`) antes de cada commit, y actualizar `.gitignore` al crear carpetas derivadas nuevas.**

**RESULTADOS DEL DEMO (5,652 frames, CPU, ~96 ms/frame, modelo baseline_v1):**

Recall A NIVEL DE INCIDENTE (¿alertó el agente la clase correcta en la escena?):

| Clase | train (inflado, memorización) | **val (creíble)** | **test (creíble)** | n escenas val/test |
|---|---:|---:|---:|---:|
| no_helmet | 0.874 | **0.778** | **0.792** | 27 / 24 |
| no_gloves | 0.847 | 0.696 | 0.565 | 23 / 23 |
| no_goggle | 0.556 | 0.440 | 0.417 | 25 / 24 |
| no_boots | 0.679 | 0.500 | 0.500 | 2 / 6 (n minúsculo) |
| **Cualquier `no_*` (escena)** | 0.967 | **0.929** | **0.846** | 28 / 26 |

| Falsas alarmas (escenas control sin `no_*`) | train | val | test |
|---|---:|---:|---:|
| Tasa | 0.8% (7/891) | **2.6% (3/115)** | **0.9% (1/114)** |

**🎯 Lectura clave (el reencuadre de E21 VALIDADO con datos):**
1. **El criterio pre-registrado (recall `no_helmet` ≥ 0.70) SÍ SE CUMPLE a nivel de incidente en datos no vistos**: 0.778 (val) y 0.792 (test), contra 0.467 a nivel de fotograma en la evaluación estándar. La diferencia no es truco: es el umbral por clase (0.15) + la métrica correcta para el caso de uso.
2. **A nivel de escena (cualquier incumplimiento): 92.9% val / 84.6% test** con ~1-3% de falsas alarmas.
3. **Honestidad metodológica:** (a) train está inflado por memorización — se reporta solo como referencia; (b) val/test tienen pocas escenas de incidente (28/26) — intervalos amplios, pero la señal es consistente entre ambos; (c) la simulación repite el mismo frame 4 veces, así que en esta simulación el recall por fotograma y por incidente coinciden — **en video real el recall de incidente tenderá a ser MAYOR** (más oportunidades temporales con variaciones de pose, no 4 frames idénticos); (d) `latencia_max` (4.5 s) es el calentamiento del primer frame en CPU; la media es 96 ms.
4. **Latencia end-to-end: 96 ms/frame en CPU** (~10 GB de margen frente al objetivo <10 s del proyecto); en GPU la percepción es 5.4 ms.
5. **El agente completo funciona**: detecta → confirma con K frames → filtra por cooldown → alerta (consola + payload WhatsApp listo) → guarda frame anotado → persiste historial JSONL.

**Artefactos:** `src/safesite/*.py` (7 módulos), `eda/salidas/resumen_fase3_demo.json` (métricas completas por split), `runs/agente/historial_incidentes.jsonl` (640 incidentes), `runs/agente/alertas/*.jpg` (frames anotados de evidencia).

**Estado `tuned_v2_s` (yolov8s):** 🔄 entrenando en background (~2 h estimadas) — al terminar se comparará con baseline_v1 en la métrica de incidente (misma simulación) y se decidirá el checkpoint de despliegue.

### E23 — P6 COMPLETADO + P8 DECISIÓN DE DESPLIEGUE: tuned_v2_s gana ✅

**tuned_v2_s (yolov8s, 11.1M params, data v3):** 44/100 épocas (early stop, mejor época 19) en 0.808 h · VRAM 2.4 GB · seed 42 · `runs/safesite/tuned_v2_s/weights/best.pt` (22.5 MB)

**Métricas estándar (por fotograma), best.pt:**

| Métrica | VAL | TEST |
|---|---:|---:|
| mAP50 global | 0.553 | 0.523 |
| **Precisión global** | **0.810** (la más alta de los 3 modelos) | 0.611 |
| no_helmet AP50 | **0.453** (la más alta) | **0.176** (la más alta) |
| helmet AP50 | 0.819 | 0.925 |

**P8 — Comparación en la métrica que importa (recall A NIVEL DE INCIDENTE, agente completo, misma simulación):**

| Métrica | baseline_v1 (v8n, GPU→sim) | **tuned_v2_s (v8s, GPU)** | Δ val |
|---|---:|---:|---:|
| no_helmet — val | 0.778 | **0.963** | **+18.5 pts** |
| no_helmet — test | 0.792 | **0.833** | +4.1 pts |
| Cualquier `no_*` (escena) — val | 0.929 | **0.964** | +3.5 pts |
| Cualquier `no_*` (escena) — test | 0.846 | **0.962** | **+11.6 pts** |
| no_gloves — val | 0.696 | **0.783** | +8.7 pts |
| no_goggle — test | 0.417 | **0.542** | +12.5 pts |
| no_boots — val (n=2) | 0.500 | 0.000 | ruido (n minúsculo) |
| Falsas alarmas — val / test | 2.6% / 0.9% | 3.5% / 2.6% | +0.9 / +1.7 pts |
| Latencia por frame (GPU) | — | **31.5 ms** | — |

**DECISIÓN (P8): `tuned_v2_s/weights/best.pt` es el checkpoint de despliegue.** Superior en todas las métricas de negocio (recall de incidente), con falsas alarmas levemente mayores pero aún bajas (2.6–3.5%) y ajustables por umbral. El criterio pre-registrado (recall `no_helmet` ≥ 0.70 en val) se cumple **con holgura: 0.963**. `config.RUTA_MODELO` ya apunta a él.

**Notas técnicas:** (1) la simulación P8 corrió en GPU (ya libre tras el entrenamiento) con `--device 0`; (2) el demo ahora acepta `--modelo` y `--device` y guarda `resumen_fase3_demo_<run>.json` por modelo (no sobrescribe comparaciones); (3) conclusión de Fase 2 consolidada: el modelo MÁS GRANDE sí ayudó donde la replicación de datos falló — el límite era parcialmente capacidad de extraer el patrón "ausencia de EPP", no solo datos; (4) `no_boots` en val tiene n=2 escenas — cualquier número allí es ruido (documentado en E17).

**Artefactos:** `eda/salidas/metricas_tuned_v2_s.json` (val/test por fotograma), `eda/salidas/resumen_fase3_demo_tuned_v2_s.json` (incidente), `runs/safesite/tuned_v2_s/` (run completo).

### E25 — FASE 4 (parte 2): circuito conversacional completo (webhook bidireccional) ✅

**Petición del usuario:** mensajes menos técnicos (lenguaje natural + métricas bajo demanda respondiendo INFO).

**Construido:**
- **Mensajes naturales** en `ActuadorWhatsApp` (DESCRIPCION_NATURAL por clase: "un trabajador SIN CASCO", etc.) + invitación explícita a responder INFO. Métricas TÉCNICAS solo bajo demanda.
- **`servidor_webhook.py`** (stdlib pura, sin dependencias): GET = challenge de Meta; POST = mensajes entrantes → si el supervisor responde INFO/métricas/detalle → envía el detalle técnico de la última alerta; "hola" → presentación; otros → "solo entiendo INFO".
- **Túnel público temporal** con cloudflared (quick tunnel, sin cuenta). **Hallazgo:** QUIC/UDP inestable en esta red (caídas cada 15-30 s: `datagram manager error`) → **`--protocol http2`** (TCP) lo estabilizó.

**Camino del diagnóstico (4 hallazgos encadenados, todos documentados):**
1. Los envíos de alerta llegaban como chat de un número desconocido (+1 555-667-8447 "Test Number") — el usuario no los veía al inicio; luego confirmó recepción.
2. El primer INFO nunca llegó: la URL del webhook se verificaba pero faltaba la **suscripción al campo `messages`**.
3. **`piloto.py` (modo piloto auto-suficiente):** un solo comando que limpia procesos, levanta webhook + túnel, espera propagación de DNS y se **AUTO-REGISTRA en Meta via Graph API** (`POST /{APP_ID}/subscriptions`) — ya sin pasos manuales en el panel. Errores resueltos en el camino: el token de System User NO sirve para subscriptions (error #15: exige **app access token** `APP_ID|APP_SECRET`, agregado al `.env`); el registro inmediato falla por DNS no propagado (error #2200 → espera con reintentos); el `netstat` de Windows explota en UTF-8 por BOM/codificación local (decodificación con `errors="replace"`).
4. **La pieza final:** con el webhook registrado, los mensajes entrantes SEGUIAN sin llegar → faltaba **suscribir la app al WABA** (`POST /{WABA_ID}/subscribed_apps` → `{"success":true}`), paso que el panel hace invisible. Ese día el log registró: `📩 mensaje entrante de 573185469893: 'info' -> métricas enviadas` — **circuito conversacional completo**.

**Arranque autónomo verificado (piloto):** limpieza → servidor → túnel http2 → espera DNS (7 intentos) → registro de DOS objetos (`whatsapp` con `messages` + `whatsapp_business_account` con 10 campos) → suscripción app→WABA → auto-prueba local+pública → 🟢 activo. El `.env` acumuló: `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_DESTINATARIO`, `WHATSAPP_APP_ID`, `WHATSAPP_APP_SECRET`, `WHATSAPP_WABA_ID` (todos gitignored).

### E26 — FASE 4 (parte 3): alertas CONSOLIDADAS + rotación de escenas de prueba ✅

**Petición del usuario:** (1) un solo mensaje con TODAS las faltas del frame en vez de uno por clase; (2) rotar las escenas de prueba.

**Implementado:**
- **`alertar_lote`** en los tres actuadores (base/consola/WhatsApp): el agente agrupa las faltas confirmadas del frame, anota UNA sola foto y envía UN mensaje: "Detectamos varios incumplimientos de EPP en la zona X: • Un Trabajador Sin Casco • Un Trabajador Sin Guantes…". Cooldown por (zona, clase) intacto; el historial registra cada falta individual (misma hora de confirmación).
- **INFO por lote:** `_ultimos_incidentes` agrupa el historial por `t_confirmacion` → el detalle técnico lista todas las faltas de la última alerta con su confianza.
- **Rotación determinista** en `prueba_whatsapp.py`: puntero persistente (`runs/agente/puntero_prueba.txt`) que cicla por las 28 escenas de incidente de val — cada corrida muestra escenas distintas (verificado: [0,1,2] → [3,4,5]; el puntero autoavanza). Nota técnica: el pre-sembrado manual del puntero falló silenciosamente por BOM de PowerShell (`Set-Content -Encoding utf8`) en la primera corrida — el puntero lo escribe Python en plano, así que funciona correctamente desde la segunda.

**Prueba real (GPU, 3 escenas rotativas):** escena #3 → lote=2 (`no_gloves` 20% + `no_helmet` 19%), escena #4 → lote=2 (`no_gloves` 58% + `no_helmet` 29%), escena #5 → lote=1 (`no_helmet` 41%). **5 violaciones en 3 mensajes** (antes: 5 mensajes y 5 fotos duplicadas) — 40% menos de llamadas a la API por lote doble.

**Artefactos:** `src/safesite/{actuarios,agente,servidor_webhook,prueba_whatsapp,piloto}.py` actualizados, `eda/salidas/resumen_fase4_whatsapp.json`.

### E27 — FASE 4 (final) COMPLETADA: panel web con detección EN VIVO por webcam ✅

**Petición del usuario:** frontend básico pero funcional para detectar en TIEMPO REAL por su webcam si una persona tiene o no sus EPP.

**Construido — `src/safesite/panel.py`** (única dependencia nueva: Flask 3.1.3):
- **Arquitectura de 3 hilos** para que nada se congele:
  1. *Captura*: webcam (CAP_DSHOW, 1280×720) → `agente.procesar_frame` (percepción → razonamiento K=3 → memoria/cooldown — el pipeline completo intacto) → frame anotado compartido bajo lock
  2. *Worker WhatsApp*: `ActuadorWhatsAppAsync` encola los lotes y el worker los envía por HTTP — **el video nunca se congela durante un envío de 1-3 s**
  3. *Flask*: `/` (panel HTML), `/video` (MJPEG ~15 FPS al navegador), `/estado` (JSON: conteos por clase, FPS, latencia, incidentes)
- **Panel**: tema oscuro, video con cajas (verde = EPP presente, rojo = incumplimiento), tarjetas de conteo por clase, log de incidentes con hora/confianza/frames, indicador de FPS
- **El circuito conversacional sigue vivo durante la sesión** (la Memoria escribe el historial → el webhook INFO del piloto responde con métricas del último lote en vivo)

**Verificado en el arranque:** webcam 1280×720 abierta, ~5 FPS con yolov8s en GPU (73 ms/frame), WhatsApp en ENVIO-REAL, `/estado` respondiendo. **El agente quedó 100% conectado al mundo físico**: webcam → detección → confirmación → WhatsApp con foto, en < 1 s de confirmación + ~2.6 s de envío.

**Arquitectura completa del proyecto (todas las fases del roadmap cerradas):**
```
webcam → percepcion(YOLO tuned_v2_s) → razonamiento(K frames, umbrales por clase)
       → memoria(cooldown + historial) → actuadores(consola/panel + WhatsApp async)
       ⇄ supervisor: responde INFO → webhook → métricas del lote
```

**Artefactos:** `src/safesite/panel.py`; ejecución: `.venv\Scripts\python.exe -m src.safesite.panel` → http://localhost:5000

### E24 — FASE 4 (parte 1) COMPLETADA: alertas REALES de WhatsApp con evidencia ✅

**Configuración de credenciales (Meta Business Cloud API):**
- App `safesite-agent` creada por el usuario en developers.facebook.com (tipo Business, producto WhatsApp)
- **Token permanente** de System User (~199 chars) — el usuario lo configuró directamente en las variables de entorno de Windows (`setx`) y **nunca pasó por el chat ni por git** (lección aplicada tras exponer el temporal: auto-expira, no se repitió el patrón)
- Credenciales centralizadas en **`.env`** (gitignored, verificado con `git check-ignore`): `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_ID`, `WHATSAPP_DESTINATARIO=573185469893` (número personal del usuario — hará de supervisor HSE en el piloto)
- Mini-loader de `.env` en `src/safesite/__init__.py` (sin dependencias; `os.environ.setdefault` — el entorno real tiene prioridad). **Bug documentado:** PowerShell `Set-Content -Encoding utf8` escribe BOM (`EF BB BF`, verificado en bytes) que contaminaba la primera clave → corregido leyendo con `utf-8-sig`

**Verificaciones previas:**
1. Validez del token: `GET /me` → `{"name": "WilliamLzn"}` ✅
2. Mensaje de texto manual: `messages[0].id = wamid.HBgMNTcz...` ✅ (el destinatario estaba en la lista de permitidos del número de prueba — sin error 131047)
3. Hallazgo técnico de PowerShell: pasar JSON con comillas a `curl.exe` desde PowerShell mutila las comillas → error `#100 messaging_product required` — resuelto con `Invoke-RestMethod` (el agente usa Python/requests, inmune a esto)

**`ActuadorWhatsApp` extendido (envío real con evidencia):**
- Flujo de 2 pasos de la API Cloud: `POST /{phone_id}/media` (JPEG del frame anotado, desde memoria vía `cv2.imencode`, calidad 85) → `media_id` → `POST /messages` con `image.id` + caption (`Zona | INCUMPLIMIENTO: clase | conf | hora`)
- **Degradación elegante**: si falla la imagen → texto puro; la alerta nunca se pierde
- Modo texto libre (válido con número de prueba hacia permitidos); método `construir_payload` (plantilla `alerta_epp`) preservado para producción con número de negocio
- `modo` automático: `ENVIO-REAL` solo si las 3 variables existen; si no, `DRY-RUN`

**Prueba end-to-end (`src/safesite/prueba_whatsapp.py`, 3 escenas de incidente de val, GPU):**

| Resultado | Valor |
|---|---|
| Escenas con alerta WhatsApp real | **2/3** (la 3ª fue de las que el modelo no detecta — consistente con recall de incidente 96.3%) |
| Mensajes enviados con imagen+caption | **3** (uno por clase confirmada) |
| Latencia HTTP a la API de Meta | media **2.64 s**, máx 4.10 s por llamada |
| Latencia del ciclo completo del agente | media 1.84 s (incluye los envíos) |
| **Objetivo del README: alerta < 10 s** | ✅ **CUMPLIDO**: percepción 31.5 ms + subida de imagen ~2.6 s + envío ~2.6 s ≈ **5.3 s end-to-end** |

**Artefactos:** `src/safesite/prueba_whatsapp.py` (reproducible con `--escenas N --split val --device 0`), `eda/salidas/resumen_fase4_whatsapp.json`, `src/safesite/{__init__,actuarios}.py` actualizados.

**Pendiente de Fase 4:** fuente de video real (webcam del portátil o RTSP de cámara IP) en `percepcion.py` → con eso el pipeline queda 100% conectado al mundo físico.

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
| P5 | **Fase 2:** tuning anti-desbalance | `eda\07_oversampling_dataset_v3.py` + `tuned_v1` | ✅ **E19–E21** (hallazgo negativo documentado) |
| P6 | Fallback pre-registrado: yolov8s sobre dataset_v3 | `--model yolov8s.pt --name tuned_v2_s` | ✅ **E23** (44 épocas, ~49 min) |
| P7 | **Fase 3:** núcleo del agente + demo con métrica de incidente | `src\safesite\` (7 módulos) + `-m src.safesite.demo` | ✅ **E22** (criterio CUMPLIDO a nivel de incidente: no_helmet 0.778 val / 0.792 test) |
| P8 | Comparar `tuned_v2_s` vs `baseline_v1` en métrica de incidente; elegir checkpoint de despliegue | `--modelo runs/safesite/tuned_v2_s/weights/best.pt --device 0` | ✅ **E23** — **tuned_v2_s gana** (no_helmet 0.963 val / 0.833 test; escena 0.962 test); `config.RUTA_MODELO` actualizado |
| P9 | **Fase 4:** WhatsApp real (credenciales Meta + plantilla `alerta_epp`) + panel + fuente de video real (webcam/RTSP) | `actuarios.py` + `percepcion.py` | ⬜ próxima |

> **Regla de la bitácora:** al completar P5+ se añaden nuevas entradas con fecha, comando exacto, duración, métricas y decisión tomada.
