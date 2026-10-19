# Demo estática (`deploy/estatica/`)

La demo pública del proyecto: el modelo de despliegue exportado a ONNX
corre **en el navegador del visitante** (ONNX Runtime Web), con la lógica
del agente replicada en JS desde `src/safesite/` (umbrales por clase,
K=3, cooldown, re-anclaje de gafas, mensaje de WhatsApp solo mostrado).

## Publicación

Se sirve por **GitHub Pages** (gratis para siempre, sin tarjeta) en la
rama `gh-pages` del propio repo:

- `generar.py` — produce los assets (modelo, 140 fotos de test con sus
  etiquetas, figuras del EDA, `datos.js` con las métricas reales).
- `publicar_pages.py` — arma el staging, hace commit a la rama `gh-pages`
  y la empuja. La activación de Pages es una vez:
  **Settings → Pages → Branch: gh-pages, / (root) → Save**.

URL resultante: `https://williamlzn.github.io/SAFESITE-AGENT/`

## Prueba local

```powershell
.venv\Scripts\python.exe deploy\estatica\generar.py
.venv\Scripts\python.exe -m http.server 8080 --directory deploy\estatica
# abrir http://localhost:8080
```

## Historial de hospedaje (por qué Pages)

La búsqueda de un hosting gratuito permanente quedó documentada en la
bitácora (E48–E53): HF cobró su tier con servidor y luego su static Space
resultó bloqueado en cuentas free ("Refreshing" eterno, verificado
recreándolo de cero); Claw Cloud pasó a cobrar; Render/Koyek no tienen
RAM para la app con servidor (pico medido 677 MB, OOM a los 512 MB);
Azure ya no tiene capa free sin tarjeta. La estática + GitHub Pages es
la única combinación gratis, sin tarjeta, permanente y sin
dependencias de promociones.

Los assets (`modelo/`, `fotos/`, `figuras/`, `datos.js`) no se versionan
en `main`: se regeneran con `generar.py` y los sube `publicar_pages.py`.
