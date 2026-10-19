# Deploy de la demo (SafeSite-Agent)

Agente que revisa fotos de obra buscando trabajadores sin su equipo de
protección. Detecta con YOLOv8s, confirma una falta solo cuando la ve en 3
frames seguidos y arma el aviso al supervisor por WhatsApp (en la demo el
aviso solo se muestra, no se envía).

## Demo pública permanente: Google Cloud Run (activa)

La demo completa (Gradio, PyTorch en servidor) corre en Cloud Run con
escala a cero: gasto nulo sin tráfico, despertar automático con la
primera visita (1 a 3 min la primera carga), URL permanente:

**https://safesite-ui-428834791978.us-central1.run.app**

Proyecto: `safesite-512105` (region us-central1). Publicar o actualizar
(requiere gcloud autenticado y el proyecto con facturación activa):

```powershell
.venv\Scripts\python.exe deploy\cloudrun_publicar.py --project safesite-512105
```

El publicador arma un staging limpio (solo lo que copia el Dockerfile:
sin .venv ni dataset crudo), construye en Cloud Build, guarda la imagen
en Artifact Registry y despliega con min-instances=0, max=1, 2 GiB,
timeout 900, cpu-boost y allow-unauthenticated. Borrado al terminar la
evaluación:

```powershell
gcloud run services delete safesite-ui --region=us-central1
```

## Versión con servidor propia: app.py (Gradio)

`deploy/app.py` es la misma demo para correr donde se quiera (local con
GPU, un VPS propio, Codespaces). Escucha el puerto de `PORT` y la IP
`0.0.0.0` dentro de contenedores:

```powershell
.venv\Scripts\python.exe deploy\app.py --tema grafito
```

El color se elige con `--tema` o la variable `SAFESITE_TEMA`:
`esmeralda` (default), `grafito`, `rosa`, `ambar`, `azul`, `ocean`, `neon`.

## Respaldo estático (ONNX en el navegador)

`deploy/estatica/` sirve la demo sin servidor: el modelo exportado a
ONNX corre en el navegador del visitante (GitHub Pages, rama `gh-pages`,
con `publicar_pages.py`). Equivalencia del export verificada contra el
original (mismas detecciones, Δconf ≤ 0.018).

## Historial de hospedaje (por qué Cloud Run)

Cada intento quedó documentado en la bitácora (E48 a E56): Hugging Face
cobró su tier con servidor y su static Space resultó bloqueado en
cuentas free; Claw Cloud pasó a cobrar; Render/Koyek no tienen RAM (la
app pica a 677 MB y muere con OOM a los 512 MB); Azure ya no tiene capa
free sin tarjeta; Modal funcionó (E54) y fue retirado al consolidarse
Cloud Run (E56, pedido del usuario). La imagen Docker validada
(`deploy/Dockerfile`) es la misma que corrió en Modal y la que hoy sirve
en Cloud Run.
