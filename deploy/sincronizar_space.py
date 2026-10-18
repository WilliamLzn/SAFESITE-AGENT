"""Arma la carpeta deploy/space_build/ con una copia del proyecto tal como
la necesita el Space (misma estructura de carpetas que la raíz del repo)
y, si hay token, la sube a Hugging Face.

Como el Space conserva la estructura, el código del agente funciona allá
sin ningún cambio de rutas.

Uso, desde la raíz del repo:
    $env:HF_TOKEN = "hf_xxx"   # token de escritura (huggingface.co/settings/tokens)
    .venv\\Scripts\\python.exe deploy\\sincronizar_space.py --repo-id <usuario>/safesite-agent-demo

    # armar la carpeta sin subir, para revisarla:
    .venv\\Scripts\\python.exe deploy\\sincronizar_space.py --no-push

El best.pt pesa más de 10 MB y huggingface_hub lo maneja con LFS solo, no
hace falta git-lfs. El .env y safesite_dataset/ nunca se copian: uno tiene
las credenciales y el otro es el respaldo crudo del dataset.
"""
import argparse
import os
import shutil
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)                    # raiz del repo
DESTINO = os.path.join(AQUI, "space_build")     # staging (gitignored)

CORRIDA_OFICIAL = "20261014_170459"             # la corrida que vale para la entrega

# (origen relativo a RAIZ, destino relativo a DESTINO)
COPIAS = [
    ("deploy/app.py", "app.py"),
    ("deploy/requirements.txt", "requirements.txt"),
    ("deploy/packages.txt", "packages.txt"),
    ("deploy/README.md", "README.md"),
    ("deploy/.gitattributes", ".gitattributes"),
    (os.path.join("runs", "safesite", "tuned_v2_s", "weights", "best.pt"),
     os.path.join("runs", "safesite", "tuned_v2_s", "weights", "best.pt")),
]
CARPETAS = [
    (os.path.join("src", "safesite"), os.path.join("src", "safesite"), ["*.py"]),
    (os.path.join("dataset_v2", "images", "val"),
     os.path.join("dataset_v2", "images", "val"), ["*.jpg"]),
    (os.path.join("dataset_v2", "images", "test"),
     os.path.join("dataset_v2", "images", "test"), ["*.jpg"]),
    (os.path.join("dataset_v2", "labels", "val"),
     os.path.join("dataset_v2", "labels", "val"), ["*.txt"]),
    (os.path.join("dataset_v2", "labels", "test"),
     os.path.join("dataset_v2", "labels", "test"), ["*.txt"]),
    (os.path.join("eda", "figuras"),
     os.path.join("eda", "figuras"), ["*.png"]),
    (os.path.join("eda", "salidas"),
     os.path.join("eda", "salidas"), ["metricas_e44.json"]),
    (os.path.join("runs", "agente", "pruebas"),
     os.path.join("runs", "agente", "pruebas"), ["*.csv", "*.json", "*.md",
                                                 "*.jsonl"]),
]


def _copiar_archivos():
    total = 0
    for origen, destino in COPIAS:
        ruta_o = os.path.join(RAIZ, origen)
        ruta_d = os.path.join(DESTINO, destino)
        if not os.path.exists(ruta_o):
            sys.exit(f"ERROR: no existe {ruta_o} — revisa el paso previo.")
        os.makedirs(os.path.dirname(ruta_d), exist_ok=True)
        shutil.copy2(ruta_o, ruta_d)
        total += 1
        print(f"  + {destino} ({os.path.getsize(ruta_d) / 1e6:.1f} MB)")
    for origen, destino, patrones in CARPETAS:
        ruta_o = os.path.join(RAIZ, origen)
        ruta_d = os.path.join(DESTINO, destino)
        os.makedirs(ruta_d, exist_ok=True)
        n = 0
        for nombre in sorted(os.listdir(ruta_o)):
            if not any(nombre.endswith(p.replace("*", "")) for p in patrones):
                continue
            shutil.copy2(os.path.join(ruta_o, nombre), os.path.join(ruta_d, nombre))
            n += 1
        total += n
        print(f"  + {destino}/ ({n} archivos)")
    return total


def _peso_mb(ruta):
    suma = 0
    for dirpath, _, archivos in os.walk(ruta):
        for a in archivos:
            suma += os.path.getsize(os.path.join(dirpath, a))
    return suma / 1e6


def ensamblar(limpiar=True):
    if limpiar and os.path.exists(DESTINO):
        shutil.rmtree(DESTINO)
    os.makedirs(DESTINO, exist_ok=True)
    print(f"Armando la carpeta del Space en {DESTINO} "
          "(misma estructura que la raiz del repo):")
    total = _copiar_archivos()
    mb = _peso_mb(DESTINO)
    print(f"Listo: {total} archivos, {mb:.1f} MB (el modelo pesa 21.5 MB "
          f"y las imágenes de val y test, 27.6).")
    print("El .env y safesite_dataset/ no se copian.")


def publicar(repo_id):
    try:
        from huggingface_hub import HfApi
    except ImportError:
        sys.exit("Falta huggingface_hub:  .venv\\Scripts\\python.exe -m pip "
                 "install huggingface_hub")
    token = os.environ.get("HF_TOKEN")
    api = HfApi(token=token)
    print(f"Publicando en el Space {repo_id} …")
    api.create_repo(repo_id=repo_id, repo_type="space", space_sdk="gradio",
                    private=False, exist_ok=True)
    url = api.upload_folder(
        repo_id=repo_id, repo_type="space",
        folder_path=DESTINO, commit_message="Actualizacion de la demo",
    )
    print("\n✅ Space actualizado.")
    print(f"   URL publica: https://huggingface.co/spaces/{repo_id}")
    print("   (la primera construccion tarda ~5-10 min; luego ~1-2 min "
          "de arranque en frio)")


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-id", required=False,
                        help="usuario/safesite-agent-demo (requerido para "
                             "publicar)")
    parser.add_argument("--no-push", action="store_true",
                        help="solo ensamblar space_build/, no subir")
    args = parser.parse_args()

    ensamblar()
    if not args.no_push:
        if not args.repo_id:
            sys.exit("ERROR: --repo-id es requerido para publicar "
                     "(o usa --no-push).")
        publicar(args.repo_id)


if __name__ == "__main__":
    main()
