---
title: SafeSite Agent — Monitoreo de EPP en obra
emoji: 🦺
colorFrom: blue
colorTo: orange
sdk: gradio
sdk_version: 6.30.0
app_file: app.py
pinned: true
---

# SafeSite Agent

Agente que revisa fotos de obra buscando trabajadores sin su equipo de
protección. Detecta con YOLO, confirma una falta solo cuando la ve en 3
frames seguidos y arma el aviso al supervisor por WhatsApp (en esta página
el aviso solo se muestra, no se envía).

Todo lo que ves corre en vivo en el servidor, nada está pregrabado:

- **Demo en vivo** — webcam, subir una imagen o traer una foto del set de
  test (con su etiqueta, para saber si el agente acierta). Incluye la
  simulación de fallas del sensor.
- **Pruebas (M1–M4)** — los 13 escenarios de la suite y los M1/M2 sobre
  todas las escenas, con logs descargables.
- **Resultados oficiales** — la corrida oficial con su tabla y archivos.
- **EDA y métricas** — supuestos verificados de los datos, métricas del
  detector (P/R/F1 por clase) y del agente (accuracy y F1 por escena).
- **Cómo probar** — instrucciones paso a paso.

Código, entrenamiento y bitácora del proyecto:
[github.com/WilliamLzn/SAFESITE-AGENT](https://github.com/WilliamLzn/SAFESITE-AGENT)
