<div align="center">

![Estado](https://img.shields.io/badge/Estado-Fases_0_a_4_completadas-brightgreen?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch-2.14-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![Ultralytics](https://img.shields.io/badge/Ultralytics-YOLOv8s-DD0031?style=for-the-badge&logo=ultralytics&logoColor=white)
![OpenCV](https://img.shields.io/badge/OpenCV-5.0-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)
![Gradio](https://img.shields.io/badge/Gradio-6.30-FF7C00?style=for-the-badge&logo=gradio&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-3.1-000000?style=for-the-badge&logo=flask&logoColor=white)
![WhatsApp](https://img.shields.io/badge/WhatsApp-Business_Cloud_API-25D366?style=for-the-badge&logo=whatsapp&logoColor=white)
![Modal](https://img.shields.io/badge/Modal-Demo_24_7-7B2BF9?style=for-the-badge)
![NVIDIA](https://img.shields.io/badge/GPU-RTX_4050-76B900?style=for-the-badge&logo=nvidia&logoColor=white)
![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-CI-2088FF?style=for-the-badge&logo=githubactions&logoColor=white)

</div>

<h1 align="center">SAFESITE-AGENT</h1>

<p align="center">
  <strong>Agente inteligente de monitoreo de EPP (equipo de protección personal) en obra</strong><br/>
  Detección de incumplimientos con YOLOv8s, razonamiento temporal y alertas automáticas por WhatsApp<br/>
  <em>Proyecto de Inteligencia Artificial, Universidad Tecnológica de Bolívar</em>
</p>

---

## Índice

- [Qué es SafeSite-Agent](#qué-es-safesite-agent)
- [El problema](#el-problema)
- [Cómo funciona el agente](#cómo-funciona-el-agente)
- [Resultados medidos](#resultados-medidos)
- [El dataset y su análisis](#el-dataset-y-su-análisis)
- [Estructura del repositorio](#estructura-del-repositorio)
- [Requisitos e instalación](#requisitos-e-instalación)
- [Cómo ejecutar el proyecto](#cómo-ejecutar-el-proyecto)
- [Pruebas y CI](#pruebas-y-ci)
- [La demo web pública](#la-demo-web-pública)
- [Documentación](#documentación)
- [Créditos](#créditos)
- [Referencias](#referencias)
- [Nota de transparencia](#nota-de-transparencia)

---

## Qué es SafeSite-Agent

**SafeSite-Agent** es un agente que **percibe** continuamente el video de una obra de construcción (webcam o cámara IP), **razona** sobre lo observado con confirmación temporal y memoria anti-spam, y **actúa de forma autónoma** avisando al supervisor de seguridad (HSE) por **WhatsApp Business** cuando detecta a un trabajador sin su equipo de protección personal: casco, gafas, guantes o botas.

Desde la teoría de agentes inteligentes se clasifica como un **agente reactivo basado en modelos** (*model-based reflex agent*) con componente de **utilidad** para priorizar alertas: su decisión no depende solo del fotograma actual, sino de un estado interno (rachas por zona y clase, mas un cooldown) que distingue un evento aislado de un patrón recurrente.

El ciclo completo del agente:

1. **Percibir**: YOLOv8s detecta personas, EPP presentes y faltas explicitas (clases `no_*`) en cada fotograma.
2. **Razonar**: una falta solo se confirma si aparece en **3 fotogramas seguidos** (K=3). Las decisiones usan exclusivamente las clases de incumplimiento explicitas del detector.
3. **Recordar**: cada par (zona, clase) confirmado entra en un **cooldown de 30 segundos** para no repetir alertas; el canal de WhatsApp tiene además un tope global (mínimo 60 segundos entre mensajes, máximo 20 por hora).
4. **Actuar**: un único mensaje de WhatsApp con todas las faltas del momento y la foto anotada del incidente. El supervisor puede responder **INFO** y el agente le devuelve el detalle técnico por el mismo chat.

---

## El problema

El incumplimiento en el uso de EPP es una de las principales causas de accidentalidad en construcción. La supervisión manual tiene un límite claro: *un supervisor no puede observar de forma simultánea y continua todos los puntos críticos de una obra*.

| Limitación de la supervisión humana | Cómo lo aborda SafeSite-Agent |
|---|---|
| Monitoreo discontinuo y limitado | Observación continua del flujo de video |
| Tiempo de reacción variable | Alerta automática por WhatsApp en segundos |
| Criterio subjetivo y fatiga | Criterio estandarizado (confirmación temporal K=3) |
| Dificultad para atender eventos simultáneos | Memoria por zona y clase, sin notificaciones duplicadas |

**Entorno de operación:** obra de construcción (área piloto). Ambiente *parcialmente observable, estocástico, secuencial, dinámico y continuo*, gestionado por un **agente único**.

---

## Cómo funciona el agente

### Percepción

- **Modelo:** YOLOv8s entrenado por el proyecto (checkpoint de despliegue: `runs/safesite/tuned_v2_s/weights/best.pt`).
- **Umbrales por clase:** menos exigencia para las clases débiles. En el perfil de evaluación, las faltas `no_*` se aceptan con confianza de 0.15 o mas, y el resto de clases con 0.35 o mas.
- **Perfiles de operación:** el perfil `evaluacion` (umbral global 0.15) es el de las métricas validadas; el perfil `vivo` (por clase: no_helmet 0.18, no_goggle 0.18, no_gloves 0.25, no_boots 0.15, mas una regla de coherencia por persona) es el usado en sesiones reales con webcam para reducir falsas alarmas.

### Razonamiento temporal

- Una clase `no_*` vista en un fotograma inicia una **racha**. La racha se rompe si la clase desaparece.
- La falta se **confirma al tercer fotograma consecutivo** (K=3): es el momento exacto en que se dispara la alerta.
- Una racha ya confirmada no vuelve a alertar hasta que el cooldown lo permita.

### Memoria y anti-spam

- **Cooldown por (zona, clase):** 30 segundos mínimo entre alertas del mismo tipo en la misma zona.
- **Límites del canal de WhatsApp:** mínimo 60 segundos entre cualquier par de mensajes y tope de 20 mensajes por hora rodante.
- **Historial persistente:** todos los incidentes confirmados quedan en `runs/agente/historial_incidentes.jsonl`.

### Actuadores

- **WhatsApp Business Cloud API (Meta):** un mensaje consolidado con la lista de faltas y una foto anotada, por ejemplo: *"Detectamos varios incumplimientos de EPP en la zona norte: un trabajador SIN CASCO, un trabajador SIN GUANTES"*.
- **Webhook conversacional:** el supervisor responde **INFO** y recibe la métrica técnica del incidente. El circuito completo (webhook, túnel HTTPS y auto-registro en Meta) arranca con un solo comando (`piloto.py`).
- **Panel web en vivo (Flask + MJPEG):** video anotado en tiempo real, tarjetas de EPP por clase, log de incidentes y botones para pausar WhatsApp o forzar una alerta.

---

## Resultados medidos

Todas las medidas de desempeño se pre-registraron **antes** de construir el agente. Corrida oficial (GPU local, 5 repeticiones, 14 de octubre de 2026):

| Medida | Qué mide | Fórmula | Objetivo | Resultado |
|---|---|---|---|---|
| **M1** Recall de incidente | de las escenas con falta, en cuántas el agente alerta | escenas con alerta / escenas con falta | 0.70 o mas | **0.964 val / 0.962 test** |
| **M2** Falsas alarmas | de las escenas sin falta, en cuántas alerta igual | escenas control alertadas / escenas control | 0.10 o menos | **0.035 val / 0.026 test** |
| **M3** Tiempo de notificación | cuánto tarda en llegar el aviso | confirmación + procesamiento + envío | menos de 10 s | **2.99 s** |
| **M4** Cooldown anti-spam | que no repita la misma alerta en la ventana | alertas duplicadas | 0 | **S6 = 1 alerta, S7 = 2** |

Métricas del agente a nivel de escena (umbrales reales de operación):

| Split | Escenas con falta | Escenas control | TP | FN | FP | TN | Accuracy | Precisión | Recall (M1) | F1 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| val | 28 | 115 | 27 | 1 | 4 | 111 | 0.965 | 0.871 | 0.964 | 0.915 |
| test | 26 | 114 | 25 | 1 | 3 | 111 | 0.971 | 0.893 | 0.962 | 0.926 |

Recuperación de incumplimientos por clase de riesgo (simulación de video con K=3):

| Clase de riesgo | Recall val | Recall test |
|---|---:|---:|
| no_helmet (sin casco) | 96.3 % | 83.3 % |
| no_goggle (sin gafas) | 44.0 % | 54.2 % |
| no_gloves (sin guantes) | 78.3 % | 65.2 % |
| no_boots (sin botas) | 0.0 % | 33.3 % |
| **Cualquier falta en escena** | **96.4 %** | **96.2 %** |

**La idea central del proyecto:** el detector falla mucho caja por caja en las clases débiles (`no_boots` y `no_goggle` tienen F1 casi nulo por el desbalance del dataset), pero el agente las confirma viéndolas 3 frames seguidos y llega a un F1 de escena de 0.92. La confirmación temporal compensa la debilidad del detector.

**Rendimiento:** cerca de 31.5 ms por fotograma en GPU (RTX 4050), sobrado para el objetivo de alerta en menos de 10 segundos. En CPU el mismo pipeline tarda entre 0.5 y 0.9 s por fotograma.

---

## El dataset y su análisis

Dataset oficial **Construction PPE** de Ultralytics: 1,416 imágenes de obra con 11,521 cajas en 11 clases (persona, 5 EPP, 4 faltas `no_*` y una clase de ruido).

| Clase | Cajas | Clase | Cajas |
|---|---:|---|---:|
| Person | 2,245 | no_gloves | 556 |
| helmet | 1,734 | no_helmet | 485 |
| vest | 1,618 | no_goggle | 411 |
| boots | 1,597 | goggles | 518 |
| gloves | 1,445 | none | 797 |
| | | **no_boots** | **115** |

El análisis exploratorio (EDA) se hizo **antes de construir el agente**, con hallazgos que definieron el diseño:

- **Integridad:** etiquetas YOLO verificadas una por una contra los metadatos oficiales, sin una sola discrepancia (hallazgo F1).
- **Contaminación de splits:** el split original tenía 112 imágenes del test oficial dentro de train y no existía validación. Se rehízo el split completo (`dataset_v2/`: train 1,130, val 143, test 140, todo etiquetado) antes de entrenar (F2, F3, F4).
- **Desbalance severo:** solo el 20.3 % de las imágenes de train muestra alguna falta `no_*`; `no_boots` tiene 115 cajas de 11,521 (1 %), por ser la clase mas difícil de detectar. De ahí salieron los umbrales por clase y la medición por escena (F5).
- **Regla de anidamiento descartada:** buscar el casco dentro de la caja de la persona falla el 38.2 % de las veces, así que las decisiones usan solo las clases `no_*` explicitas (F6).
- **Objetos pequeños:** la caja mediana ocupa el 1.85 % de la imagen, por lo que la resolución de inferencia se mantiene en 640 px o mas (F7).

Los detalles completos están en [`Documentation/EDA_SAFESITE_DATASET.md`](Documentation/EDA_SAFESITE_DATASET.md) y las 6 figuras del análisis en `eda/figuras/`.

---

## Estructura del repositorio

```
SAFESITE-AGENT/
├── AGENTS.md                        # convenciones para agentes de IA que trabajen en el repo
├── README.md                        # este documento
├── requirements.txt                 # dependencias del entorno de ejecución
├── .env.example                     # plantilla de credenciales de WhatsApp (copiar a .env)
├── construction-ppe.ndjson           # metadatos oficiales del dataset (solo lectura)
├── image_downloader.py               # pipeline original de descarga (obsoleto: URLs CDN expiradas)
├── safesite_dataset/                # DATO CRUDO: respaldo del dataset (no regenerable desde internet)
├── dataset_v2/                      # re-split OFICIAL para entrenar (images, labels, dataset.yaml)
├── eda/
│   ├── 01_inspeccion_ndjson.py      # análisis exploratorio reproducible (seed 42)
│   ├── 02_analisis_etiquetas.py
│   ├── 03_analisis_imagenes.py
│   ├── 04_figuras.py                # genera las 6 figuras de eda/figuras/
│   ├── 05_complementos.py
│   ├── 06_resplit_oficial.py        # produce dataset_v2/
│   ├── 07_oversampling_dataset_v3.py
│   ├── salidas/                     # resúmenes JSON del EDA y métricas por clase
│   └── figuras/                     # fig1 a fig6 en PNG
├── src/
│   ├── entrenamiento/
│   │   └── entrenar_baseline.py     # entrena YOLOv8 (seed 42, workers=0 en Windows)
│   └── safesite/                    # NÚCLEO DEL AGENTE
│       ├── agente.py                # orquestador: percibir, razonar, actuar
│       ├── percepcion.py            # wrapper de YOLO + umbrales por clase + dibujo anotado
│       ├── razonamiento.py          # confirmación temporal K=3 y filtro por clase
│       ├── memoria.py               # cooldown anti-spam e historial jsonl
│       ├── actuarios.py             # consola y WhatsApp Business Cloud API
│       ├── config.py                # parámetros centrales (umbrales, K, cooldown)
│       ├── demo.py                  # simulación de video sobre el dataset con métricas
│       ├── pruebas_medidas.py       # suite M1-M4: 13 escenarios y splits completos
│       ├── panel.py                 # panel web Flask + MJPEG con webcam en vivo
│       ├── piloto.py                # webhook + túnel cloudflared + auto-registro en Meta
│       ├── servidor_webhook.py      # webhook stdlib para el circuito conversacional (INFO)
│       ├── prueba_whatsapp.py       # prueba de alertas rotativas (envía mensajes reales)
│       ├── capturar_banco.py        # captura de escenarios reales por webcam
│       └── banco_vivo.py            # evaluación de perfiles sobre el banco en vivo
├── deploy/
│   ├── app.py                       # demo web Gradio (6 pestañas) para local o servidor
│   ├── modal_app.py                 # despliegue de esa demo en Modal (24/7, escala a cero)
│   ├── Dockerfile                   # imagen Docker de la demo (CPU, validada)
│   ├── demo_publica.py              # plan de emergencia: demo local + túnel cloudflared
│   ├── sincronizar_space.py         # historial: armado de paquete para Hugging Face
│   ├── requirements.txt            # dependencias solo de la demo
│   └── estatica/                    # variante estática (modelo ONNX en el navegador)
├── tests/
│   └── test_nucleo.py               # 13 pruebas del núcleo sin modelo ni dataset
├── .github/
│   └── workflows/
│       └── tests.yml                # CI: pytest en cada push y pull request
├── runs/                            # artefactos de ejecución (entrenamientos, evidencias)
└── Documentation/
    ├── BITACORA.md                  # bitácora de TODAS las ejecuciones (E1 a E54)
    ├── EDA_SAFESITE_DATASET.md      # informe del EDA (hallazgos F1 a F10)
    ├── ROADMAP_AGENTE.md            # plan de ejecución (Fases 0 a 5)
    ├── DESARROLLO_AGENTE.md         # desarrollo completo con UML del agente
    ├── ANALISIS_PRUEBAS.md          # interpretación de la suite de pruebas
    ├── MATRIZ_DECISION.md           # decisión del proyecto (Fase 1)
    ├── TABLA_CAMBIOS.md             # cambios del documento de diseño
    ├── GUION_VIDEO.md               # guion de la presentación
    ├── ENUNCIADO.md                 # enunciado de la entrega
    ├── WHATSAPP_LIMITES_COSTOS.md   # límites y costos de la Cloud API
    ├── SKILLS.md                    # skills de IA instaladas y procedencia
    └── BITACORA_USO_IA.md           # registro del uso de herramientas de IA
```

---

## Requisitos e instalación

**Requisitos previos**

- Python 3.11 o superior (probado en 3.12 y 3.14)
- Git
- Opcional: GPU NVIDIA para entrenamiento e inferencia acelerada (todo funciona en CPU, mas lento)
- Opcional: cuenta de WhatsApp Business Cloud API (Meta Developers) para alertas reales; sin credenciales el actuador funciona en modo DRY-RUN (construye y registra el mensaje, no lo envía)

**Pasos de instalación** (PowerShell, Windows)

```powershell
# 1. clonar
git clone https://github.com/WilliamLzn/SAFESITE-AGENT.git
cd SAFESITE-AGENT

# 2. entorno virtual
python -m venv .venv
.venv\Scripts\activate

# 3. dependencias
pip install -r requirements.txt
# con GPU NVIDIA: instalar torch con CUDA desde el índice de PyTorch
# https://pytorch.org/get-started/locally/

# 4. credenciales de WhatsApp (opcional; sin esto corre en DRY-RUN)
Copy-Item .env.example .env
# editar .env con el token, phone_id, destinatario y credenciales de la app

# 5. verificar la instalación (13 pruebas del núcleo, no necesita GPU)
python -m pytest tests -q
```

---

## Cómo ejecutar el proyecto

Todos los comandos se corren **desde la raíz del repositorio**. Con el entorno activado (`.venv\Scripts\activate`) basta `python -m ...`; aquí se muestra la forma completa con la ruta del venv.

**1. Demo del agente sobre el dataset** (simulación de video con métricas de incidente; no necesita credenciales)

```powershell
.venv\Scripts\python.exe -m src.safesite.demo
```

**2. Suite de pruebas de la entrega** (medidas M1 a M4, 13 escenarios, logs descargables)

```powershell
.venv\Scripts\python.exe -m src.safesite.pruebas_medidas --device 0
```

**3. Panel web en vivo por webcam** (video anotado en http://localhost:5000)

```powershell
.venv\Scripts\python.exe -m src.safesite.panel --device 0
```

**4. Piloto de WhatsApp** (webhook, túnel y auto-registro en Meta; arranca el circuito conversacional completo)

```powershell
.venv\Scripts\python.exe -m src.safesite.piloto
```

**5. Prueba de alertas rotativas** (envía mensajes reales de WhatsApp; requiere credenciales en .env)

```powershell
.venv\Scripts\python.exe -m src.safesite.prueba_whatsapp --escenas 3 --device 0
```

**6. Entrenar un nuevo modelo** (el script no sobrescribe runs existentes: use un nombre nuevo)

```powershell
.venv\Scripts\python.exe src\entrenamiento\entrenar_baseline.py --name mi_run
# variante mas grande (la que produjo el modelo de despliegue):
.venv\Scripts\python.exe src\entrenamiento\entrenar_baseline.py --model yolov8s.pt --name mi_run_s
```

**7. Reproducir el EDA** (scripts de análisis y figuras)

```powershell
python eda\01_inspeccion_ndjson.py
python eda\02_analisis_etiquetas.py
python eda\03_analisis_imagenes.py
python eda\04_figuras.py
python eda\05_complementos.py
```

**8. Pruebas automáticas del núcleo**

```powershell
.venv\Scripts\python.exe -m pytest tests -q
```

**Notas operativas**

- En Windows, el DataLoader de entrenamiento debe usar `workers=0` (riesgo de WinError 1455).
- Una sola sesión de agente a la vez sobre el repositorio.
- Para WhatsApp, si pasan mas de 24 horas sin actividad el supervisor debe escribir primero al número de prueba (ventana de 24 horas de la API).

---

## Pruebas y CI

- **Suite de desempeño** (`src/safesite/pruebas_medidas.py`): las 4 medidas pre-registradas M1 a M4, con 13 escenarios (normales, límite y de falla) por 5 repeticiones, mas M1 y M2 sobre las 283 escenas de validación y test. Los logs quedan en `runs/agente/pruebas/` (JSONL, CSV, JSON y tabla Markdown).
- **Pruebas del núcleo** (`tests/test_nucleo.py`): 13 pruebas que validan la lógica del agente sin modelo ni dataset (confirmación K=3, rachas, umbrales por clase, coherencia, cooldown, contención, re-anclaje de gafas, frames inválidos).
- **Integración continua** (`.github/workflows/tests.yml`): GitHub Actions corre pytest en cada push y pull request.

---

## La demo web pública

La demo completa (Gradio) está publicada y disponible 24/7 con arranque automático:

**https://williamlzn--demo.us-east.modal.run**

- La app **duerme** cuando nadie la usa (no consume) y **despierta sola** con la primera visita: la primera carga tarda entre 1 y 3 minutos (carga de PyTorch); luego responde con fluidez.
- Incluye: demo en vivo (webcam, imágenes propias y fotos del set de test con su etiqueta oficial), fallas del sensor, la suite M1-M4 en vivo, resultados oficiales y el EDA con sus figuras.
- **Publicar o actualizar** (requiere `pip install modal` y `modal token new` una sola vez):

```powershell
$env:PYTHONUTF8 = '1'
.venv\Scripts\python.exe -m modal deploy deploy\modal_app.py
```

**Alternativas documentadas** (cada una con su evidencia en la bitácora):

| Vía | Comando | Estado |
|---|---|---|
| Modal (permanente, escala a cero) | `modal deploy deploy\modal_app.py` | activa |
| Demo local completa | `.venv\Scripts\python.exe deploy\app.py --tema grafito` | http://localhost:7860 |
| Demo desde el propio PC con túnel | `.venv\Scripts\python.exe deploy\demo_publica.py` | emergencia |
| Variante estática (ONNX en el navegador) | `deploy\estatica\publicar_pages.py` | respaldo en GitHub Pages |

La bitácora (`Documentation/BITACORA.md`, entradas E48 a E54) documenta el diagnóstico completo de plataformas: los planes gratuitos con servidor de Hugging Face, Claw Cloud y Render se descartaron con evidencia (cobro, bloqueo silencioso y memoria insuficiente), y la solución final usa contenedores on-demand de Modal.

---

## Documentación

| Documento | Contenido |
|---|---|
| [Documentation/DESARROLLO_AGENTE.md](Documentation/DESARROLLO_AGENTE.md) | Desarrollo completo del agente con diseño, UML y decisiones |
| [Documentation/EDA_SAFESITE_DATASET.md](Documentation/EDA_SAFESITE_DATASET.md) | Informe del análisis exploratorio de datos (hallazgos F1 a F10) |
| [Documentation/BITACORA.md](Documentation/BITACORA.md) | Registro de todas las ejecuciones: comandos, semillas y resultados |
| [Documentation/ROADMAP_AGENTE.md](Documentation/ROADMAP_AGENTE.md) | Plan de ejecución por fases y criterios pre-registrados |
| [Documentation/ANALISIS_PRUEBAS.md](Documentation/ANALISIS_PRUEBAS.md) | Interpretación de los resultados de la suite |
| [Documentation/GUION_VIDEO.md](Documentation/GUION_VIDEO.md) | Guion de la presentación del proyecto |
| [Documentation/WHATSAPP_LIMITES_COSTOS.md](Documentation/WHATSAPP_LIMITES_COSTOS.md) | Límites y costos de WhatsApp Business Cloud API |
| [AGENTS.md](AGENTS.md) | Convenciones para agentes de IA en este repositorio |

---

## Créditos

| | |
|---|---|
| **Universidad** | Universidad Tecnológica de Bolívar |
| **Programa** | Ingeniería en Sistemas y Computación |
| **Presentado por** | William David Lozano Julio, T00078475 |
| **Curso** | Inteligencia Artificial |
| **Docente** | Edwin Alexander Puertas Del Castillo |
| **Periodo** | Agosto a octubre de 2026 |

---

## Referencias

- Russell, S. J., y Norvig, P. *Artificial Intelligence: A Modern Approach*.
- Ultralytics: *YOLOv8* y el dataset *Construction PPE*.
- Meta: *WhatsApp Business Cloud API*.
- Modal: *serverless cloud para contenedores*.
- Kassis, T., et al. (2026). *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*. arXiv.

---

## Nota de transparencia

Este proyecto fue desarrollado con ayuda de agentes de inteligencia artificial (OpenCode y modelos de lenguaje) para análisis de datos, redacción de documentación y depuración de código. Todo el contenido refleja fielmente los archivos del repositorio y los datos reales medidos en los experimentos. La bitácora de uso de IA está en [`Documentation/BITACORA_USO_IA.md`](Documentation/BITACORA_USO_IA.md) y el registro completo de ejecuciones en [`Documentation/BITACORA.md`](Documentation/BITACORA.md).
