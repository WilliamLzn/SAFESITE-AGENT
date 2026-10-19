"""SafeSite-Agent — publica la demo Gradio en Google Cloud Run.

Cloud Run sirve contenedores con escala a cero (URL permanente, gasto
solo con tráfico) y es la alternativa documentada a Modal (E54). Este
script reutiliza la imagen Docker ya validada del proyecto (E50/E55) y
hace el trabajo pesado: arma un staging limpio (para que el .gitignore
no excluya el modelo del contexto de build) y corre los comandos gcloud.

Requisitos UNA vez (solo puede hacerlos el dueño de la cuenta):
  1. Tarjeta de credito asociada en console.cloud.google.com (Cloud Run
     la exige aunque el uso quede en la capa gratuita). Configurar un
     presupuesto y una alerta de gasto ANTES de desplegar.
  2. Google Cloud CLI instalada:  winget install GoogleCloudSDK.gcloud
  3. Autenticacion:  gcloud auth login
  4. Elegir el proyecto:  gcloud config set project ID_DEL_PROYECTO

Uso, desde la raiz del repo:
    .venv\\Scripts\\python.exe deploy\\cloudrun_publicar.py --project ID_DEL_PROYECTO [--region us-central1]
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)                 # deploy/ -> raiz del repo
STAGING = os.path.join(tempfile.gettempdir(), "safesite_cloudrun_build")

# lo que entra al contexto de build (lo mismo que copia el Dockerfile)
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


def _run(cmd, cwd=None):
    # gcloud en Windows es un .cmd y CreateProcess no lo lanza directo:
    # hay que pasar por cmd.exe (con /c) para que resuelva el PATHEXT
    if os.name == "nt":
        cmd = ["cmd", "/c"] + cmd
    print("  $ " + " ".join(cmd), flush=True)
    r = subprocess.run(cmd, cwd=cwd)
    if r.returncode != 0:
        sys.exit(f"ERROR: el comando anterior fallo (codigo {r.returncode}). "
                 "Corrige lo que indique gcloud y vuelve a correr este script.")


def _armar_staging():
    if os.path.exists(STAGING):
        shutil.rmtree(STAGING)
    os.makedirs(STAGING)
    for origen, destino in COPIAS:
        o, d = os.path.join(RAIZ, origen), os.path.join(STAGING, destino)
        os.makedirs(os.path.dirname(d), exist_ok=True)
        if os.path.isdir(o):
            shutil.copytree(o, d)
        else:
            shutil.copy2(o, d)
    print(f"Staging listo en {STAGING} "
          f"(solo lo que necesita el Dockerfile; sin .venv ni dataset crudo)")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        description="Publica la demo en Cloud Run (build + deploy)")
    parser.add_argument("--project", required=True,
                        help="ID del proyecto de Google Cloud")
    parser.add_argument("--region", default="us-central1",
                        help="region de Cloud Run (default us-central1)")
    parser.add_argument("--solo-build", action="store_true",
                        help="construir y subir la imagen sin desplegar")
    args = parser.parse_args()

    if shutil.which("gcloud") is None:
        sys.exit("Falta gcloud:  winget install GoogleCloudSDK.gcloud  "
                 "y luego  gcloud auth login")

    repo = f"{args.region}-docker.pkg.dev/{args.project}/safesite/safesite-ui"
    imagen = f"{repo}:latest"

    print("1/3 habilitando APIs y creando el repositorio de imagenes...")
    _run(["gcloud", "services", "enable", "run.googleapis.com",
          "cloudbuild.googleapis.com", "artifactregistry.googleapis.com"])
    # el repositorio puede existir de corridas anteriores: no es error
    r = subprocess.run(
        ["cmd", "/c", "gcloud", "artifacts", "repositories", "create",
         "safesite", "--repository-format=docker", "--location", args.region],
        capture_output=True, text=True)
    if r.returncode != 0 and "already exists" not in (r.stdout + r.stderr):
        sys.exit(f"ERROR creando el repositorio:\n{r.stderr}")

    print("2/3 construyendo la imagen en Cloud Build (~75 MB de subida)...")
    _armar_staging()
    _run(["gcloud", "builds", "submit", STAGING, "--tag", imagen,
          f"--project={args.project}"])

    if args.solo_build:
        print(f"Imagen lista: {imagen}")
        return

    print("3/3 desplegando en Cloud Run (min-instances=0, max=1, 2 GiB)...")
    _run(["gcloud", "run", "deploy", "safesite-ui",
          "--image", imagen,
          f"--region={args.region}",
          f"--project={args.project}",
          "--allow-unauthenticated",
          "--memory", "2Gi",
          "--cpu", "2",
          "--min-instances", "0",
          "--max-instances", "1",
          "--timeout", "900",
          "--cpu-boost"])
    print("\nListo. La URL del servicio la imprime el comando anterior")
    print("(algo como https://safesite-ui-xxxx.run.app). Prueba el arranque")
    print("en frio UNA vez, con paciencia (1 a 3 min la primera visita).")
    print("Para borrar todo cuando termine la evaluacion:")
    print(f"  gcloud run services delete safesite-ui --region={args.region}")


if __name__ == "__main__":
    main()
