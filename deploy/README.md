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

## Demo en GitHub Codespaces (recomendado, gratis)

La página corre en una VM gratuita de GitHub, no en el PC y sin túneles:
el repo ya trae el `.devcontainer/devcontainer.json` con todo
preinstalado (torch-cpu, ultralytics, gradio).

1. En GitHub, sobre el repo: botón **Code → pestaña Codespaces →
   create codespace on main**. La primera vez tarda ~5–8 min
   (instala las librerías); los arranques siguientes, segundos.
2. En la terminal del codespace:
   ```bash
   python deploy/app.py
   ```
3. En el panel **Ports** de abajo, click derecho sobre el puerto 7860 →
   **Port Visibility → Public** (con esto cualquiera con la URL puede
   abrirla, sin cuenta de GitHub).
4. La URL pública es la del 7860: `https://…-7860.app.github.dev`.
   Es https, así que la webcam de la demo funciona desde cualquier
   navegador, incluido el celular.

El codespace se puede pausar (**Stop codespace**) y reanudar cuando se
necesite: la URL pública del puerto se conserva. La cuota gratuita es de
60 h-core al mes (con el GitHub Student Pack, verificable con el correo
institucional, sube a 90): de sobra para una demo. La app corre en CPU
(las VM gratuitas no tienen GPU).

## Emergencia: demo desde el PC

Si no queda otra, `deploy/demo_publica.py` sirve la página desde el
propio PC con un túnel cloudflared (E48). Depende del PC encendido y la
URL cambia en cada arranque; no es la vía recomendada.

Código, entrenamiento y bitácora del proyecto:
[github.com/WilliamLzn/SAFESITE-AGENT](https://github.com/WilliamLzn/SAFESITE-AGENT)
