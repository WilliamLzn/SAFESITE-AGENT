"""SafeSite-Agent — la demo Gradio completa servida en Modal.

Modal corre contenedores on-demand: la app DUERME cuando nadie la usa
(no gasta crédito) y DESPIERTA sola con la primera visita (~40-60 s la
primera vez: importar torch + cargar la página; luego fluido). La URL
modal.run es permanente, no depende del PC del equipo y la capa gratuita
de Modal no pide tarjeta.

La imagen es EXACTAMENTE la de deploy/Dockerfile (validada en E50: HTTP
200 + verificación real por API): se arma un staging limpio como contexto
de build para no subir el .venv entero.

Uso (después de `modal token new` una vez):
    .venv\\Scripts\\python.exe -m modal deploy deploy/modal_app.py
"""
import os
import shutil
import tempfile

import modal

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGING = os.path.join(tempfile.gettempdir(), "safesite_modal_build")

# lo que el Dockerfile copia dentro de la imagen (nada más al contexto)
COPIAS = [
    ("deploy/Dockerfile", "Dockerfile"),
    ("deploy/requirements.txt", "deploy/requirements.txt"),
    ("deploy/app.py", "deploy/app.py"),
    ("src/safesite", "src/safesite"),
    ("dataset_v2/dataset.yaml", "dataset_v2/dataset.yaml"),
    ("dataset_v2/images/val", "dataset_v2/images/val"),
    ("dataset_v2/images/test", "dataset_v2/images/test"),
    ("dataset_v2/labels/val", "dataset_v2/labels/val"),
    ("dataset_v2/labels/test", "dataset_v2/labels/test"),
    ("eda/figuras", "eda/figuras"),
    ("eda/salidas/metricas_e44.json", "eda/salidas/metricas_e44.json"),
    ("runs/safesite/tuned_v2_s/weights/best.pt",
     "runs/safesite/tuned_v2_s/weights/best.pt"),
    ("runs/agente/pruebas", "runs/agente/pruebas"),
]


def _armar_staging():
    if os.path.exists(STAGING):
        shutil.rmtree(STAGING)
    os.makedirs(STAGING)
    for origen, destino in COPIAS:
        o = os.path.join(RAIZ, origen)
        d = os.path.join(STAGING, destino)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        if os.path.isdir(o):
            shutil.copytree(o, d)
        else:
            shutil.copy2(o, d)
    return STAGING


# La imagen se construye SOLO en la máquina del cliente (donde existe el
# repo). Modal vuelve a importar este módulo DENTRO del contenedor para
# hidratar la función, y allí no existen ni el repo ni el staging: sin
# este guard, el import crashea y el contenedor muere en loop.
imagen = None
if os.path.exists(os.path.join(RAIZ, "deploy", "Dockerfile")):
    _armar_staging()
    imagen = modal.Image.from_dockerfile(
        os.path.join(STAGING, "Dockerfile"), context_dir=STAGING)

app = modal.App("safesite-demo")


# max_containers=1: NUNCA se crean contenedores en paralelo (una sola
# instancia sirve todo; sin esto, cada request impaciente puede abrir
# contenedores extra y quemar crédito en arranques que no sirven nada).
@app.function(image=imagen, memory=2048, cpu=2, scaledown_window=120,
               max_containers=1)
@modal.web_server(8788, startup_timeout=600, label="demo")
def servir():
    """Arranca la página Gradio dentro del contenedor (la imagen ya trae
    todo; escucha 0.0.0.0:8788 por sus ENV). Bloquea: el contenedor vive
    mientras la app viva, y duerme tras 5 min sin visitas."""
    import subprocess
    subprocess.run(["python", "deploy/app.py"], cwd="/app", check=False)
