# Análisis de resultados — Fase 3 (máximo una página)

*Ejecución de referencia: `runs/agente/pruebas/` — corrida 20261014_170459 (GPU RTX 4050, 5 repeticiones por escenario, seed 42, K=3 frames, cooldown 30 s). Tabla completa: `tabla_resultados_20261014_170459.md`.*

## Qué medidas se cumplieron

**Las cuatro medidas de desempeño probadas cumplen su umbral pre-registrado.**

1. **M1 — Recall de incidente (≥ 0.70):** 0.964 ± 0.000 en validación (28 escenas) y 0.962 ± 0.000 en test (26 escenas), × 5 repeticiones. El agente alerta 24 de cada 25 escenas con incumplimiento real; la desviación estándar exactamente 0 en las cinco repeticiones confirma que el pipeline es determinista dada una semilla y un checkpoint fijos.
2. **M2 — Falsas alarmas (≤ 0.10):** 3.5 % (val, 115 escenas control) y 2.6 % (test, 114 escenas). Un supervisor recibiría menos de una alerta espuria cada 28 escenas de cumplimiento.
3. **M3 — Tiempo de notificación (< 10 s):** 2.99 s end-to-end estimados (1.0 s de confirmación temporal K=3 a 2 FPS + ~0.1 s de inferencia de los 3 frames + 1.9 s de envío HTTP medido en E24). En la sesión real con webcam y WhatsApp (E28) se midieron ~2.6 s por alerta con foto. Margen de 3.3× frente al umbral.
4. **M4 — Cooldown anti-spam (0 duplicadas):** la reincidencia dentro de la ventana de 30 s produce exactamente 1 alerta (S6: 1 ± 0) y la reincidencia posterior a la ventana produce las 2 esperadas (S7: 2 ± 0). La memoria de corto plazo funciona como se diseñó.

**Casos de falla esperada (requisito del enunciado):** los cuatro escenarios de falla se comportaron según el diseño, sin excepciones: frames inválidos (None y 1 canal) quedan registrados como fallo de percepción y el agente continúa; el frame negro no produce alertas ni error; con la API de WhatsApp caída la alerta **no se pierde** (queda persistida en el historial) y la degradación imagen→texto no propaga excepciones; el checkpoint inexistente produce un fallo de arranque controlado.

## Qué no se cumplió y causa probable

**S5 — Persona lejana (caso límite): 0 alertas en 5/5 repeticiones.** La escena de test con la persona de menor caja no disparó alerta. Causa probable: resolución del objeto — el EDA midió área mediana de 1.85 % de la imagen y la inferencia corre a 640 px; una persona que ocupa pocos píxeles genera confianzas bajo el umbral 0.15 de las clases `no_*` y la racha nunca alcanza K=3. Es consistente con la frontera conocida del sistema (no es una falla del razonamiento: la percepción no percibe).

**Qué cambiaríamos para corregirla:** (1) inferencia con `imgsz ≥ 960` para escenas de cámara fija con zonas profundas (costo: ~2× latencia, aún lejos del umbral de 10 s); (2) recortes de la escena con re-escala antes de inferir (dos pasadas por frame); (3) reentrenar con mosaico de recortes de personas pequeñas. Ninguna se aplicó antes de la entrega deliberadamente: cambiar el modelo o la resolución invalidaría las métricas ya validadas y el tiempo de cómputo restante no daba para re-validar.

## Lectura de conjunto

El agente cumple su objetivo de negocio (alertar incumplimientos con evidencia y en tiempo útil) con holgura en todas las medidas, y sus dos debilidades conocidas son de percepción con causa identificada y documentada: objetos pequeños (S5) y las clases minoritarias del dataset (`no_boots`, `no_goggle`), ambas heredadas del desbalance del dataset fuente y abordadas parcialmente con la elección de YOLOv8s (E23). La suite queda instalada en el repo para re-ejecutar las pruebas tras cualquier cambio (`src/safesite/pruebas_medidas.py`).
