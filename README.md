<p align="center">
  <img src="https://img.shields.io/badge/Estado-Diseño_y_Dataset-blue?style=for-the-badge" alt="Estado">
  <img src="https://img.shields.io/badge/Modelo-YOLO-brightgreen?style=for-the-badge&logo=python&logoColor=white" alt="Modelo">
  <img src="https://img.shields.io/badge/Tarea-Detección_de_Objetos-yellow?style=for-the-badge" alt="Tarea">
  <img src="https://img.shields.io/badge/Canal-WhatsApp_Business-25D366?style=for-the-badge&logo=whatsapp&logoColor=white" alt="Canal">
  <img src="https://img.shields.io/badge/Idioma-Español-red?style=for-the-badge" alt="Idioma">
</p>

<h1 align="center">👷 SAFESITE-AGENT</h1>

<p align="center">
  <strong>Agente inteligente de monitoreo de seguridad en obra</strong><br/>
  Detección de elementos de protección personal (EPP) en tiempo real sobre video de cámaras IP/CCTV
</p>

<p align="center">
  <em>Proyecto de Inteligencia Artificial — Universidad Tecnológica de Bolívar</em>
</p>

---

## 📌 Índice

- [¿Qué es SafeSite-Agent?](#-qué-es-safesite-agent)
- [El problema que resuelve](#-el-problema-que-resuelve)
- [Cómo funciona (arquitectura del agente)](#-cómo-funciona)
- [El dataset: Construction PPE](#-el-dataset-construction-ppe)
- [Estructura del repositorio](#-estructura-del-repositorio)
- [Quick Start](#-quick-start)
- [Formato de etiquetas YOLO](#-formato-de-etiquetas-yolo)
- [Estado del proyecto y roadmap](#-estado-del-proyecto-y-roadmap)
- [Créditos](#-créditos)

---

## 🤖 ¿Qué es SafeSite-Agent?

**SafeSite-Agent** es un agente de software diseñado para **percibir de forma continua** el video de las cámaras instaladas en un área piloto de una obra de construcción, **razonar** sobre lo observado y **actuar de manera autónoma** emitiendo alertas en tiempo real cuando detecta que un trabajador no usa su equipo de protección personal (casco, guantes, chaleco, entre otros).

Se clasifica principalmente como un **model-based reflex agent** (agente reactivo basado en modelos) complementado con un componente de **utilidad** para priorizar alertas. Es decir, su decisión no depende solo del fotograma actual: mantiene un estado interno que le permite distinguir si un incumplimiento es un evento aislado o un patrón recurrente en una zona determinada.

> Su valor está en operar **sin pausas**, reducir el tiempo de reacción frente a incumplimientos y estandarizar un criterio de verificación que, a diferencia del ojo humano, no se ve afectado por la fatiga ni por la simultaneidad de eventos en la obra.

---

## 🚧 El problema que resuelve

El incumplimiento en el uso de EPP es una de las **principales causas de accidentalidad** en el sector de la construcción. La supervisión manual tiene un límite claro: *un supervisor no puede observar de manera simultánea y continua todos los puntos críticos de una obra*.

| Limitación de la supervisión humana | Cómo lo aborda SafeSite-Agent |
|-------------------------------------|-------------------------------|
| Monitoreo discontinuo y limitado | Observación continua del flujo de video |
| Tiempo de reacción variable | Alertas automáticas en tiempo real |
| Criterio subjetivo y afectado por la fatiga | Criterio estandarizado y consistente |
| Difícil atender eventos simultáneos | Procesamiento paralelo del video de varias cámaras |

**Entorno de operación:** una obra de construcción (área piloto delimitada y puntos de acceso). Es un ambiente *parcialmente observable, estocástico, secuencial, dinámico y continuo*, gestionado por un **agente único**.

---

## ⚙️ Cómo funciona

El agente combina un modelo de visión por computador (**YOLO**) con reglas de decisión y memoria. El pipeline conceptual:

```
          ┌──────────────────────────────────────────────────────────────┐
          │                   ENTORNO (obra de construcción)             │
          │   cámaras IP/CCTV ▪ trabajadores ▪ condiciones del clima     │
          └──────────────────────────────────────────────────────────────┘
                                     │  video RGB
                                     ▼
   ┌───────────────────────────────────────────────────────────────────────────┐
   │                       PERCEPCIÓN Y MANEJO DE ENTRADAS                     │
   │   ▪ muestreo de fotogramas ▪ detección de personas ▪ clasificación de EPP │
   │   ▪ metadatos de captura (marca de tiempo, zona, cámara)                  │
   └───────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
   ┌───────────────────────────────────────────────────────────────────────────┐
   │                       RAZONAMIENTO Y TOMA DE DECISIONES                   │
   │   ▪ reglas: EPP completo / incompleto                                      │
   │   ▪ memoria de corto plazo (evita notificaciones duplicadas)              │
   │   ▪ historial por zona y horario (prioriza patrones recurrentes)          │
   └───────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
   ┌───────────────────────────────────────────────────────────────────────────┐
   │                               ACTUADORES                                  │
   │   ▪ WhatsApp Business bot announcer → alerta al supervisor HSE            │
   │   ▪ Panel de supervisión → video con bounding boxes superpuestos          │
   │   ▪ Actualización de historial → persistente por zona/horario             │
   └───────────────────────────────────────────────────────────────────────────┘
```

**Medidas de desempeño objetivo:**
- ✅ Exactitud (accuracy) de detección de EPP **≥ 90 %** en el área piloto.
- ⏱️ Alerta vía WhatsApp en **menos de 10 segundos** desde que se detecta el incumplimiento.
- 📉 Reducción del **30 %** en el tiempo promedio de detección frente a la supervisión manual.

---

## 📊 El dataset: Construction PPE

Construido sobre el dataset oficial **Construction PPE** (Ultralytics) para la tarea de **detección de objetos**. Aporta los datos con los que se entrena el modelo de visión del agente.

<p align="center">
  <img src="https://img.shields.io/badge/1.416-imágenes-informational?style=flat-square" alt="imágenes">
  <img src="https://img.shields.io/badge/11-clases-informational?style=flat-square" alt="clases">
  <img src="https://img.shields.io/badge/11.521-bounding_boxes-informational?style=flat-square" alt="bounding boxes">
</p>

**Split oficial del dataset:**

| Split  | Imágenes | Uso                     |
|--------|----------|-------------------------|
| Train  | 1,132    | Entrenamiento con etiquetas |
| Valid  | 143      | Validación del modelo       |
| Test   | 141      | Evaluación                  |

> ℹ️ **Nota sobre el repositorio:** el script `image_downloader.py` realiza su **propio split 80/20** sobre los 1,416 registros: descarga **1,129 imágenes con etiquetas** (carpeta `train/`) y **284 imágenes sin etiquetas** (carpeta `test/`), de modo que las etiquetas de test pueden generarse posteriormente para evaluación.

**Las 11 clases (y su frecuencia en las 11,521 cajas etiquetadas):**

| ID | Clase         | Cajas | ID | Clase     | Cajas |
|----|---------------|-------:|----|-----------|------:|
| 0  | helmet        | 1,734  | 6  | Person    | 2,245 |
| 1  | gloves        | 1,445  | 7  | no_helmet | 485   |
| 2  | vest          | 1,618  | 8  | no_goggle | 411   |
| 3  | boots         | 1,597  | 9  | no_gloves | 556   |
| 4  | goggles       | 518    | 10 | no_boots  | 115   |
| 5  | none          | 797    |    |           |       |

Las clases `no_*` representan el **EPP ausente** (el caso de incumplimiento que interesa al agente), mientras que las clases restantes modelan el equipo presente sobre cada persona.

---

## 🗂️ Estructura del repositorio

```
SAFESITE-AGENT/
├── construction-ppe.ndjson         # Metadata del dataset (registros de imagen + anotaciones)
├── image_downloader.py             # Descarga de imágenes + generación de etiquetas YOLO
├── README.md                       # Este documento
├── Documentation/
│   └── Diseño_Agente_SafeSite.pdf  # Documento de diseño del agente
└── safesite_dataset/
    ├── train/                      # Imágenes + etiquetas .txt (formato YOLO)
    └── test/                       # Imágenes (sin etiquetas, listas para evaluación)
```

---

## 🚀 Quick Start

Requisitos: **Python 3** y el paquete `requests`.

```bash
# 1. Instalar dependencia
pip install requests

# 2. Ejecutar el pipeline de preparación del dataset
python image_downloader.py
```

El script `image_downloader.py` realiza las siguientes tareas:
1. Lee los registros de imagen del archivo `construction-ppe.ndjson`.
2. Mezcla y particiona los datos en **80% train / 20% test** (semilla `42` para reproducibilidad).
3. **Descarga imágenes** desde las URL del CDN de Ultralytics.
4. **Genera etiquetas YOLO** (`.txt`) para cada imagen de `train/` a partir de las anotaciones del NDJSON; las imágenes de `test/` se descargan **sin etiquetas**, para poder evaluarlas posteriormente.

---

## 🏷️ Formato de etiquetas YOLO

Cada imagen de entrenamiento tiene asociado un archivo `.txt` del mismo nombre, donde **cada línea** representa un objeto en el formato:

```
<class_id> <x_center> <y_center> <width> <height>
```

> Las coordenadas están **normalizadas** (valores entre 0 y 1) respecto al ancho y alto de la imagen.

Ejemplo real (`00820783fe0983a4dc3f2435e928a038.txt`):

```text
0 0.361090 0.359030 0.230440 0.158430      # helmet
2 0.364160 0.679010 0.380640 0.230440      # vest
6 0.374730 0.521860 0.488850 0.562920      # Person
```

---

## 🗓️ Estado del proyecto y roadmap

**⚠️ Fase actual — diseño y preparación de datos:**
- ✅ Documento de diseño del agente (`Documentation/`).
- ✅ Pipeline de descarga y etiquetado del dataset en formato YOLO.
- ✅ Dataset de entrenamiento (train) descargado y etiquetado.

**🔜 Siguientes fases (desarrollo):**
- ⬜ Entrenamiento y tuning del modelo de detección (YOLO).
- ⬜ Integración del flujo de video en tiempo real.
- ⬜ Reglas de decisión + memoria (historial por zona/horario).
- ⬜ Bot announcer de WhatsApp Business.
- ⬜ Panel de supervisión con bounding boxes en vivo.
- ⬜ Reentrenamiento con falsos positivos/negativos reportados por supervisores.

---

## 🎓 Créditos

**SAFESITE-AGENT** es un proyecto académico de la asignatura **Inteligencia Artificial**:

| | |
|---|---|
| **Universidad** | Universidad Tecnológica de Bolívar |
| **Programa** | Ingeniería en Sistemas y Computación |
| **Presentado por** | William David Lozano Julio — T00078475 |
| **Curso** | Inteligencia Artificial |
| **Docente** | Edwin Alexander Puertas Del Castillo |
| **Fecha** | 28/08/2026 |

**Referencias:**
- Russell, S. J., & Norvig, P. *Artificial Intelligence: A Modern Approach*.
- IBM — *Components of AI agents*.
- Ultralytics — *Construction-PPE Dataset*.
- *PPE detector: a YOLO-based architecture...* (PMC).

---

<sub>
**Nota de transparencia:** este README fue redactado con la ayuda de agentes de inteligencia artificial — específicamente **Big Pickle** (modelo `opencode/big-pickle`, ejecutado en la herramienta de asistencia OpenCode) y **Anthropic Claude** — que analizaron el dataset, el código y el documento de diseño del proyecto para generar la documentación. El contenido refleja fielmente los archivos existentes en el repositorio y los datos reales del dataset, sin elementos inventados.
</sub>
