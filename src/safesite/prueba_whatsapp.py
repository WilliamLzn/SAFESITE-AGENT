"""Prueba end-to-end Fase 4 — alertas REALES de WhatsApp con frame anotado.

Ejecuta el agente completo (percepcion -> confirmacion K frames -> cooldown
-> alerta) sobre las primeras escenas de incidente de un split, enviando
mensajes REALES por WhatsApp Business Cloud API con la imagen del frame
anotado como evidencia.

Con el numero de PRUEBA de Meta solo llegan a los destinatarios permitidos
(verificados en el panel). Requiere credenciales en el entorno o en .env:
WHATSAPP_TOKEN, WHATSAPP_PHONE_ID, WHATSAPP_DESTINATARIO.

Ejecutar desde la RAIZ del proyecto:
    .venv\\Scripts\\python.exe -m src.safesite.prueba_whatsapp --escenas 3 --device 0

Con --rutas procesa IMAGENES CONCRETAS (envio REAL de WhatsApp) en lugar
de la rotacion automatica; el GT se lee de su etiqueta hermana en
dataset_v2/labels/<split>/ (si existe):
    .venv\\Scripts\\python.exe -m src.safesite.prueba_whatsapp --device 0 \\
        --rutas dataset_v2\\images\\test\\<imagen>.jpg
"""
import argparse
import json
import os
import time

import cv2

from . import config
from .actuarios import ActuadorConsola, ActuadorWhatsApp
from .agente import SafeSiteAgent
from .demo import (BASE, FPS_SIMULADO, FRAMES_POR_ESCENA, cargar_escenas,
                   clases_de_ruta)

SALIDA = os.path.join(BASE, "eda", "salidas", "resumen_fase4_whatsapp.json")
RUTA_PUNTERO = os.path.join(BASE, "runs", "agente", "puntero_prueba.txt")


class ActuadorWhatsAppForzado(ActuadorWhatsApp):
    """Prueba end-to-end: los envios son deliberados y secuenciales (el
    usuario pidio explicitamente correr la prueba), asi que bypassan los
    limites anti-spam globales del canal (forzar=True, E32)."""

    def alertar(self, incidente, frame_anotado=None, ruta_frame=None):
        return super().alertar(incidente, frame_anotado, ruta_frame,
                               forzar=True)

    def alertar_lote(self, incidentes, frame_anotado=None, ruta_frame=None):
        return super().alertar_lote(incidentes, frame_anotado, ruta_frame,
                                    forzar=True)


def _escenas_rotativas(incidentes, n):
    """Rotación determinista: cada corrida usa las siguientes n escenas
    (puntero persistente que cicla) — así las pruebas muestran variedad
    de tipos de incumplimiento en lugar de la misma escena."""
    os.makedirs(os.path.dirname(RUTA_PUNTERO), exist_ok=True)
    puntero = 0
    if os.path.exists(RUTA_PUNTERO):
        try:
            puntero = int(open(RUTA_PUNTERO, encoding="utf-8").read().strip())
        except ValueError:
            puntero = 0
    total = len(incidentes)
    indices = [(puntero + i) % total for i in range(n)]
    with open(RUTA_PUNTERO, "w", encoding="utf-8") as f:
        f.write(str((puntero + n) % total))
    return indices, [incidentes[i] for i in indices]


def main():
    parser = argparse.ArgumentParser(
        description="Prueba end-to-end del announcer de WhatsApp")
    parser.add_argument("--escenas", type=int, default=3,
                        help="numero de escenas de incidente a procesar")
    parser.add_argument("--rutas", nargs="+", default=None,
                        help="imagenes concretas a procesar (GT desde "
                             "dataset_v2/labels) en lugar de la rotacion")
    parser.add_argument("--split", default="val",
                        choices=("train", "val", "test"))
    parser.add_argument("--device", default=config.DEVICE_DEFECTO)
    args = parser.parse_args()

    # 0) comprobar credenciales ANTES de procesar nada
    act_whatsapp = ActuadorWhatsAppForzado()
    if act_whatsapp.modo != "ENVIO-REAL":
        raise SystemExit(
            "Credenciales WhatsApp incompletas (WHATSAPP_TOKEN, "
            "WHATSAPP_PHONE_ID, WHATSAPP_DESTINATARIO). Ver .env")
    destino = act_whatsapp.destinatario
    print(f"Destinatario: ***{destino[-4:]} | modo: {act_whatsapp.modo}")

    # 1) agente con checkpoint de despliegue (config.RUTA_MODELO)
    agente = SafeSiteAgent(device=args.device,
                           actuadores=[ActuadorConsola(), act_whatsapp])
    print(f"Modelo: {config.RUTA_MODELO} | device: {args.device}")

    # 2) escenas: concretas (--rutas) o rotativas por split
    if args.rutas:
        indices, escenas = [], []
        for ruta in args.rutas:
            base = os.path.splitext(os.path.basename(ruta))[0]
            gt = set()
            for split in ("train", "val", "test"):
                lbl = os.path.join(BASE, "dataset_v2", "labels", split,
                                   base + ".txt")
                if os.path.exists(lbl):
                    gt = clases_de_ruta(lbl) & config.CLASES_INCUMPLIMIENTO
                    break
            indices.append(base)
            escenas.append((ruta, gt))
        print(f"escenas concretas: {indices}")
    else:
        # escenas de incidente del split elegido (ROTATIVAS)
        incidentes, _ = cargar_escenas(args.split)
        if not incidentes:
            raise SystemExit(f"Sin escenas de incidente en split {args.split}")
        indices, escenas = _escenas_rotativas(incidentes, args.escenas)
        print(f"escenas rotativas #{indices} de {len(incidentes)} disponibles "
              f"(split {args.split})")

    # 3) correr el agente (4 frames/escena, igual que el demo)
    t_inicio = time.perf_counter()
    escenas_con_alerta = 0
    escenas_usadas = []
    for idx_escena, (ruta_jpg, gt) in zip(indices, escenas):
        frame = cv2.imread(ruta_jpg)
        zona = (f"prueba_{args.split}_{idx_escena:04d}"
                if isinstance(idx_escena, int) else f"prueba_{idx_escena}")
        alerto = False
        clases_alertadas = []
        for k in range(FRAMES_POR_ESCENA):
            incidentes_conf, _ = agente.procesar_frame(
                frame, zona=zona,
                t_stamp=time.time() + k * (1.0 / FPS_SIMULADO),
                origen=os.path.basename(ruta_jpg))
            if incidentes_conf:
                alerto = True
                clases_alertadas = sorted(i.clase for i in incidentes_conf)
                break  # una alerta (consolidada) por escena basta
        escenas_usadas.append({"indice": idx_escena,
                                "gt": sorted(gt),
                                "alertadas": clases_alertadas})
        if alerto:
            escenas_con_alerta += 1
        print(f"escena #{idx_escena} gt={sorted(gt)} -> "
              f"{'ALERTA ENVIADA (' + ', '.join(clases_alertadas) + ')' if alerto else 'sin deteccion'}")

    duracion = time.perf_counter() - t_inicio
    http_llamadas = len(act_whatsapp.tiempos_envio_ms)
    resumen = {
        "prueba": "end-to-end WhatsApp (Fase 4)",
        "modelo": config.RUTA_MODELO,
        "device": args.device,
        "split": args.split,
        "escenas_procesadas": len(escenas),
        "escenas_usadas": escenas_usadas,
        "escenas_con_alerta_whatsapp": escenas_con_alerta,
        "nota": "alertas CONSOLIDADAS: un mensaje por escena con todas "
                "las faltas y una sola foto",
        "llamadas_http_api": http_llamadas,
        "latencia_whatsapp_media_ms": round(
            sum(act_whatsapp.tiempos_envio_ms) / http_llamadas, 1)
        if http_llamadas else None,
        "latencia_whatsapp_max_ms": round(max(act_whatsapp.tiempos_envio_ms), 1)
        if http_llamadas else None,
        "latencia_agente_media_ms": round(agente.latencia_media_ms, 1),
        "duracion_total_s": round(duracion, 1),
    }
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(f"\nResumen guardado en: {SALIDA}")


if __name__ == "__main__":
    main()
