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
"""
import argparse
import json
import os
import time

import cv2

from . import config
from .actuarios import ActuadorConsola, ActuadorWhatsApp
from .agente import SafeSiteAgent
from .demo import BASE, FPS_SIMULADO, FRAMES_POR_ESCENA, cargar_escenas

SALIDA = os.path.join(BASE, "eda", "salidas", "resumen_fase4_whatsapp.json")


def main():
    parser = argparse.ArgumentParser(
        description="Prueba end-to-end del announcer de WhatsApp")
    parser.add_argument("--escenas", type=int, default=3,
                        help="numero de escenas de incidente a procesar")
    parser.add_argument("--split", default="val",
                        choices=("train", "val", "test"))
    parser.add_argument("--device", default=config.DEVICE_DEFECTO)
    args = parser.parse_args()

    # 0) comprobar credenciales ANTES de procesar nada
    act_whatsapp = ActuadorWhatsApp()
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

    # 2) escenas de incidente del split elegido
    incidentes, _ = cargar_escenas(args.split)
    escenas = incidentes[:args.escenas]
    if not escenas:
        raise SystemExit(f"Sin escenas de incidente en split {args.split}")

    # 3) correr el agente (4 frames/escena, igual que el demo)
    t_inicio = time.perf_counter()
    escenas_con_alerta = 0
    for idx, (ruta_jpg, gt) in enumerate(escenas):
        frame = cv2.imread(ruta_jpg)
        zona = f"prueba_{args.split}_{idx:04d}"
        alerto = False
        for k in range(FRAMES_POR_ESCENA):
            incidentes_conf, _ = agente.procesar_frame(
                frame, zona=zona,
                t_stamp=time.time() + k * (1.0 / FPS_SIMULADO),
                origen=os.path.basename(ruta_jpg))
            if incidentes_conf:
                alerto = True
                break  # una alerta por escena basta para la prueba
        if alerto:
            escenas_con_alerta += 1
        print(f"escena {idx + 1}/{len(escenas)} gt={sorted(gt)} -> "
              f"{'ALERTA ENVIADA' if alerto else 'sin deteccion'}")

    duracion = time.perf_counter() - t_inicio
    http_llamadas = len(act_whatsapp.tiempos_envio_ms)
    resumen = {
        "prueba": "end-to-end WhatsApp (Fase 4)",
        "modelo": config.RUTA_MODELO,
        "device": args.device,
        "split": args.split,
        "escenas_procesadas": len(escenas),
        "escenas_con_alerta_whatsapp": escenas_con_alerta,
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
