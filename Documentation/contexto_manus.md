# Contexto del proyecto SAFESITE — Nómina LIVE

**Para:** Cristian Mateo Benítez (Integrante 2)  
**De:** William David Lozano Julio (Integrante 1)  
**Fecha:** 03-nov-2026  
**Profesor:** Edwin Puerta  
**Curso:** IA — Proyecto final  

---

## 1. ¿Para qué sirve este documento?

Es una guía rápida para que entiendas el proyecto sin tener que leer todo el repositorio ni preguntar por cada detalle. Cubre lo que ya tenemos, lo que estamos construyendo, qué está listo, qué falta y hacia dónde vamos. Está escrito en lenguaje sencillo, sin tecnicismos innecesarios.

---

## 2. Lo que ya tenemos (SAFESITE actual)

SAFESITE es un sistema que detecta si los trabajadores llevan el Equipo de Protección Personal (EPP): casco, guantes, botas y gafas. Ya está construido y funcionando.

| Componente | Qué hace | Estado |
|---|---|---|
| **YOLOv8s** | Detecta falta de EPP en imágenes de cámara | Entrenado y listo (`tuned_v2_s`) |
| **Confirmación K=3** | Espera 3 frames antes de alertar para evitar falsos positivos | Implementado |
| **Alertas WhatsApp** | Envía mensajes cuando hay incumplimiento de EPP | Funcionando (Cloud API de Meta) |
| **Panel web (Flask)** | Muestra video en tiempo real y tarjetas de EPP por clase | http://localhost:5000 |
| **Demo en la nube** | Google Cloud Run, disponible 24/7 | https://safesite-ui-428834791978.us-central1.run.app |
| **Pruebas de EPP** | Métricas M1–M4 ya validadas | Listas |

**Regla importante:** La carpeta `safesite_dataset/` y el archivo `.ndjson` son **solo lectura**. No se modifican, mueven ni borran sin confirmación explícita.

---

## 3. Lo que estamos construyendo (Nómina LIVE)

La idea es convertir SAFESITE en un **gestor y verificador de nómina en tiempo real para empresas de construcción**. No solo detecta si falta un casco, ahora también:

- Identifica al trabajador (mediante código badge/QR o selección manual).
- Registra su entrada y salida.
- Verifica si llegó tarde o a tiempo.
- Calcula horas trabajadas.
- Genera reportes (PDF y WhatsApp) al cierre de cada turno o jornada.
- Alerta si alguien intenta entrar sin estar registrado en la nómina ("alguien raro").

### ¿Por qué 2 agentes y no 1?

Porque manejan cosas distintas:

| Agente | Qué hace | Modelo |
|---|---|---|
| **Agente 1 (primero)** | Identifica al trabajador, valida su badge, registra entrada/salida, calcula horas | LLM con herramientas + reglas deterministas |
| **Agente 2 (segundo)** | Revisa con la cámara si el trabajador lleva el EPP completo | YOLOv8s (ya entrenado) |

**Orden:** Primero Agente 1 (¿quién es? ¿puede entrar?), luego Agente 2 (¿lleva el EPP puesto?). El EPP ya no bloquea la entrada; si falta algo, se registra como incidente pero se deja pasar.

### ¿Por qué NO reconocimiento facial?

- El curso prohíbe datos personales identificables (nombres reales, caras, cédulas).
- No tenemos dataset de rostros.
- En una obra con casco, gafas y sol, el reconocimiento facial falla mucho más que un código QR.
- El curso pide una técnica de IA como núcleo (ruta E: agente con herramientas); ya la tenemos con el LLM + YOLO.

---

## 4. Estado actual (qué está listo y qué falta)

### ✅ Listo
- Documento de integración bajo CRISP-ML(Q) (`CRISPML_INTEGRACION_NOMINA.md`).
- Diccionario de datos de la base de datos (`DICCIONARIO_DATOS_NOMINA.md`).
- Esquema SQL de la base de datos (`src/safesite/modelo_datos.sql`).
- Diagramas de base de datos y flujo de agentes (`DIAGRAMAS_BD_NOMINA.md`).
- `main.tex` en `Documentation/` (Hito 1: matriz de decisión y selección del agente).
- Primera entrada de bitácora de uso de IA (`BITACORA_USO_IA_NOMINA.md`).
- main.tex original en la raíz (versión informe completo, se puede ignorar para el Hito 1).

### 🚧 En progreso (próximos pasos inmediatos)
1. Generador de datos sintéticos de nómina (seed 42, sin datos reales).
2. EDA inicial sobre esos datos sintéticos.
3. Implementar Agente 1 (Nómina/Identificación).
4. Implementar Agente 2 (EPP) conectado al Agente 1.
5. Generación de reporte PDF + WhatsApp de cierre de jornada.

### 📋 Pendiente (más adelante)
- Pruebas formales contra métricas M1–M7.
- Análisis de al menos 10 errores clasificados.
- Despliegue del panel de nómina en la nube.
- Informe IEEE final (6–8 páginas).
- Video de sustentación (máximo 20 minutos).

---

## 5. Base de datos (9 tablas, sin nombres reales)

Todas las tablas pertenecen a una empresa (`empresa_id`) para que varias empresas puedan usar el sistema sin mezclarse sus datos.

| Tabla | Qué guarda |
|---|---|
| `empresa` | Datos de la empresa (nombre, NIT) |
| `puesto` | Puestos de trabajo y qué EPP requiere cada uno |
| `turno` | Horarios de entrada/salida y tolerancia de puntualidad |
| `empleado` | Pseudónimo, código badge, puesto, turno, salario base (datos de prueba) |
| `asistencia` | Entrada, salida, frames de evidencia, estado (presente/tardanza/ausente) |
| `incidente` | Falta de EPP, persona no registrada, salida temprana, etc. |
| `periodo_nomina` | Períodos de pago (abierto, cerrado, liquidado) |
| `liquidacion` | Horas normales, horas extra, descuentos, total |
| `regla` | Reglas configurables por empresa (cooldown, umbrales, etc.) |

**Nunca se guardan nombres reales, caras ni cédulas de empleados.** Se usa `pseudonimo` y `codigo_badge`.

---

## 6. Reglas de oro del proyecto

1. **Datos crudos solo lectura:** `safesite_dataset/` y `.ndjson` no se tocan.
2. **Semilla fija 42** en todo lo que se genere o entrene.
3. **Bitácora obligatoria:** cada ejecución relevante se registra en `Documentation/BITACORA.md`.
4. **Commits distribuidos:** no dejar todo para un solo commit la víspera de la entrega.
5. **Métricas pre-registradas:** los umbrales de éxito se definen **antes** de experimentar.

---

## 7. Archivos clave y dónde están

| Archivo | Ruta | Para qué sirve |
|---|---|---|
| Plan de integración | `Documentation/CRISPML_INTEGRACION_NOMINA.md` | Hoja de ruta completa bajo CRISP-ML(Q) |
| Diccionario de datos | `Documentation/DICCIONARIO_DATOS_NOMINA.md` | Explicación de cada tabla y columna |
| Diagramas | `Documentation/DIAGRAMAS_BD_NOMINA.md` | ER diagram, flujo de agentes, secuencias |
| Esquema SQL | `src/safesite/modelo_datos.sql` | Código para crear la base de datos |
| Hito 1 (LaTeX) | `Documentation/main.tex` | Matriz de decisión y selección del agente |
| Bitácora IA | `Documentation/BITACORA_USO_IA_NOMINa.md` | Registro de uso de IA (Integrante 1 y 2) |
| Roadmap | `Documentation/ROADMAP_AGENTE.md` | Plan original de fases 0–5 |
| Enunciado | `Documentation/ENUNCIADO.md` | Requisitos del curso |

---

## 8. Cómo puedes ayudar sin gastar muchos créditos de IA

- **Revisa los documentos creados** y dime si algo no tiene sentido o falta algo.
- **Valida la matriz de decisión** del `main.tex`: ¿están bien los pesos y puntajes?
- **Prueba el esquema SQL** en una base de datos local si tienes PostgreSQL instalado.
- **Piensa en casos de prueba:** ¿qué pasaría si alguien entra con el badge de otro? (ya lo planteamos como supuesto S12).
- **No necesitas generar todo el código desde cero:** yo me encargo de la implementación; tú enfócate en revisar, probar y documentar lo que se hace.

---

## 9. Próxima reunión sugerida

Cuando termines de leer este documento, podemos definir quién implementa el Agente 1 y quién el Agente 2, y empezar a escribir el generador de datos sintéticos.

---

> **Nota:** Si algo no queda claro, házmelo saber y lo aclaro. Este documento es vivo y se actualiza a medida que avanzamos.
