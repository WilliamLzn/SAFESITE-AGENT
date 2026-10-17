# Guion del video de evidencia (≤ 20 min) — SafeSite-Agent

**Requisitos del enunciado:** cámara y voz de ambos integrantes; el agente ejecutándose **desde cero** (no solo resultados guardados); al menos un escenario típico y uno de falla esperada; la ejecución de las pruebas y la obtención de los valores de la tabla; índice con minutos al inicio. *Un video que supere 20 minutos solo se evalúa hasta el minuto 20.*

## Índice sugerido (18:30)

| Minuto | Sección | Qué mostrar / decir | Quién |
|---|---|---|---|
| 00:00 | Introducción (1:00) | Pareja, curso, agente elegido y por qué (1 frase: matriz de decisión 4.85 vs 2.90, ver `MATRIZ_DECISION.md`) | Ambos |
| 01:00 | Arquitectura (2:30) | Diagrama del ciclo percepción→decisión→acción; dónde está cada paso en el código (`agente.py::procesar_frame`: detectar → evaluar rachas K=3 → actuadores); los 7 componentes IBM mapeados a módulos | Integrante 1 |
| 03:30 | Arranque desde cero (2:00) | Clonar/abrir el repo en limpio, crear venv, `pip install -r requirements.txt`, configurar `.env` (copiar de `.env.example`), abrir el panel. Dejar claro que no hay resultados pre-cargados | Integrante 2 |
| 05:30 | Demo en vivo — escenario típico (4:00) | Levantar `panel.py` (webcam) y `piloto.py` (webhook): un integrante **sin casco** frente a la cámara → mostrar el video anotado en vivo (cajas con etiquetas en español, gafas a nivel de ojos), la confirmación K=3 en el log, la **alerta real de WhatsApp con foto** en el teléfono (~2.6 s), el cooldown impidiendo duplicados, y la respuesta a **INFO** desde el chat | Integrante 1 en cámara, Integrante 2 mostrando el teléfono |
| 09:30 | Demo — caso de falla esperada (2:30) | 1) Tapar/ desconectar la webcam → el agente registra "percepción sin dato" y NO se detiene; 2) desconectar internet o usar credenciales inválidas → la alerta degrada a texto puro / queda en el historial ("la alerta nunca se pierde") | Integrante 2 |
| 12:00 | Pruebas de la Fase 3 (4:00) | Ejecutar `.venv\Scripts\python.exe -m src.safesite.pruebas_medidas --device 0` en pantalla; explicar las 4 medidas con su fórmula y **umbral pre-registrado**; señalar el log JSONL escribiéndose; al terminar, mostrar la tabla de resultados generada (M1 96.3%/96.2%, M2 3.5%/2.6%, M3 ~3 s, M4 cumple) y los archivos de evidencia en `runs/agente/pruebas/` | Integrante 1 |
| 16:00 | Análisis de resultados (2:00) | Qué se cumplió, qué no (S5: persona lejana sin alerta — caso límite honesto), causa probable (objetos pequeños: área mediana 1.85 % de la imagen) y qué cambiaríamos (imgsz>640, entrenamiento con recortes, calibrar umbral) | Integrante 2 |
| 18:00 | Cierre (0:30) | Limitaciones (dataset sesgado en gafas/botas, simulación vs. obra real) y trabajo futuro; enlace del repo en pantalla | Ambos |

## Checklist técnica antes de grabar

- [ ] Cerrar sesiones/ventanas que puedan mostrar credenciales (tokens del `.env` NUNCA en pantalla).
- [ ] `git status` limpio y repo subido a GitHub (P13) para poder mostrar el enlace real.
- [ ] Probar la webcam y el micrófono; grabar a 1080p para que el texto del panel sea legible.
- [ ] Tener ya cargadas en otra pestaña: la tabla `runs/agente/pruebas/tabla_resultados_*.md` y `Documentation/BITACORA.md`.
- [ ] Celular con WhatsApp en modo cámara para capturar la alerta entrando en vivo.
- [ ] Casco/obra: preparar un casco real para el contraste "con casco = sin alerta, sin casco = alerta".
