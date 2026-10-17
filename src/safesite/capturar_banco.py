"""SafeSite-Agent — Banco de pruebas EN VIVO (captura): frames por escenario.

Graba frames de webcam en poses CONTROLADAS (con/sin cada EPP). Esos mismos
frames alimentan dos cosas:
  1) la evaluacion por clase del banco (banco_vivo.py), y
  2) el conjunto de fine-tune del dominio webcam (BITACORA E35: solucion de
     raiz para gafas; y para el chaleco, etiquetando una clase nueva
     `no_vest` si los datos lo respaldan).

La ventana muestra el video ANOTADO con lo que ve el modelo (mismo formato
que el panel) para que observes en vivo donde falla mientras posas.

Uso (desde la raiz del repo):
  .venv\\Scripts\\python.exe -m src.safesite.capturar_banco --device 0

Teclas:  1-7 elegir escenario · ESPACIO iniciar/detener rafaga · ESC salir
Consejo: ~40 frames por escenario; varia ligeramente la pose/angulo durante
la rafaga (los frames casi identicos valen para confirmacion temporal, los
variados valen mas para el fine-tune).
"""
import argparse
import glob
import json
import os
import sys
import time
from datetime import datetime

import cv2

from . import config
from .banco_vivo import ESCENARIOS_BANCO
from .percepcion import Percepcion
from .razonamiento import Razonamiento

DIR_CAPTURAS = os.path.join("runs", "agente", "banco_vivo", "capturas")
ARCHIVO_MANIFIESTO = os.path.join(DIR_CAPTURAS, "manifiesto.json")


def _hud(img, actual, conteos, capturando, n_burst, objetivo):
    """Superficie de estado: escenarios, conteos y ayuda de teclas."""
    alto = img.shape[0]
    cv2.rectangle(img, (0, 0), (330, 30 + 22 * (len(ESCENARIOS_BANCO) + 3)),
                  (20, 20, 20), -1)
    y = 22
    cv2.putText(img, "BANCO VIVO — 1-7 escenario · ESPACIO capturar · ESC salir",
                (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
    for i, (nombre, def_) in enumerate(ESCENARIOS_BANCO.items()):
        y += 22
        color = (80, 220, 80) if nombre == actual else (160, 160, 160)
        marca = ">" if nombre == actual else " "
        cv2.putText(img, f"{marca}{i + 1} {nombre} [{conteos.get(nombre, 0)}]",
                    (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    y += 22
    cv2.putText(img, ESCENARIOS_BANCO[actual]["descripcion"][:44],
                (8, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 0), 1)
    if capturando:
        cv2.rectangle(img, (0, 0), (img.shape[1] - 1, alto - 1), (0, 0, 255), 6)
        cv2.putText(img, f"CAPTURANDO {actual}: {n_burst}/{objetivo} (ESPACIO=detener)",
                    (img.shape[1] - 430, alto - 14),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 255), 2)


def _guardar_manifiesto(sesion, bursts):
    """Reescribe el manifiesto escaneando el disco (robusto a recargas)."""
    conteos = {}
    for nombre in ESCENARIOS_BANCO:
        carpeta = os.path.join(DIR_CAPTURAS, nombre)
        conteos[nombre] = len(glob.glob(os.path.join(carpeta, "*.jpg")))
    os.makedirs(DIR_CAPTURAS, exist_ok=True)
    with open(ARCHIVO_MANIFIESTO, "w", encoding="utf-8") as f:
        json.dump({"sesion": sesion, "frames_por_escenario": conteos,
                   "bursts_de_esta_sesion": bursts,
                   "escenarios": ESCENARIOS_BANCO},
                  f, ensure_ascii=False, indent=2)


def main():
    # consolas Windows en cp1252 no pueden con los emojis del log
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Captura de frames por escenario para el banco en vivo.")
    parser.add_argument("--device", default=None,
                        help="cpu | 0 | cuda:0 para la anotacion en vivo")
    parser.add_argument("--camara", type=int, default=0)
    parser.add_argument("--ancho", type=int, default=1280)
    parser.add_argument("--alto", type=int, default=720)
    parser.add_argument("--frames", type=int, default=40,
                        help="frames por rafaga (default 40)")
    parser.add_argument("--fps", type=float, default=5.0,
                        help="frames guardados por segundo en la rafaga (default 5)")
    parser.add_argument("--sin-modelo", action="store_true",
                        help="capturar sin anotar (mas rapido en CPU)")
    args = parser.parse_args()

    cam = cv2.VideoCapture(args.camara, cv2.CAP_DSHOW)
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, args.ancho)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, args.alto)
    if not cam.isOpened():
        raise SystemExit(f"❌ no se pudo abrir la camara {args.camara}")

    percepcion, razonamiento = None, None
    if not args.sin_modelo:
        percepcion = Percepcion(device=args.device)
        # anotacion con el perfil VIVO (lo mismo que ves en el panel)
        razonamiento = Razonamiento(
            umbrales_incumplimiento=config.UMBRALES_INCUMPLIMIENTO_VIVO,
            coherencia=config.REGLA_COHERENCIA_VIVO)
        print(f"👁️ anotacion en vivo con {percepcion.ruta_modelo} "
              f"(device={percepcion.device})", flush=True)

    escenarios = list(ESCENARIOS_BANCO)
    actual = escenarios[0]
    conteos = {n: len(glob.glob(os.path.join(DIR_CAPTURAS, n, "*.jpg")))
               for n in ESCENARIOS_BANCO}
    capturando, n_burst = False, 0
    t_ultimo_save, bursts = 0.0, []
    sesion = datetime.now().isoformat(timespec="seconds")
    print(f"🎬 sesion {sesion} — recinto de capturas: {DIR_CAPTURAS}", flush=True)

    # calentamiento del sensor (primeros frames suelen salir oscuros)
    for _ in range(10):
        cam.read()

    try:
        while True:
            ok, frame = cam.read()
            if not ok:
                print("⚠️ frame invalido de la camara; reintentando...",
                      flush=True)
                time.sleep(0.05)
                continue

            vista = frame
            if percepcion is not None:
                try:
                    dets = percepcion.detectar(frame)
                    vista = percepcion.anotar(frame, razonamiento.filtrar_por_clase(dets))
                except Exception as e:            # la anotacion NUNCA frena la captura
                    print(f"⚠️ anotacion fallo ({type(e).__name__}: {e})",
                          flush=True)
                    vista = frame

            if capturando:
                ahora = time.time()
                if ahora - t_ultimo_save >= 1.0 / args.fps:
                    carpeta = os.path.join(DIR_CAPTURAS, actual)
                    os.makedirs(carpeta, exist_ok=True)
                    base = len(glob.glob(os.path.join(carpeta, "*.jpg")))
                    ruta = os.path.join(carpeta, f"f_{base:04d}.jpg")
                    cv2.imwrite(ruta, frame,     # frame CRUDO (fine-tune)
                                [cv2.IMWRITE_JPEG_QUALITY, 95])
                    n_burst += 1
                    t_ultimo_save = ahora
                    conteos[actual] = base + 1
                    if n_burst >= args.frames:
                        capturando = False
                        bursts.append({"escenario": actual, "n": n_burst,
                                       "t": datetime.now().isoformat(
                                           timespec="seconds")})
                        print(f"  ✅ rafaga lista: {actual} +{n_burst} frames "
                              f"(total {conteos[actual]})", flush=True)
                        _guardar_manifiesto(sesion, bursts)

            _hud(vista, actual, conteos, capturando, n_burst, args.frames)
            cv2.imshow("SafeSite — banco en vivo (captura)", vista)

            tecla = cv2.waitKey(1) & 0xFF
            if tecla == 27:                     # ESC
                break
            if tecla == 32:                     # ESPACIO: iniciar/detener rafaga
                if capturando:
                    capturando = False
                    bursts.append({"escenario": actual, "n": n_burst,
                                   "t": datetime.now().isoformat(
                                       timespec="seconds")})
                    print(f"  ⏹️ rafaga detenida: {actual} +{n_burst} frames",
                          flush=True)
                    _guardar_manifiesto(sesion, bursts)
                else:
                    capturando, n_burst = True, 0
                    t_ultimo_save = 0.0
                    print(f"  ⏺️ capturando {actual}: "
                          f"{ESCENARIOS_BANCO[actual]['descripcion']}",
                          flush=True)
            elif ord("1") <= tecla <= ord("7"):
                if capturando:                      # cambio de escenario a mitad
                    bursts.append({"escenario": actual, "n": n_burst,
                                   "t": datetime.now().isoformat(
                                       timespec="seconds")})
                    print(f"  ⏹️ rafaga detenida: {actual} +{n_burst} frames",
                          flush=True)
                actual = escenarios[tecla - ord("1")]
                capturando = False
                print(f"▶️ escenario: {actual} — "
                      f"{ESCENARIOS_BANCO[actual]['descripcion']}", flush=True)
    finally:
        cam.release()
        cv2.destroyAllWindows()
        _guardar_manifiesto(sesion, bursts)
        print(f"📦 manifiesto: {ARCHIVO_MANIFIESTO}", flush=True)
        print("\nSiguiente paso:", flush=True)
        print(r"  .venv\Scripts\python.exe -m src.safesite.banco_vivo --device 0",
              flush=True)


if __name__ == "__main__":
    main()
