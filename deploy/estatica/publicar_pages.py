"""Publica la demo estática en GitHub Pages (rama gh-pages del repo).

GitHub Pages sirve archivos estáticos gratis para siempre, sin tarjeta y
sin promociones que caduquen — la demo del modelo-en-el-navegador no
necesita nada más. El sitio queda en:

    https://williamlzn.github.io/SAFESITE-AGENT/

La rama gh-pages es huérfana: contiene SOLO el sitio (index.html, app.js,
styles.css, datos.js, el modelo ONNX, las fotos de test y las figuras),
nada del repositorio de código.

Requisito único (una vez): activar Pages en GitHub → Settings → Pages →
Branch: gh-pages, carpeta / (root) → Save.

Uso, desde la raíz del repo:
    .venv\\Scripts\\python.exe deploy\\estatica\\publicar_pages.py
"""
import argparse
import os
import shutil
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(os.path.dirname(AQUI))
REMOTE = "https://github.com/WilliamLzn/SAFESITE-AGENT.git"
RAMA = "gh-pages"

README_SITIO = """# SafeSite Agent — demo en vivo

Este sitio es la demo pública del proyecto
[SAFESITE-AGENT](https://github.com/WilliamLzn/SAFESITE-AGENT): el mismo
modelo YOLOv8s exportado a ONNX corriendo **en el navegador del
visitante**, con la lógica del agente (confirmación K=3, cooldown,
umbrales por clase) replicada desde `src/safesite/`.

Rama servida por GitHub Pages; el código del proyecto vive en `main`.
"""

# lo que va al sitio (igual que el staging del publicador de HF, E53)
SITIO = ["index.html", "app.js", "styles.css", "datos.js"]
CARPETAS = ["modelo", "fotos", "figuras"]


def _run(cmd, cwd):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"ERROR en {' '.join(cmd)}:\n{r.stderr}\n{r.stdout}")
    return r.stdout


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    parser = argparse.ArgumentParser(
        description="Publica la demo estática en la rama gh-pages")
    parser.add_argument("--dry-run", action="store_true",
                        help="prepara la rama y muestra el resumen sin "
                             "hacer push")
    args = parser.parse_args()

    staging = os.path.join(tempfile.gettempdir(), "safesite_pages_build")
    if os.path.exists(staging):
        shutil.rmtree(staging)
    os.makedirs(staging)

    for nombre in SITIO:
        origen = os.path.join(AQUI, nombre)
        if not os.path.exists(origen):
            sys.exit(f"Falta {origen} — corre antes "
                     ".venv\\Scripts\\python.exe deploy\\estatica\\generar.py")
        shutil.copy2(origen, os.path.join(staging, nombre))
    for carpeta in CARPETAS:
        shutil.copytree(os.path.join(AQUI, carpeta),
                        os.path.join(staging, carpeta))
    with open(os.path.join(staging, "README.md"), "w",
              encoding="utf-8") as f:
        f.write(README_SITIO)
    print(f"Staging listo: {len(os.listdir(staging))} entradas "
          f"(~75 MB)")

    _run(["git", "init", "-b", RAMA], cwd=staging)
    _run(["git", "add", "-A"], cwd=staging)
    _run(["git", "commit", "-m",
          "Demo estatica: SafeSite Agent con el modelo en el navegador"],
         cwd=staging)
    _run(["git", "remote", "add", "origin", REMOTE], cwd=staging)
    _run(["git", "config", "user.name",
          _run(["git", "config", "user.name"], cwd=RAIZ).strip()
          or "WilliamLzn"], cwd=staging)
    _run(["git", "config", "user.email",
          _run(["git", "config", "user.email"], cwd=RAIZ).strip()
          or "williamlzno@users.noreply.github.com"], cwd=staging)

    n = sum(len(files) for _, _, files in os.walk(staging)) - 1
    print(f"Rama {RAMA} con {n} archivos lista "
          f"(index, app, datos, modelo, {n - 6} fotos… etc).")
    if args.dry_run:
        print("--dry-run: no se hizo push.")
        return
    print("Haciendo push a origin/gh-pages (≈75 MB, puede tardar)…")
    _run(["git", "push", "origin", RAMA], cwd=staging)
    print("\n✅ Rama gh-pages publicada.")
    print("   Falta UN paso (una vez): GitHub → SAFESITE-AGENT → Settings")
    print("   → Pages → Branch: gh-pages, carpeta / (root) → Save.")
    print("   En ~1-2 min: https://williamlzn.github.io/SAFESITE-AGENT/")


if __name__ == "__main__":
    main()
