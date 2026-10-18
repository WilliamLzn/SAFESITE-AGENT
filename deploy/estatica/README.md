---
title: SafeSite Agent — Demo en vivo
emoji: 🦺
colorFrom: blue
colorTo: yellow
sdk: static
pinned: true
---

# SafeSite Agent — demo en vivo

Agente de monitoreo de EPP en obra: detecta con YOLOv8s, confirma una
falta solo cuando la ve en 3 frames seguidos y arma el aviso al
supervisor por WhatsApp (aquí el aviso solo se muestra, no se envía).

En este Space la demo es **estática**: el modelo (exportado a ONNX) se
descarga una vez y corre **en tu navegador** con ONNX Runtime Web —
ninguna imagen sale de tu equipo. El proyecto original corre en Python
en servidor (Gradio + PyTorch, `deploy/app.py` en el repositorio); esta
versión existe porque los Static Spaces son los únicos que Hugging Face
mantiene gratis. La equivalencia del modelo exportado está verificada
(mismas detecciones en el set de test).

- Demo: subir imagen, webcam en vivo (K=3 y cooldown reales), fotos del
  set de test con su etiqueta oficial y fallas del sensor.
- Resultados oficiales de la suite (M1–M4) y EDA del dataset.
- Nota del deploy con la comparación de tecnologías.

Código, entrenamiento y bitácora del proyecto:
[github.com/WilliamLzn/SAFESITE-AGENT](https://github.com/WilliamLzn/SAFESITE-AGENT)
