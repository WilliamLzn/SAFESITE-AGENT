"""Publica la demo estática en un Hugging Face Space (sdk: static).

Los Static Spaces son gratis para todos (no requieren la suscripción PRO
que sí piden los Spaces con servidor, E48), no se duermen y sirven los
archivos por CDN. El modelo corre en el navegador del visitante.

Uso, desde la raíz del repo:
    $env:HF_TOKEN = "hf_xxx"   # token de escritura (huggingface.co/settings/tokens)
    .venv\\Scripts\\python.exe deploy\\estatica\\publicar_estatica.py --repo-id TU_USUARIO/safesite-demo

Antes de publicar corre generar.py para que existan los assets.
"""
import argparse
import os
import sys

from huggingface_hub import HfApi

AQUI = os.path.dirname(os.path.abspath(__file__))


def main():
    parser = argparse.ArgumentParser(
        description="Publica deploy/estatica/ como Space estático")
    parser.add_argument("--repo-id", required=True,
                        help="usuario/safesite-demo (el nombre que quieras)")
    args = parser.parse_args()

    if not os.path.exists(os.path.join(AQUI, "modelo", "best.onnx")):
        sys.exit("Faltan los assets: corre antes  "
                 ".venv\\Scripts\\python.exe deploy\\estatica\\generar.py")

    token = os.environ.get("HF_TOKEN")
    if not token:
        sys.exit("Falta el token:  $env:HF_TOKEN = 'hf_...'  "
                 "(huggingface.co/settings/tokens, permiso de escritura)")

    api = HfApi(token=token)
    print(f"Creando/actualizando el Space {args.repo_id} (sdk static)…")
    api.create_repo(repo_id=args.repo_id, repo_type="space",
                    space_sdk="static", private=False, exist_ok=True)
    print("Subiendo la página y el modelo (~75 MB la primera vez)…")
    url = api.upload_folder(
        repo_id=args.repo_id, repo_type="space",
        folder_path=AQUI,
        commit_message="Demo estática: SafeSite Agent con el modelo en el navegador",
        ignore_patterns=["generar.py", "publicar_estatica.py",
                         "space_build", "__pycache__"],
    )
    print("\n✅ Space actualizado.")
    print(f"   URL pública: https://{args.repo_id.split('/')[0].lower()}-"
          f"{args.repo_id.split('/')[1]}.hf.space")
    print("   (la primera construcción tarda un par de minutos)")
    print(f"   Página del Space: https://huggingface.co/spaces/{args.repo_id}")


if __name__ == "__main__":
    main()
