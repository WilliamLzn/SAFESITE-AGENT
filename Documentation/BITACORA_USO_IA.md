# Bitácora de uso de IA — SAFESITE-AGENT

Registro de cómo se utilizó la IA generativa (OpenCode) durante el desarrollo. Todo el código fue supervisado y revisado por el equipo antes de incorporarse al repositorio.

## 1. Primera entrada — Etapa Nómina LIVE (03-nov-2026)

| Fecha | Integrante | Herramienta | Para qué se usó | Qué se aceptó, modificó o descartó | Cómo se verificó |
|---|---|---|---|---|---|
| 03-nov-2026 | Integrante 1 | OpenCode | Proponer la ampliación de SAFESITE a gestor y verificador de nómina LIVE | Se aceptó ampliar el proyecto manteniendo la detección de EPP existente como capa de cumplimiento | Se revisó el estado actual del roadmap y se confirmó continuidad con dataset_v2 y tuned_v2_s |
| 03-nov-2026 | Integrante 1 | OpenCode | Definir la arquitectura de agentes para nómina LIVE | Se aceptó usar 2 agentes secuenciales: Agente 1 (Nómina/Identificación) primero, Agente 2 (EPP) segundo | Se validó el flujo lógico: identificación → entrada → EPP → salida → reportes |
| 03-nov-2026 | Integrante 2 | OpenCode | Corregir el orden de los agentes | Se modificó el orden inicial (EPP primero) a Nómina primero, EPP segundo, según sugerencia del equipo | Se revisó el flujo de control de acceso y se confirmó que es más lógico identificar antes de validar EPP |
| 03-nov-2026 | Integrante 1 | OpenCode | Elegir el método de identificación de trabajadores | Se aceptó usar badge/QR o selección manual; se descartó reconocimiento facial | Se verificó contra la restricción del curso sobre datos personales y la falta de dataset facial |
| 03-nov-2026 | Integrante 1 | OpenCode | Definir los motivos de no usar reconocimiento facial | Se aceptaron los motivos: restricción de datos personales, no hay dataset facial, complejidad adicional, robustez en obra | Se revisó el enunciado del curso (línea 26 sobre datos personales) y la ruta E |
| 03-nov-2026 | Integrante 2 | OpenCode | Aplicar la metodología CRISP-ML(Q) | Se aceptó usar CRISP-ML(Q) en las 6 fases más bucle de calidad, tal como exige el profesor | Se verificó que sea la metodología obligatoria indicada por el docente |
| 03-nov-2026 | Integrante 1 | OpenCode | Definir supuestos de seguridad para el uso de badge | Se aceptó incluir el supuesto S12 (suplantación de badge por persona no autorizada) con sus mitigaciones | Se analizó el flujo de entrada y se registró la evidencia fotográfica en asistencia.frames_evidencia |

## 2. Decisiones del Hito 2 (15-nov-2026)

| Decisión | Papel de la IA | Papel del equipo |
|---|---|---|
| Estados de cámara (Reconociendo → Reconocido → Escaneando EPP) + overlay dentro del video | Propuso y escribió el código de la máquina de estados | Validamos que aparezca correctamente dentro del cuadro de la cámara y no encima de otros elementos |
| Emojis por puesto en badges de trabajador | Propuso el mapeo puesto→emoji (supervisor 🦺, albañil 🧱, electricista ⚡, ayudante 🛠️, operario_grua 🏗️, soldador 🔥) y lo implementó | Validamos que se vean correctamente en las cards |
| Horas semanales + alerta de salida mal trazada | Propuso la lógica de acumulación semanal y el umbral de tolerancia de 30 min | Definimos los umbrales exactos y el comportamiento de la alerta |
| Fix deadlock en marcar_entrada/marcar_salida (lock reentrante) | Identificó la causa raíz (Lock de Python no es reentrante) y propuso la solución (acceso directo al estado sin llamar a esta_dentro()) | Validamos que el hilo ya no se muere |
| Fix endpoint /badge/estado para siempre devolver JSON válido | Propuso el try/except que devuelve [] ante cualquier error | Verificamos que el navegador ya no lanza Uncaught SyntaxError |
| Reducción de logs del bucle de captura | Propuso eliminar logs repetitivos por frame y dejar solo cambios de estado | Validamos que la consola sea legible |
