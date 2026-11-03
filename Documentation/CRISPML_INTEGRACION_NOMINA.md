# Aplicación de CRISP-ML(Q) a SAFESITE — Extensión a Gestor y Verificador de Nómina LIVE

**Proyecto:** SAFESITE-AGENT  
**Metodología obligatoria:** CRISP-ML(Q) (Cross-Industry Standard Process for Machine Learning con énfasis en Quality)  
**Versión:** 1.1 — Flujo corregido: identificación → entrada → EPP → salida → reportes agregados  
**Fecha:** 02-nov-2026  
**Idioma:** español

---

## 1. Contexto y alcance

### 1.1 Lo que ya tenemos (SAFESITE actual)

SAFESITE es un sistema de percepción y alerta basado en visión por computadora:

| Componente | Estado | Detalle |
|---|---|---|
| Percepción | YOLOv8n / YOLOv8s | Dataset Construction PPE (11 clases, 1,416 imágenes), re-split oficial `dataset_v2/` (train/val/test) |
| Checkpoint de despliegue | `runs/safesite/tuned_v2_s/weights/best.pt` | Mejor en todas las métricas (val/test mAP50, recall `no_*`) |
| Confirmación temporal | K=3 frames | Evita falsos positivos por detección esporádica |
| Cooldown y límite | 60 s global / 20 msg/hora | Anti-spam en canal WhatsApp |
| Actuador | WhatsApp Cloud API (Meta) | Alertas con foto, payload DRY-RUN, ventana de 24 h |
| Panel | Flask + MJPEG | http://localhost:5000, video anotado en tiempo real, tarjetas EPP por clase |
| Pruebas | `pruebas_medidas.py` | 4 medidas pre-registradas (M1–M4), 13 escenarios × 5 repeticiones |
| Despliegue | Google Cloud Run | Demo web 24/7: https://safesite-ui-428834791978.us-central1.run.app |

### 1.2 La ampliación solicitada

Convertir SAFESITE en un **gestor y verificador de nómina LIVE para empresas**, manteniendo la detección de EPP como validación de cumplimiento, no como puerta de bloqueo inicial.

Flujo conceptual (según tu diseño):

```
[Trabajador llega] → [Agente 1: Nómina/Identificación] → [Marcaje entrada] → [Agente 2: EPP] → [Jornada] → [Salida] → [Reportes agregados PDF + WhatsApp]
```

---

## 2. Arquitectura de agentes: 2 agentes secuenciales (orden corregido)

Tienes razón: el orden correcto es **primero nómina/identificación, luego EPP**. No tiene sentido verificar el EPP de alguien que no está registrado en la nómina.

### 2.1 Agente 1: Identificación y verificación de nómina (primero en actuar)

| Función | Detalle |
|---|---|
| Validar si el trabajador está registrado en la nómina | Consulta `empleado`, `puesto`, `turno` por `codigo_badge` o selección manual |
| Validar su entrada | Registra `entrada_ts` en tabla `asistencia`, estado `presente` / `tardanza` / `bloqueado` |
| Decidir si permite el acceso | Basado en turno programado, tolerancia de puntualidad, reglas de empresa |
| Salida al final de jornada | Registra `salida_ts`, calcula horas trabajadas |

**Modelo:** LLM con herramientas + reglas deterministas de cálculo de horas.

**Herramientas:**
- `consultar_empleado(codigo_badge)` → devuelve si existe, puesto, turno, epp_requerido
- `registrar_entrada(empleado_id, ts, frames_evidencia)`
- `registrar_salida(empleado_id, ts)`
- `calcular_horas(entrada_ts, salida_ts, descanso_min)`
- `verificar_puntualidad(entrada_ts, turno_inicio, tolerancia)`
- `generar_liquidacion_parcial(empleado_id, fecha)`
- `enviar_alerta_whatsapp(mensaje, foto)`

### 2.2 Agente 2: Verificación de EPP (segundo en actuar)

| Función | Detalle |
|---|---|
| Analizar frame de cámara con YOLO | Detectar clases `no_helmet`, `no_goggle`, `no_gloves`, `no_boots` |
| Confirmación temporal K=3 frames | Evitar falsos positivos esporádicos |
| Verificar EPP requerido para el puesto del empleado | Cruzar `epp_requerido` del puesto con lo detectado |
| Generar incidente si falta EPP | Registrar en tabla `incidente`, tipo `falta_epp`, severidad |
| No bloquear la entrada por sí solo | La entrada ya fue validada por Agente 1; EPP genera observación/incidente, no rechazo automático |

**Modelo:** YOLOv8s (`tuned_v2_s`) + reglas deterministas (`razonamiento.py`).

**Salida:** estado_epp (cumple / incumple), confianza, frames_evidencia, incidente (si aplica).

### 2.3 Flujo secuencial completo

```
Paso 1: Trabajador se presenta en la entrada
Paso 2: Agente 1 (Nómina) valida si está registrado (badge/QR o selección manual)
        → Si no existe: rechazar acceso, registrar intento no autorizado, alerta WhatsApp "alguien raro"
        → Si existe: continuar
Paso 3: Agente 1 registra entrada (entrada_ts) y verifica puntualidad
Paso 4: Agente 2 (EPP) analiza el frame con YOLOv8s (K=3 frames)
        → Detecta si lleva el EPP requerido para su puesto
        → Si falta EPP: registrar incidente, no bloquear entrada (registro con observación)
Paso 5: Durante la jornada, el trabajador opera normalmente
Paso 6: Al final, Agente 1 registra salida (salida_ts) y calcula horas
Paso 7: Si llegaron múltiples personas en un intervalo de tiempo:
        → Generar reporte general PDF (entradas, salidas, incidentes de EPP, ausentes)
        → Enviar notificación WhatsApp resumida (entradas del período, ausencias, incidentes críticos)
```

### 2.4 ¿Por qué 2 agentes y no 1?

| Razón | Explicación |
|---|---|
| Separación de responsabilidades | Agente 1 maneja identidad, turnos, horarios y nómina. Agente 2 maneja visión y cumplimiento de EPP. |
| Datos distintos | Agente 1 consume tablas (empleado, turno, asistencia). Agente 2 consume frames de cámara. |
| Modelos distintos | Agente 1 usa LLM con herramientas. Agente 2 usa YOLOv8s. |
| Evaluación independiente | Cada agente tiene sus propias métricas pre-registradas y se puede auditar por separado. |
| Mantenibilidad | Cambiar la regla de horas extra solo toca al Agente 1. Cambiar el umbral de EPP solo toca al Agente 2. |

---

## 3. CRISP-ML(Q): fases aplicadas

| Fase | Objetivo | Qué aplica a lo existente (SAFESITE EPP) | Qué es nuevo (nómina LIVE) |
|---|---|---|---|
| **1. Business Understanding** | Definir objetivo de negocio, criterios de éxito, PEAS | PEAS del agente EPP existente | PEAS del agente de nómina, flujo identidad→entrada→EPP→salida, reportes agregados |
| **2. Data Understanding** | Explorar y validar calidad de los datos | `dataset_v2/`, `construction-ppe.ndjson`, EDA en `eda/` | Datos sintéticos de nómina (empleado, turno, asistencia), sin identificadores reales |
| **3. Data Preparation** | Limpiar, transformar, integrar | `dataset_v2/` (train 1,130 / val 143 / test 140) | Esquema BD: `empleado`, `puesto`, `turno`, `asistencia`, `incidente`, `periodo_nomina`, `liquidacion`, `regla` |
| **4. Modeling** | Seleccionar técnica, entrenar | YOLOv8s `tuned_v2_s`, reglas `razonamiento.py` | Agente LLM con herramientas (ruta E), línea base "prompt único", reglas de nómina deterministas |
| **5. Evaluation** | Evaluar contra criterios de negocio | `pruebas_medidas.py` (M1–M4), métricas por clase `no_*` | Métricas de nómina (tasa de éxito, exactitud asistencia, error de horas, errores de herramienta, reportes PDF generados correctamente) |
| **6. Deployment** | Desplegar, monitorear, mantener | Panel Flask, demo Gradio Cloud Run, `.env` | Dashboard de nómina live, API para herramientas, generación de PDF, reuso de WhatsApp |
| **(Q) Quality / Feedback** | Monitoreo continuo, re-entrenamiento | Bitácora `Documentation/BITACORA.md` | Monitoreo de falsas alarmas de nómina, recall por clase `no_*` en vivo, calidad de reportes PDF |

### 3.1 Detalle por fase (aplicado al flujo corregido)

#### Fase 1 — Business Understanding

**PEAS Agente 1 (Nómina):**
- **P (Performance):** Tasa de éxito en identificación, exactitud de entrada/salida, error de horas calculadas, reportes PDF generados sin errores.
- **E (Environment):** Entrada de obra, cámara, panel web, base de datos de nómina, WhatsApp.
- **A (Actuators):** Registro en BD, mensaje WhatsApp, generación de PDF, actualización de panel.
- **S (Sensors):** Cámara webcam, lector de badge/QR (o selección manual), base de datos.

**PEAS Agente 2 (EPP):**
- **P (Performance):** recall `no_*` ≥ 0.70, precisión de detección EPP, confirmación K=3 estable.
- **E (Environment):** Mismo puesto de entrada, condiciones de iluminación de obra.
- **A (Actuators):** Registro de incidente, tarjeta EPP en panel, alerta opcional por WhatsApp.
- **S (Sensors):** Cámara webcam.

**Criterios de éxito (pre-registrados, ejemplo):**
- M1: Tasa de éxito por tarea del agente de nómina ≥ 0.80 (vs. línea base prompt único ≈ 0.25 esperado).
- M2: Exactitud de estado de asistencia (presente/ausente/tardanza) F1 ≥ 0.85.
- M3: recall de detección de falta de EPP ≥ 0.70, precisión ≥ 0.90.
- M4: Error absoluto de horas calculadas ≤ 1 min (RMSE < 2 min).
- M5: Errores de herramienta ≤ 5% de llamadas.
- M6: Tiempo de respuesta < 5 s por tarea.
- M7: Reportes PDF generados correctamente en ≥ 95% de los intervalos solicitados.

#### Fase 2 — Data Understanding

**Datos existentes (EPP):** `safesite_dataset/` (solo lectura), `dataset_v2/` (re-split oficial, seed 42), `construction-ppe.ndjson`.

**Datos nuevos (nómina):** Datos sintéticos generados con script propio, seed 42, pseudónimos (`codigo_badge`, `pseudonimo`), nunca nombres reales ni salarios reales. Anomalías inyectadas: marcajes duplicados, entrada sin salida, cambios de turno, falta de EPP, sensor sin dato (frame None/1 canal), intento de acceso de persona no registrada.

**Regla crítica del curso:** no datos personales identificables salvo anonimización justificada.

#### Fase 3 — Data Preparation

Esquema propuesto (Postgres/SQLite, RLS multi-tenant):

```sql
empresa(id, nombre)
puesto(id, empresa_id, nombre, epp_requerido[])        -- ej. {"casco","guantes"}
empleado(id, empresa_id, codigo_badge, pseudonimo, puesto_id, turno_id, salario_base_por_hora)
turno(id, empresa_id, inicio, fin, descanso_min, tolerancia_puntualidad_min)
asistencia(id, empresa_id, empleado_id, fecha, entrada_ts, salida_ts,
           frames_evidencia, confianza_epp, estado)    -- estado: presente/ausente/tardanza/bloqueado
incidente(id, asistencia_id, tipo, severidad, ts, canal)  -- tipo: falta_epp, no_registrado, salida_temprana
periodo_nomina(id, empresa_id, desde, hasta, estado)
liquidacion(id, periodo_id, empleado_id, horas_norm, horas_extra, descuentos, total)
regla(id, key, valor, version, activa)                 -- reglas configurables en runtime
```

**Partición:** split por `empleado_id`, no por fila, para evitar data leakage.

#### Fase 4 — Modeling

**Agente 1 (Nómina):** LLM con herramientas. El LLM decide qué consultar y cómo redactar, pero el cálculo numérico (horas, extras, descuentos) queda en reglas deterministas.

**Agente 2 (EPP):** YOLOv8s `tuned_v2_s`, clases `no_helmet`, `no_goggle`, `no_gloves`, `no_boots`. Reglas de coherencia existentes.

**Vinculación empleado–cámara:** código QR o badge impreso, o selección manual en el panel. **No reconocimiento facial** (ver sección 5).

#### Fase 5 — Evaluation

Suite de pruebas con:
- ≥10 casos por medida (normales, límite, falla esperada).
- 5 repeticiones si hay aleatoriedad; media y desviación estándar.
- Tabla de sensibilidad para modificación en vivo.

**Análisis de errores:** ≥10 casos clasificados por tipo (falso positivo EPP, falsa tardanza, error de herramienta, frame inválido, persona no registrada, ventana WhatsApp cerrada) con hipótesis de causa.

#### Fase 6 — Deployment

- Panel web extendido: video MJPEG + tablero de nómina live (quién entró, quién salió, quién falta, resumen de horas).
- Generación de reporte PDF por intervalo de tiempo.
- API para herramientas del agente.
- WhatsApp reutilizando `ActuadorWhatsApp` existente (cooldown 60 s, límite 20 msg/hora, botón Pausar/Enviar ahora).
- README con ejecución en <5 comandos, `requirements.txt` con versiones fijadas.

#### Fase (Q) — Quality / Feedback loop

- Logs de ejecución: percepciones, decisiones y acciones con timestamp.
- Monitoreo de falsas alarmas y recall por clase `no_*`.
- Plan de re-entrenamiento si métricas caen bajo umbral.
- Bitácora obligatoria en `Documentation/BITACORA.md`.

---

## 4. Reportes agregados: PDF + WhatsApp

Tu requerimiento: si llegan múltiples personas en un intervalo de tiempo, generar un reporte general (PDF) aparte y notificar por WhatsApp sobre entradas o si hay alguien raro.

### 4.1 Reporte PDF general

**Contenido del PDF por intervalo (ej. turno de la mañana, turno de la tarde, día completo):**
- Número total de entradas registradas
- Lista de empleados entrados (pseudónimo, puesto, hora entrada, hora salida, horas trabajadas)
- Ausentes esperados (empleados con turno programado que no marcaron entrada)
- Incidentes de EPP (quién faltó qué elemento, severidad)
- Intentos de acceso de personas no registradas (alguien raro)
- Resumen de horas extra y descuentos

**Generación:** librería Python (reportlab o fpdf2), ejecutada al cierre del intervalo o por solicitud manual desde el panel.

### 4.2 Notificación WhatsApp

**Mensaje resumen por intervalo:**
- "Buenos días, reporte de entradas del turno X: N empleados registrados, M ausentes, K incidentes de EPP, L intentos no autorizados."
- Si hay "alguien raro" (persona no registrada intentando entrar): alerta inmediata con foto del frame y timestamp.

**Canal:** reusa `ActuadorWhatsApp` existente con cooldown y límites. Para el reporte general, usar `forzar=True` si es un envío deliberado del reporte de cierre.

---

## 5. Reconocimiento facial: no hay dataset, ¿cómo iniciar?

**No uses reconocimiento facial.** Razones:

1. **El curso prohíbe datos personales identificables** salvo anonimización justificada (`Documentation/Markdown pegado.md`, línea 26).
2. **No tienes dataset de rostros** ni tiempo para etiquetar uno.
3. **Riesgos de privacidad, sesgo y uso indebido** (vigilancia) complican el análisis de IA responsable.

**Alternativa: Badge o código QR impreso por empleado.**
- La cámara (o panel) lee el código y asocia al `empleado_id`.
- Fallback: selección manual en el panel desde lista de pseudónimos.
- Nunca nombres reales ni salarios reales.

Si el profesor insiste en facial: usar un **simulador de identidad** (el agente asume identidad por badge y devuelve confianza 1.0/0.0 según caso de prueba), declarado en el informe.

---

## 6. Supuestos a evaluar y validar

| ID | Supuesto | Tipo | Cómo validar | Criterio de aceptación | Mitigación si falla |
|---|---|---|---|---|---|
| S1 | El trabajador se identifica con badge/QR antes de cualquier otra acción | Negocio | Probar flujo de entrada con badge válido e inválido | 100% de identificaciones correctas en casos de prueba | Seleccionar manualmente desde panel como fallback |
| S2 | Solo trabajadores registrados en nómina pueden marcar entrada | Negocio | Intentar registro con código de empleado inexistente | Rechazo + registro de intento no autorizado + alerta WhatsApp | Bloqueo total de acceso físico (puerta/tornillo) |
| S3 | La detección YOLO certifica presencia de EPP durante la entrada | Técnico | Probar `tuned_v2_s` en `dataset_v2/test` | recall `no_*` ≥ 0.70 | Ajustar umbral por clase o aumentar K de confirmación |
| S4 | Un empleado = un badge/código único | Técnico | Verificar unicidad de `codigo_badge` en BD | 100% únicos | Validación de duplicados en alta |
| S5 | Los turnos son fijos y predecibles por puesto | Negocio | Revisar catálogo de turnos | Desviación estándar de inicio < 15 min | Ventana de tolerancia configurable |
| S6 | Los datos sintéticos representan comportamiento real | Datos | Comparar distribuciones sintéticas vs. estadísticas sectoriales | Coeficiente de variación similar (±20%) | Etiquetar como simulado; validar con datos reales en piloto |
| S7 | El LLM no alucina cálculos de nómina | Modelo | Pruebas unitarias de herramientas con valores conocidos | Error absoluto = 0 en cálculos deterministas | Todo cálculo en reglas deterministas; LLM solo redacta |
| S8 | La ventana de 24 h de WhatsApp no bloquea alertas críticas | Operativo | Probar `prueba_whatsapp.py --rutas  imágenes` | Envío exitoso (200 + wamid) | Plantilla `alerta_epp` o notificación por panel |
| S9 | El cooldown de 60 s no pierde alertas críticas de nómina | Negocio | Simular alertas consecutivas | 0 alertas críticas perdidas | `forzar=True` para envíos deliberados (reporte de cierre) |
| S10 | Frames fallidos (None / 1 canal) no rompen el pipeline | Técnico | Inyectar frames inválidos en `procesar_frame` | Se registran en `frames_fallidos`, pipeline continúa | Validación de entrada existente; omisión segura |
| S11 | El reporte PDF se genera correctamente por intervalo | Operativo | Generar PDF con datos de prueba | PDF válido, contiene todos los campos esperados | Fallback a reporte por consola/CSV |

---

## 7. Riesgos de IA responsable y mitigaciones

| Riesgo | Descripción | Mitigación |
|---|---|---|
| Penalización injusta | Falta de EPP detectada como falta grave y afecta salario | EPP genera incidente/observación, no bloqueo automático de entrada; revisión humana antes de descontar |
| Sesgo por iluminación/vestimenta | YOLO falla más en poca luz o con EPP de colores distintos | Métricas por subgrupo (condición de iluminación); umbrales adaptativos |
| Exfiltración de datos laborales | Salarios o horarios expuestos en logs/WhatsApp | Pseudónimos, no nombres reales; logs sin salarios; RLS en BD |
| Uso indebido (vigilancia) | Sistema usado para control excesivo más que verificación EPP | Alcance limitado a entrada/salida y EPP; no seguimiento continuo dentro de la obra |
| Alucinación del LLM | Cálculo incorrecto de horas o liquidación | Cálculo en reglas deterministas; LLM solo consulta y redacta |
| "Alguien raro" no detectado | Persona no registrada pasa desapercibida | Validación obligatoria de badge antes de cualquier registro; alerta WhatsApp inmediata si falla |

---

## 8. Artefactos y entregables por fase (CRISP-ML(Q))

| Fase | Artefacto | Ubicación sugerida |
|---|---|---|
| 1. Business Understanding | PEAS actualizado, matriz de decisión, métricas pre-registradas | `Documentation/MATRIZ_DECISION.md`, `Documentation/PEAS_NOMINA.md` |
| 2. Data Understanding | Diccionario de datos, informe EDA de nómina | `Documentation/DICCIONARIO_DATOS_NOMINA.md`, `eda/salidas/eda_nomina.md` |
| 3. Data Preparation | Esquema BD, script generación sintética (seed 42), partición | `src/safesite/modelo_datos.sql`, `src/safesite/generar_sintetico.py` |
| 4. Modeling | Agente LLM con herramientas, línea base, reglas deterministas | `src/safesite/agente_nomina.py`, `src/safesite/herramientas_nomina.py`, `config/reglas_nomina.yaml` |
| 5. Evaluation | Tabla de resultados, análisis de errores, tabla de sensibilidad | `runs/agente/pruebas_nomina/`, `Documentation/ANALISIS_ERRORES_NOMINA.md` |
| 6. Deployment | Panel de nómina, generación PDF, API, README, despliegue | `deploy/`, `README.md`, `requirements.txt` |
| (Q) Quality | Bitácora, plan de re-entrenamiento, monitoreo | `Documentation/BITACORA.md`, `Documentation/BITACORA_USO_IA.md` |

---

## 9. Próximos pasos inmediatos

1. **Crear `Documentation/DICCIONARIO_DATOS_NOMINA.md`** — variables, unidades, rangos, códigos de faltante.
2. **Diseñar esquema BD** (`src/safesite/modelo_datos.sql`) con RLS multi-tenant.
3. **Crear generador de datos sintéticos** (seed 42, pseudónimos, anomalías inyectadas).
4. **Ejecutar EDA inicial** sobre datos sintéticos con `@exploratory-data-analysis`.
5. **Definir PEAS y matriz de decisión** para el agente de nómina (ruta E del curso).
6. **Implementar Agente 1 (Nómina/Identificación)** — primero en el flujo.
7. **Implementar Agente 2 (EPP)** — segundo, valida cumplimiento sin bloquear entrada.
8. **Implementar generación de reporte PDF** y notificación WhatsApp de cierre de intervalo.
9. **Ejecutar pruebas** y registrar en `Documentation/BITACORA.md`.

---

## 10. Bitácora de cambios (CRISP-ML(Q))

| Fecha | Fase CRISP-ML | Qué se decidió | Por qué | Evidencia |
|---|---|---|---|---|
| 02-nov-2026 | 1. Business Understanding | 2 agentes secuenciales: Nómina primero, EPP segundo | Flujo lógico de control de acceso: identificar antes de verificar cumplimiento | Este documento |
| 02-nov-2026 | 2. Data Understanding | No reconocimiento facial; usar badge/QR | Sin dataset facial; restricción de datos personales del curso | Este documento |
| 02-nov-2026 | 6. Deployment | Reporte PDF agregado + WhatsApp por intervalo | Requerimiento del usuario: visibilidad general de entradas y "alguien raro" | Este documento |

---

> **Nota:** Este documento es el punto de partida para aplicar CRISP-ML(Q) a la ampliación de SAFESITE. Se debe mantener actualizado a medida que avance el desarrollo y registrar cada decisión relevante en `Documentation/BITACORA.md`.
