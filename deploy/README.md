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
  test (con su etiqueta, para saber si el agente acierta).
- **Fallas del sensor** — los tres casos de falla (sin dato, formato
  inválido, frame negro) con la reacción del agente frame por frame.
- **Pruebas (M1–M4)** — qué mide cada medida pre-registrada, los 13
  escenarios de la suite y los M1/M2 sobre todas las escenas, con logs
  descargables.
- **Resultados oficiales** — la corrida oficial con su tabla, explicada, y
  los archivos de evidencia.
- **EDA y métricas** — supuestos verificados de los datos (con las 6
  figuras del EDA), límites de la validación, métricas del detector (P/R/F1
  por clase) y del agente (accuracy y F1 por escena).
- **Cómo probar** — instrucciones paso a paso.

## Color de la página

El tema se elige al arrancar, con la opción `--tema` o la variable
`SAFESITE_TEMA`. Los disponibles: `esmeralda` (por defecto), `grafito`,
`rosa`, `ambar`, `azul`, `ocean` y `neon`.

Local:
```powershell
.venv\Scripts\python.exe deploy\app.py --tema grafito
.venv\Scripts\python.exe deploy\app.py --tema rosa
```

En el Space: Settings → Variables and secrets → nueva variable
`SAFESITE_TEMA` con valor `grafito` (o `rosa`), y el Space se reinicia
solo.

## Demo permanente en Claw Cloud (recomendado, gratis y 24/7)

La página vive en un contenedor en la nube: no depende del PC ni de
encender nada. Claw Cloud regala $5/mes de crédito con una cuenta de
GitHub de más de 180 días, y un contenedor de esta app (2 GB de RAM)
cabe en ese crédito. La imagen ya está lista (`deploy/Dockerfile`,
validada localmente: construye y sirve la página).

1. Cuenta en **claw.cloud** entrando con tu GitHub (los $5 llegan si la
   cuenta de GitHub tiene más de 180 días).
2. En el panel de Claw Cloud Run: **Settings → Access Key → crear**
   (sirve para subir la imagen; puedes borrarla al terminar).
3. Desde la raíz del repo, construir y subir la imagen:
   ```powershell
   docker build -f deploy/Dockerfile -t safesite-demo .
   docker login hub.claw.cloud        # usuario de Claw + la access key
   docker tag safesite-demo:latest hub.claw.cloud/<TU_USUARIO>/safesite-demo:latest
   docker push hub.claw.cloud/<TU_USUARIO>/safesite-demo:latest
   ```
   El primer push sube ~2.8 GB (puede tardar; las siguientes veces solo
   sube lo que cambió).
4. En Claw Cloud Run: **App List → Create App**, imagen
   `hub.claw.cloud/<TU_USUARIO>/safesite-demo:latest`, recursos
   **1–2 vCPU y 2 GB de RAM** (la app consume ~0.8 GB), puerto **8788**
   (ya viene configurado en la imagen).
5. Deploy → URL **https** pública y permanente, con la webcam funcional.
   Cada vez que cambies la página: reconstruir, `push` y redeploy.

Por qué no Render: el free tier da 512 MB de RAM y la app consume
835–858 MB medidas en CPU (moriría con out-of-memory), y además duerme
tras 15 min sin visitas.

## Demo en GitHub Codespaces (gratis, para presentaciones puntuales)

Para un día concreto: **Code → Codespaces → create codespace on main**
(~5–8 min la primera vez), `python deploy/app.py`, click derecho en el
puerto 7860 del panel **Ports → Port Visibility → Public**, y abrir la
URL `https://…-7860.app.github.dev`. El codespace se pausa y reanuda
conservando la URL. No sirve para "siempre listo": hay que encenderlo.

## Emergencia: demo desde el PC

Si no queda otra, `deploy/demo_publica.py` sirve la página desde el
propio PC con un túnel cloudflared (E48). Depende del PC encendido y la
URL cambia en cada arranque; no es la vía recomendada.

Código, entrenamiento y bitácora del proyecto:
[github.com/WilliamLzn/SAFESITE-AGENT](https://github.com/WilliamLzn/SAFESITE-AGENT)
