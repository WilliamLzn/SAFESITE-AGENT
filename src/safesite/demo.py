"""Demo Fase 3 — el agente SafeSite procesa escenas del dataset como video.

Diseno del experimento (metrica reencuadrada de la bitacora E21):
- Escenas de INCIDENTE: las imagenes de train con >=1 etiqueta `no_*`
  (239 escenas). Cada una se simula como K_SIM frames consecutivos a 2 FPS
  (el incumplimiento persiste en el tiempo, como en video real).
- Escenas de CONTROL: 100 imagenes de train SIN ninguna etiqueta `no_*`
  (semilla 42) -> tasa de falsas alarmas.
- Metricas:
  * recall A NIVEL DE FOTOGRAMA (percepcion cruda): la clase aparece en
    >=1 frame de la escena (sin confirmacion temporal);
  * recall A NIVEL DE INCIDENTE (agente completo): la clase se confirma
    con K frames consecutivos y dispara la alerta;
  * falsas alarmas en escenas de control;
  * latencia end-to-end por frame.

Ejecutar desde la RAIZ del proyecto:
    .venv\\Scripts\\python.exe -m src.safesite.demo
"""
import argparse
import json
import os
import sys

import cv2

from . import config
from .agente import SafeSiteAgent

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
FRAMES_POR_ESCENA = 4
FPS_SIMULADO = 2.0
SEED = 42


def _tag_del_modelo(ruta_modelo):
    """runs/safesite/<name>/weights/best.pt -> <name>; si no, 'custom'."""
    try:
        return os.path.basename(os.path.dirname(os.path.dirname(ruta_modelo)))
    except (IndexError, OSError):
        return "custom"


def clases_de_ruta(ruta_txt):
    ids = set()
    with open(ruta_txt, encoding="utf-8") as f:
        for ln in f:
            partes = ln.split()
            if len(partes) == 5:
                ids.add(int(partes[0]))
    return ids


def cargar_escenas(split):
    """Escenas de incidente y control de un split de dataset_v2."""
    img_dir = os.path.join(BASE, "dataset_v2", "images", split)
    lbl_dir = os.path.join(BASE, "dataset_v2", "labels", split)
    incidentes, control = [], []
    for nombre in sorted(os.listdir(lbl_dir)):
        if not nombre.endswith(".txt"):
            continue
        ids = clases_de_ruta(os.path.join(lbl_dir, nombre))
        ruta_jpg = os.path.join(img_dir, nombre[:-4] + ".jpg")
        if not os.path.exists(ruta_jpg):
            continue
        gt = ids & config.CLASES_INCUMPLIMIENTO
        if gt:
            incidentes.append((ruta_jpg, gt))
        else:
            control.append((ruta_jpg, gt))
    return incidentes, control


def simular_escena(agente, ruta_jpg, gt, zona, t_inicial):
    """Corre la escena por el agente; devuelve metricas de la escena."""
    frame = cv2.imread(ruta_jpg)
    clases_percibidas, clases_alertadas = set(), set()
    intervalo = 1.0 / FPS_SIMULADO
    for k in range(FRAMES_POR_ESCENA):
        t_stamp = t_inicial + k * intervalo
        incidentes, filtradas = agente.procesar_frame(
            frame, zona=zona, t_stamp=t_stamp,
            origen=os.path.basename(ruta_jpg))
        for d in filtradas:
            if d.cls_id in config.CLASES_INCUMPLIMIENTO:
                clases_percibidas.add(d.cls_id)
        for inc in incidentes:
            clases_alertadas.add(inc.clase_id)
    return {"gt": gt, "percibidas": clases_percibidas,
            "alertadas": clases_alertadas}


def evaluar_split(agente, split, verbose=True):
    """Ejecuta el agente sobre todas las escenas de un split (incidente+control).

    IMPORTANTE (honestidad metodologica): train esta inflado por memorizacion
    (el modelo vio esas imagenes al entrenarse). El numero creible es el de
    val/test. En video continuo el recall de incidente real sera >= el de
    esta simulacion (muchas mas oportunidades temporales que 4 frames fijos).
    """
    incidentes, control = cargar_escenas(split)
    if verbose:
        print(f"[{split}] escenas incidente: {len(incidentes)} | "
              f"control: {len(control)}")
    t0 = 0.0
    por_clase_percibido = {c: [0, 0] for c in config.CLASES_INCUMPLIMIENTO}
    por_clase_alertado = {c: [0, 0] for c in config.CLASES_INCUMPLIMIENTO}
    escenas_con_alerta_correcta = 0
    for idx, (ruta, gt) in enumerate(incidentes):
        r = simular_escena(agente, ruta, gt, f"{split}_{idx:04d}", t_inicial=t0)
        t0 += FRAMES_POR_ESCENA * 2.0
        acierto = False
        for c in gt:
            por_clase_percibido[c][1] += 1
            por_clase_alertado[c][1] += 1
            if c in r["percibidas"]:
                por_clase_percibido[c][0] += 1
            if c in r["alertadas"]:
                por_clase_alertado[c][0] += 1
                acierto = True
        if acierto:
            escenas_con_alerta_correcta += 1

    falsas, clases_falsas = 0, {}
    for j, (ruta, _) in enumerate(control):
        r = simular_escena(agente, ruta, set(),
                           f"{split}_ctrl_{j:04d}", t_inicial=t0)
        t0 += FRAMES_POR_ESCENA * 2.0
        if r["alertadas"]:
            falsas += 1
            for c in r["alertadas"]:
                clases_falsas[config.NOMBRES_CLASES[c]] = (
                    clases_falsas.get(config.NOMBRES_CLASES[c], 0) + 1)

    return {
        "escenas_incidente": len(incidentes),
        "escenas_control": len(control),
        "recall_por_clase": {
            config.NOMBRES_CLASES[c]: {
                "fotograma(>=1 frame)": (
                    round(por_clase_percibido[c][0] / por_clase_percibido[c][1], 3)
                    if por_clase_percibido[c][1] else None),
                "incidente(agente, K frames)": (
                    round(por_clase_alertado[c][0] / por_clase_alertado[c][1], 3)
                    if por_clase_alertado[c][1] else None),
                "n_escenas_gt": por_clase_alertado[c][1],
            } for c in config.CLASES_INCUMPLIMIENTO
        },
        "recall_escena_cualquier_no": (
            round(escenas_con_alerta_correcta / len(incidentes), 3)
            if incidentes else None),
        "falsas_alarmas_control": {
            "escenas_con_alerta": falsas,
            "tasa": round(falsas / len(control), 3) if control else None,
            "por_clase": clases_falsas,
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Demo del agente SafeSite sobre escenas del dataset")
    parser.add_argument("--modelo", default=None,
                        help="ruta al checkpoint (default: config.RUTA_MODELO)")
    parser.add_argument("--device", default=None,
                        help="'cpu' | '0' (GPU) (default: config.DEVICE_DEFECTO)")
    args = parser.parse_args()

    ruta_modelo = args.modelo or config.RUTA_MODELO
    device = args.device or config.DEVICE_DEFECTO
    if not os.path.exists(os.path.join(BASE, ruta_modelo)):
        sys.exit(f"No existe el checkpoint: {ruta_modelo}. "
                 f"Entrena primero (Fase 1).")

    tag = _tag_del_modelo(ruta_modelo) if args.modelo else ""
    salida = os.path.join(
        BASE, "eda", "salidas",
        f"resumen_fase3_demo_{tag}.json" if tag else "resumen_fase3_demo.json")
    print(f"Modelo: {ruta_modelo} | device: {device} | salida: {salida}")

    agente = SafeSiteAgent(ruta_modelo=ruta_modelo, device=device)
    por_split = {}
    for split in ("train", "val", "test"):
        antes = agente.alertas_emitidas
        por_split[split] = evaluar_split(agente, split)
        por_split[split]["alertas_emitidas"] = (agente.alertas_emitidas - antes)

    resumen = {
        "config": {
            "modelo": ruta_modelo,
            "device": device,
            "umbral_incumplimiento": config.UMBRAL_INCUMPLIMIENTO,
            "k_frames_confirmacion": config.K_FRAMES_CONFIRMACION,
            "cooldown_s": config.COOLDOWN_S,
            "frames_por_escena": FRAMES_POR_ESCENA,
        },
        "nota_metodologica": "train inflado por memorizacion; el recall "
                             "creible es val/test. Simulacion = 4 frames "
                             "identicos por escena a 2 FPS; en video real el "
                             "recall de incidente tiende a ser mayor.",
        "por_split": por_split,
        "ejecucion": agente.resumen_ejecucion(),
    }
    with open(salida, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    print(json.dumps(resumen, ensure_ascii=False, indent=2))
    print(f"\nResumen guardado en: {salida}")
    print(f"Historial de incidentes: {config.ARCHIVO_HISTORIAL}")


if __name__ == "__main__":
    main()
