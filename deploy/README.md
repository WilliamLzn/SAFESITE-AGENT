---
title: SafeSite Agent — Demo en vivo
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

## Demo pública permanente: la estática (recomendado)

`deploy/estatica/` — el mismo modelo exportado a **ONNX** corre **en el
navegador del visitante** (ONNX Runtime Web), servido por **GitHub Pages**
en la rama `gh-pages` del propio repo: gratis para siempre, sin tarjeta,
sin dormirse. Equivalencia del export verificada contra el original
(mismas detecciones, Δconf ≤ 0.018). Publicación:

```powershell
.venv\Scripts\python.exe deploy\estatica\generar.py            # assets (una vez)
.venv\Scripts\python.exe deploy\estatica\publicar_pages.py     # rama gh-pages
```

Activar Pages una sola vez: **GitHub → SAFESITE-AGENT → Settings → Pages
→ Branch: gh-pages, / (root) → Save**. URL:
`https://williamlzn.github.io/SAFESITE-AGENT/`

Prueba local antes de publicar:

```powershell
.venv\Scripts\python.exe -m http.server 8080 --directory deploy\estatica
# abrir http://localhost:8080
```

## Versión con servidor: app.py (Gradio)

`deploy/app.py` es la versión completa (suite M1–M4 corriendo en vivo,
webcam, fallas del sensor). Necesita un servidor Python con ~700 MB de
RAM (pico medido 677 MB). Úsala en local (GPU disponible), en Codespaces
para una presentación puntual o en cualquier VPS propio:

```powershell
.venv\Scripts\python.exe deploy\app.py --tema grafito
```

El color se elige con `--tema` o la variable `SAFESITE_TEMA`:
`esmeralda` (default), `grafito`, `rosa`, `ambar`, `azul`, `ocean`, `neon`.

## Por qué no las plataformas "gratis" con servidor

Cada intento quedó documentado en la bitácora (E48–E51): Hugging Face pasó
su tier CPU a suscripción PRO (error 402 al publicar); Claw Cloud empezó
a exigir un plan de pago para entrar; Render/Koyek ofrecen 512 MB y la
app muere con OOM en la primera verificación (verificado con el límite
exacto de memoria); Azure ya no tiene capa free sin tarjeta. La imagen
Docker validada (`deploy/Dockerfile`) queda lista por si alguna de ellas
vuelve a ser viable.

## Emergencia: demo desde el PC

`deploy/demo_publica.py` sirve la versión Gradio desde el propio PC con
un túnel cloudflared (E48). Depende del PC encendido; no es la vía
recomendada.
