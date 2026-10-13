# 📊 EDA — Dataset Construction PPE (SafeSite-Agent)

| | |
|---|---|
| **Proyecto** | SAFESITE-AGENT — Agente de monitoreo de EPP en obra |
| **Fecha del análisis** | 13 de octubre de 2026 |
| **Datos analizados** | `construction-ppe.ndjson` (metadatos oficiales) + `safesite_dataset/` (imágenes y etiquetas en disco) |
| **Metodología** | Skill `exploratory-data-analysis` de [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) — análisis acotado, datos crudos en **solo lectura**, artefactos derivados separados en `eda/` |
| **Software** | Python 3.14.6, Pillow 12.3.0, matplotlib 3.11.2, numpy 2.5.2 |
| **Scripts** | `eda/01…05_*.py` (reproducibles, semilla 42 donde hay muestreo) |
| **Bitácora** | `Documentation/BITACORA.md` |

---

## 🎯 Resumen ejecutivo

El dataset está **íntegro y en formato YOLO correcto** (verificado 1:1 contra los metadatos oficiales), pero presenta **tres riesgos para el proyecto**: (1) el split 80/20 propio ignora el split oficial y contamina train con 112 imágenes del test oficial; (2) las clases de incumplimiento (`no_*`) —el objetivo del agente— son minoritarias (13.6% de las cajas) y solo aparecen en el **20.3%** de las imágenes de train; (3) no existe un conjunto de validación propio. La resolución dominante es 640×640 (78.8%) y hay un 4.5% de imágenes muy oscuras, relevante para operación CCTV.

**Veredicto:** apto para entrenar un baseline de forma inmediata, con correctivos de split y balance antes de reportar métricas comparables.

---

## 1. Alcance y metodología

| Análisis | Alcance | Herramienta |
|---|---|---|
| Perfil NDJSON | Los 1,417 registros (100%) | stdlib `json` |
| Etiquetas YOLO en disco | Los 1,129 `.txt` de `train/` (100%) | stdlib |
| Integridad imagen↔etiqueta | Los 1,413 JPG en disco (100%) | stdlib |
| Metadatos de imagen | Los 1,413 JPG (100%), solo contenedor (Pillow) | Pillow |
| Brillo/contraste | **Muestra determinista n=200 (~14%), seed 42 — EXPLORATORIO** | Pillow |

Reglas aplicadas de la skill: datos crudos sin modificar; hallazgos *post-hoc* marcados como exploratorios; no se hacen afirmaciones causales; alcance reportado sin extrapolación silenciosa.

## 2. Diccionario de datos

**NDJSON** (`construction-ppe.ndjson`, 1,417 líneas — 1 registro `dataset` + 1,416 `image`):

| Campo | Tipo | Significado |
|---|---|---|
| `type` | str | `dataset` \| `image` |
| `file` | str | Nombre del JPG (hash) |
| `url` | str | CDN de Ultralytics (no se accedió durante el EDA) |
| `width`, `height` | int | Dimensiones declaradas de la imagen |
| `split` | str | **Split oficial Ultralytics**: `train` / `val` / `test` |
| `annotations.boxes` | list | Cajas `[class_id, x, y, w, h]` normalizadas, **formato centro** (verificado en §4.4) |
| `class_names` | dict | 11 clases: `helmet, gloves, vest, boots, goggles, none, Person, no_helmet, no_goggle, no_gloves, no_boots` |

**Etiquetas en disco** (formato YOLO): `<class_id> <x_center> <y_center> <width> <height>`, normalizadas 0–1.

## 3. Inventario e integridad

| Verificación | Resultado |
|---|---|
| JPG en `train/` | 1,129 |
| TXT en `train/` | 1,129 — emparejamiento 1:1, **0 imágenes sin etiqueta, 0 etiquetas huérfanas** |
| JPG en `test/` | 284 (sin etiquetas, como define el pipeline) |
| Duplicados entre carpetas | 0 |
| Registros NDJSON nunca descargados | **3** (fallas de descarga del run original) |
| JPG en disco sin registro NDJSON | 0 |
| Imágenes que no abren / corruptas | 0 (todas JPEG, RGB) |
| Dimensiones disco vs NDJSON | **0 desajustes** |
| Líneas mal formadas en TXT | 0 |
| Valores fuera de rango [0,1] | 0 |
| TXT ≠ NDJSON (contenido) | **0 archivos discrepantes** |

✅ **Conclusión de integridad:** el pipeline `image_downloader.py` produjo etiquetas fieles al 100% a los metadatos oficiales. No se encontró ningún error de generación.

## 4. Análisis de etiquetas

### 4.1 Distribución de clases

Dataset completo (11,521 cajas) — [Fig. 1](../eda/figuras/fig1_clases.png):

| Clase | Cajas | % | | Clase | Cajas | % |
|---|---:|---:|---|---|---:|---:|
| Person | 2,245 | 19.49% | | goggles | 518 | 4.50% |
| helmet | 1,734 | 15.05% | | **no_gloves** | 556 | 4.83% |
| vest | 1,618 | 14.04% | | **no_helmet** | 485 | 4.21% |
| boots | 1,597 | 13.86% | | **no_goggle** | 411 | 3.57% |
| gloves | 1,445 | 12.54% | | **no_boots** | **115** | **1.00%** |
| none | 797 | 6.92% | | **Total `no_*`** | **1,567** | **13.60%** |

- **Desbalance severo**: la clase más rara (`no_boots`, 115 cajas) tiene **19.5× menos ejemplos** que la más frecuente (`Person`).
- ⚠️ **Hallazgo crítico para el objetivo del agente**: solo **229 de 1,129 imágenes de train (20.3%)** contienen al menos una caja `no_*`. El 79.7% de train no aporta señal de incumplimiento.
- La distribución en `train/` en disco es proporcional al NDJSON (p.ej. Person 19.42%, no_boots 0.95%), lo que confirma que el muestreo 80/20 no sesgó las frecuencias.

### 4.2 Densidad de objetos — [Fig. 2](../eda/figuras/fig2_cajas_por_imagen.png)

| Estadístico | Valor |
|---|---|
| Mediana de cajas/imagen | 7 |
| Media | 8.14 (SD 5.75) |
| P25–P75 | 5 – 8 |
| Máximo | **58** objetos en una imagen |

Escenas concurridas: el modelo debe manejar multitudes; el agente debe procesar detecciones múltiples por frame.

### 4.3 Geometría de cajas

| Métrica (normalizado) | Mediana | P25 | P75 | Máx |
|---|---:|---:|---:|---:|
| Área (w×h) | 0.0185 | 0.0072 | 0.0720 | 0.975 |
| Ancho | 0.1426 | 0.0875 | 0.2383 | 1.0 |
| Alto | 0.1339 | 0.0791 | 0.3201 | 1.0 |

- La **mediana de área ≈ 1.85%** de la imagen → objetos pequeños (típico de planos abiertos de obra). [Fig. 4](../eda/figuras/fig4_areas.png)
- Hay cajas que ocupan casi toda la imagen (área 0.975) → primeros planos.
- Implicación: la resolución de inferencia (p.ej. 640 px) debe preservarse; los objetos pequeños penalizan más la reducción de resolución.

### 4.4 Verificación del formato de cajas (hallazgo positivo)

El script `image_downloader.py` copia `caja[1..4]` tal cual al `.txt`. Verifiqué si el NDJSON usa formato **centro** (YOLO) o **esquina**:

| Hipótesis de formato | Violaciones encontradas |
|---|---:|
| Centro normalizado (YOLO) | **0** ✅ |
| Esquina normalizada | 2,736 ❌ |
| Valores negativos / dimensiones cero | 0 |

**Confirmado: las cajas ya vienen en formato centro YOLO normalizado y las etiquetas del proyecto son correctas.** No hay bug de formato en el pipeline.

### 4.5 Anidamiento casco⊂Persona (exploratorio)

Prueba geométrica: ¿el centro de cada caja `helmet` cae dentro de alguna caja `Person` de la misma imagen?

| Resultado | Casos |
|---|---:|
| Casco dentro de una caja Person | 1,008 (61.8%) |
| Casco fuera de toda caja Person | 623 (38.2%) |

**Implicación para el diseño del agente:** la regla "persona sin casco = Persona sin helmet anidado" **fallaría en ~38%** de los casos (personas parcialmente encuadradas, cascos en suelo/maquinaria, recortes). La decisión debe basarse en las clases `no_helmet/no_goggles/...` explícitas, no en lógica de anidamiento.

## 5. Análisis de splits — contaminación detectada

El dataset oficial define `train 1,132 / val 143 / test 141`. El proyecto re-mezcló todo con `seed 42` en 80/20 **ignorando ese campo**. Cruce real (1,413 imágenes descargadas) — [Fig. 3](../eda/figuras/fig3_splits.png):

| Carpeta del proyecto | Oficial train | Oficial val | Oficial test | Total |
|---|---:|---:|---:|---:|
| `train/` (1,129) | 915 | 102 | **112** | 1,129 |
| `test/` (284) | 215 | 41 | 28 | 284 |

Riesgos:

1. **Contaminación train←test oficial**: 112 imágenes reservadas oficialmente para evaluación están en train con etiquetas. Cualquier métrica "a ciegas" sobre test oficial dejaría de ser comparable con resultados publicados del dataset.
2. **Sin conjunto de validación propio**: el pipeline actual no reserva val; el tuning de umbrales/hiperparámetros no tiene conjunto de control.
3. **test/ sin etiquetas**: las 284 imágenes de `test/` sí tienen anotaciones en el NDJSON (se omitieron al descargar). Etiquetarlas es trivial y habilita evaluación real (ver [Roadmap](ROADMAP_AGENTE.md)).

## 6. Análisis de imágenes

### 6.1 Resoluciones — [Fig. 5](../eda/figuras/fig5_dimensiones.png)

| Resolución | Imágenes | % |
|---|---:|---:|
| **640×640** | 1,114 | 78.8% |
| 1024×768 | 41 | 2.9% |
| 1024×683 | 39 | 2.8% |
| 683×1024 | 26 | 1.8% |
| 768×1024 | 25 | 1.8% |
| 612×408 | 24 | 1.7% |
| Otras (~90 tamaños) | 144 | 10.2% |

- Relaciones de aspecto: 1.0 (79.7%), 1.5 (5.6%), 0.67 (3.0%), 1.33 (3.0%), 0.75 (2.0%) — mezcla de paisaje/retrato/cuadrado.
- YOLO letterbox-escala todo a 640; no es bloqueante, pero el agente debe **preservar la relación de aspecto al renderizar bboxes** en el panel.
- Tamaño de archivo: mediana 91.6 KB (máx 468.8 KB) — dataset liviano, carga rápida.

### 6.2 Brillo y contraste (muestra n=200, EXPLORATORIO) — [Fig. 6](../eda/figuras/fig6_brillo.png)

| Métrica | Mediana | Min | P25 | P75 | Máx |
|---|---:|---:|---:|---:|---:|
| Brillo medio (0–255) | 132 | **13.6** | 102.3 | 158.8 | 203.4 |
| Contraste (SD gris) | 65.9 | 21.7 | 56.7 | 83.0 | 116.1 |

- **9/200 imágenes (4.5%) son muy oscuras** (brillo < 60) y 48/200 (24%) < 100 → hay condiciones de noche/interior/sombra en el dataset.
- Exploratorio: si el área piloto opera de noche, conviene **aumento de datos con baja de iluminación** y validar recall en el subconjunto oscuro. El muestreo determinista (seed 42) no reemplaza una auditoría de dominio completa.

## 7. Hallazgos consolidados

| # | Hallazgo | Severidad | Impacto en el proyecto |
|---|---|---|---|
| F1 | Etiquetas YOLO correctas y 100% fieles al NDJSON; formato centro confirmado | ✅ Positivo | El dataset es entrenable **ya mismo**; no hay que regenerar nada |
| F2 | Split propio ignora el oficial; **112 test oficial en train** | 🔴 Alta | Métricas no comparables; riesgo de sobreestimar generalización |
| F3 | Sin conjunto de validación | 🔴 Alta | Tuning sin control; obligatorio crear val antes de experimentar |
| F4 | `test/` sin etiquetas aunque el NDJSON las tiene | 🟠 Media | Bloquea la evaluación cuantitativa del modelo |
| F5 | Clases `no_*` = 13.6% de cajas; `no_boots` = 1%; solo 20.3% de imágenes de train con incumplimiento | 🟠 Media | Recall bajo esperado en incumplimientos; requiere balance/aumento/métricas por clase |
| F6 | Regla casco⊂Persona falla en 38.2% | 🟠 Media | La decisión del agente debe usar clases `no_*`, no anidamiento |
| F7 | Objetos pequeños (área mediana 1.85%) y escenas densas (mediana 7 obj/img, máx 58) | 🟡 Baja | Mantener resolución de inferencia ≥640; umbral de confianza ajustado |
| F8 | 21.2% de imágenes ≠640×640, aspect ratios mixtos | 🟡 Baja | Normal en YOLO; cuidar visualización proporcional |
| F9 | 4.5% de imágenes muy oscuras (muestra) | 🟡 Baja | Considerar augmentation nocturno para CCTV 24/7 |
| F10 | 3 registros NDJSON sin descargar | 🟢 Info | Completar si se quiere el 100% del dataset |

## 8. Limitaciones del análisis

- El análisis de brillo/contraste es una **muestra del 14%** (exploratoria); los metadatos sí cubren el 100% de las imágenes.
- El EDA no certifica la calidad semántica de las anotaciones (etiquetas mal asignadas por humanos); se validó solo su fidelidad al NDJSON y su formato.
- No se evaluó similitud/duplicación de contenido visual entre imágenes (posible near-duplicate leakage entre splits propios y oficiales) — queda como trabajo futuro.
- Los porcentajes de clase provienen de las cajas, no de personas únicas: una persona puede aportar varias cajas.

## 9. Reproducibilidad

Comandos exactos (Windows PowerShell, desde la raíz del proyecto):

```powershell
python eda\01_inspeccion_ndjson.py        # perfil NDJSON
python eda\02_analisis_etiquetas.py       # etiquetas, splits, integridad
python eda\03_analisis_imagenes.py        # metadatos de imagen + muestra brillo
python eda\04_figuras.py                  # figuras 1-6 (eda/figuras/)
python eda\05_complementos.py             # porcentajes y conteos del informe
```

Salidas derivadas: `eda/salidas/resumen_eda.json`, `eda/salidas/resumen_imagenes.json`, `eda/figuras/*.png`. Semilla determinista 42 en todos los muestreos. Datos crudos sin modificar.

## 10. Referencias

- Ultralytics — Construction-PPE Dataset (dataset oficial, NDJSON del proyecto).
- Skill `exploratory-data-analysis` — K-Dense-AI/scientific-agent-skills (metodología, commit `a1043ef`).
- NIST EDA Handbook (referencia de rigor exploratorio citada por la skill).
- Kassis, T., et al. (2026). *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*. arXiv:2609.00065.
