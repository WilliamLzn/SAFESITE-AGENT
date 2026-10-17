"""SafeSite-Agent — Banco de pruebas EN VIVO: evaluacion por clase en webcam.

Mide, en el dominio REAL de la webcam del piloto (no en MOCS), que clases
detecta el modelo y que incidentes confirma el agente — el diagnostico
cuantitativo que motiva el fine-tune (BITACORA E35: gafas fallan en AMBAS
direcciones en webcam; chaleco sin clase `no_vest`).

Los frames vienen de `capturar_banco.py` (poses controladas por escenario).
La evaluacion replica el pipeline EXACTO del agente (percepcion ->
filtrado por clase con el perfil -> confirmacion temporal K=3), SIN
actuadores: nunca envia WhatsApp ni escribe alertas.

Uso (desde la raiz del repo):
  .venv\\Scripts\\python.exe -m src.safesite.banco_vivo --device 0
  .venv\\Scripts\\python.exe -m src.safesite.banco_vivo --device 0 --perfil ambos

Salidas:
  eda/salidas/banco_vivo_<fecha>.json   (reporte completo)
  eda/salidas/banco_vivo_<fecha>.md    (tabla legible)
"""
import argparse
import glob
import json
import os
import statistics
import sys
import time
from datetime import datetime

import cv2

from . import config
from .percepcion import Percepcion
from .razonamiento import Razonamiento

# --- Escenarios del banco (compartidos con capturar_banco.py) ---------------
# presentes  : clases positivas que DEBEN verse (id -> config.NOMBRES_CLASES)
# alertas    : clases `no_*` cuyo incidente DEBE confirmarse
# nota       : contexto del escenario
ESCENARIOS_BANCO = {
    "con_todo": {
        "descripcion": "Casco + gafas + chaleco + guantes puestos",
        "presentes": [0, 1, 2, 4],   # helmet, gloves, vest, goggles
        "alertas": [],
    },
    "sin_casco": {
        "descripcion": "Sin casco; gafas + chaleco + guantes puestos",
        "presentes": [1, 2, 4],
        "alertas": [7],              # no_helmet
    },
    "sin_gafas": {
        "descripcion": "Sin gafas; casco + chaleco + guantes puestos",
        "presentes": [0, 1, 2],
        "alertas": [8],              # no_goggle
    },
    "sin_chaleco": {
        "descripcion": "Sin chaleco; casco + gafas + guantes puestos",
        "presentes": [0, 1, 4],
        "alertas": [],
        "nota": ("el dataset NO tiene clase no_vest: hoy este escenario NO "
                 "puede alertar; se registra que detecta para decidir la "
                 "solucion (clase 12 en el fine-tune o regla de inferencia)"),
    },
    "sin_guantes": {
        "descripcion": "Sin guantes; casco + gafas + chaleco puestos",
        "presentes": [0, 2, 4],
        "alertas": [9],              # no_gloves
    },
    "sin_epp": {
        "descripcion": "Sin casco ni gafas (ni chaleco ni guantes)",
        "presentes": [],
        "alertas": [7, 8],           # verificable en encuadre webcam
    },
    "vacio": {
        "descripcion": "Escena sin personas (control de falsas alarmas)",
        "presentes": [],
        "alertas": [],
    },
}

PERFILES = {
    "evaluacion": {"umbrales": None, "coherencia": None},
    "vivo": {"umbrales": config.UMBRALES_INCUMPLIMIENTO_VIVO,
             "coherencia": config.REGLA_COHERENCIA_VIVO},
}


def _estadistica_conf(confs):
    """Mediana / p25 / p75 de las confianzas de una clase en un escenario."""
    if not confs:
        return None
    confs = sorted(confs)
    p25 = confs[int(0.25 * (len(confs) - 1))]
    p75 = confs[int(0.75 * (len(confs) - 1))]
    return {"mediana": round(statistics.median(confs), 3),
            "p25": round(p25, 3), "p75": round(p75, 3),
            "max": round(confs[-1], 3), "n_detecciones": len(confs)}


def evaluar_carpeta(carpetas, percepcion, perfil, fps_simulado):
    """Evalua una pasada de un perfil sobre los escenarios capturados.

    Replica el ciclo del agente SIN actuadores: detectar -> filtrar_por_clase
    -> evaluar (rachas K=3). Un escenario confirma su clase esperada si
    alguna racha alcanza K frames.
    """
    resultado = {}
    for escenario, rutas in carpetas.items():
        def_ = ESCENARIOS_BANCO.get(escenario)
        razonamiento = Razonamiento(umbrales_incumplimiento=perfil["umbrales"],
                                    coherencia=perfil["coherencia"])
        # estado crudo del modelo (antes de umbrales/confirmacion temporal)
        conf_por_clase = {}       # cls_id -> [conf...]
        frames_con_clase = {}     # cls_id -> n frames (conf >= umbral inferencia)
        frames_presente_ok = {}   # cls_id -> n frames (conf >= UMBRAL_DEFECTO)
        confirmados = {}          # cls_id -> info de la primera confirmacion
        latencias = []
        t = time.time()
        for i, ruta in enumerate(rutas):
            frame = cv2.imread(ruta)
            if frame is None:
                continue
            t0 = time.perf_counter()
            dets = percepcion.detectar(frame)
            latencias.append((time.perf_counter() - t0) * 1000)
            t += 1.0 / fps_simulado
            for d in dets:
                conf_por_clase.setdefault(d.cls_id, []).append(d.conf)
                if d.conf >= percepcion.conf:
                    frames_con_clase[d.cls_id] = frames_con_clase.get(d.cls_id, 0) + 1
                if d.cls_id != 6 and d.conf >= config.UMBRAL_DEFECTO:
                    frames_presente_ok[d.cls_id] = \
                        frames_presente_ok.get(d.cls_id, 0) + 1
            filtradas = razonamiento.filtrar_por_clase(dets)
            incidentes = razonamiento.evaluar(escenario, t, filtradas,
                                              origen=os.path.basename(ruta))
            for inc in incidentes:
                # razonamiento emite UNA vez por racha: registrar la primera
                if inc.clase_id not in confirmados:
                    confirmados[inc.clase_id] = {
                        "conf_media": round(inc.conf_media, 3),
                        "frame_confirmacion": i,
                    }
        n = len(latencias)
        esc = {
            "n_frames": n,
            "deteccion_cruda_por_clase": {
                config.NOMBRES_CLASES[c]: {
                    "tasa_frames": round(frames_con_clase.get(c, 0) / n, 3)
                    if n else 0.0,
                    "conf": _estadistica_conf(conf_por_clase.get(c, [])),
                } for c in sorted(conf_por_clase)
            },
            "presentes_esperados": {
                config.NOMBRES_CLASES[c]: {
                    "detectado_en": frames_presente_ok.get(c, 0),
                    "tasa_frames": round(frames_presente_ok.get(c, 0) / n, 3)
                    if n else 0.0,
                } for c in def_["presentes"]
            } if def_ else {},
            "incidentes_confirmados": {
                config.NOMBRES_CLASES[c]: confirmados[c]
                for c in sorted(confirmados)
            },
        }
        if def_:
            faltantes = [config.NOMBRES_CLASES[c] for c in def_["alertas"]
                         if c not in confirmados]
            inesperados = [config.NOMBRES_CLASES[c] for c in confirmados
                           if c not in def_["alertas"]]
            esc["esperado"] = {
                "alertas_esperadas": [config.NOMBRES_CLASES[c]
                                      for c in def_["alertas"]],
                "alertas_faltantes": faltantes,
                "alertas_inesperadas_FP": inesperados,
                "recall_incidente": round(
                    1 - len(faltantes) / len(def_["alertas"]), 3)
                    if def_["alertas"] else None,
            }
            if def_.get("nota"):
                esc["nota"] = def_["nota"]
        esc["latencia_media_ms"] = round(sum(latencias) / n, 1) if n else 0.0
        resultado[escenario] = esc
    return resultado


def tabla_markdown(reporte):
    """Tabla resumen legible del reporte del banco."""
    lineas = ["# Banco de pruebas en vivo (webcam)", "",
              f"fecha: {reporte['fecha']} · modelo: `{reporte['config']['modelo']}`", ""]
    for perfil, escenarios in reporte["por_perfil"].items():
        lineas += [f"## Perfil {perfil}", "",
                   "| Escenario | Frames | Alertas esperadas | Confirmadas "
                   "| Faltantes (no avisó) | Inesperadas (FP) |",
                   "|---|---|---|---|---|---|"]
        for esc, r in escenarios.items():
            esp = r.get("esperado", {})
            lineas.append(
                f"| {esc} | {r['n_frames']} "
                f"| {', '.join(esp.get('alertas_esperadas', [])) or '—'} "
                f"| {', '.join(r['incidentes_confirmados']) or '—'} "
                f"| {', '.join(esp.get('alertas_faltantes', [])) or '—'} "
                f"| {', '.join(esp.get('alertas_inesperadas_FP', [])) or '—'} |")
        lineas += ["", "### Positivos esperados (detección ≥ "
                   f"{config.UMBRAL_DEFECTO})", "",
                   "| Escenario | Clase | Frames con detección |", "|---|---|---|"]
        for esc, r in escenarios.items():
            for clase, d in r.get("presentes_esperados", {}).items():
                lineas.append(f"| {esc} | {clase} | {d['detectado_en']}"
                              f"/{r['n_frames']} ({d['tasa_frames']:.0%}) |")
        lineas.append("")
    return "\n".join(lineas)


def main():
    # consolas Windows en cp1252 no pueden con los emojis del log
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description="Banco de pruebas en vivo: evaluación por clase sobre "
                    "capturas de webcam (ver capturar_banco.py).")
    parser.add_argument("--modelo", default=None,
                        help="checkpoint a evaluar (default: config.RUTA_MODELO)")
    parser.add_argument("--device", default=None,
                        help="cpu | 0 | cuda:0 (default: config)")
    parser.add_argument("--carpeta",
                        default=r"runs\agente\banco_vivo\capturas",
                        help="raíz con un subdirectorio por escenario")
    parser.add_argument("--perfil", choices=["vivo", "evaluacion", "ambos"],
                        default="ambos",
                        help="perfil de umbrales a evaluar (default: ambos)")
    parser.add_argument("--fps-simulado", type=float, default=2.0,
                        help="fps de la línea temporal simulada (default 2)")
    parser.add_argument("--conf", type=float, default=None,
                        help="umbral de inferencia crudo (default: "
                             "config.UMBRAL_INCUMPLIMIENTO)")
    args = parser.parse_args()

    if not os.path.isdir(args.carpeta):
        raise SystemExit(f"❌ no existe {args.carpeta} — captura primero con "
                         f"`python -m src.safesite.capturar_banco`")

    # descubrir escenarios: un subdirectorio por escenario con >=K frames
    carpetas = {}
    for nombre in sorted(os.listdir(args.carpeta)):
        ruta_esc = os.path.join(args.carpeta, nombre)
        if not os.path.isdir(ruta_esc):
            continue
        if nombre not in ESCENARIOS_BANCO:
            print(f"⚠️ {nombre}: no es un escenario del banco — ignorado")
            continue
        jpgs = sorted(glob.glob(os.path.join(ruta_esc, "*.jpg")))
        if len(jpgs) < config.K_FRAMES_CONFIRMACION:
            print(f"⚠️ {nombre}: {len(jpgs)} frames "
                  f"(< {config.K_FRAMES_CONFIRMACION}) — ignorado")
            continue
        carpetas[nombre] = jpgs
    if not carpetas:
        raise SystemExit("❌ ningún escenario con frames suficientes")
    total = sum(len(v) for v in carpetas.values())
    print(f"🎬 banco: {len(carpetas)} escenarios, {total} frames", flush=True)

    percepcion = Percepcion(ruta_modelo=args.modelo, device=args.device,
                            conf=args.conf)
    perfiles = (list(PERFILES) if args.perfil == "ambos" else [args.perfil])

    reporte = {
        "fecha": datetime.now().isoformat(timespec="seconds"),
        "config": {
            "modelo": percepcion.ruta_modelo,
            "device": percepcion.device,
            "conf_inferencia": percepcion.conf,
            "k_frames": config.K_FRAMES_CONFIRMACION,
            "fps_simulado": args.fps_simulado,
            "umbral_defecto_positivos": config.UMBRAL_DEFECTO,
            "umbral_global_evaluacion": config.UMBRAL_INCUMPLIMIENTO,
        },
        "por_perfil": {},
    }
    for nombre_perfil in perfiles:
        print(f"\n━ evaluando perfil {nombre_perfil.upper()} ...", flush=True)
        reporte["por_perfil"][nombre_perfil] = evaluar_carpeta(
            carpetas, percepcion, PERFILES[nombre_perfil], args.fps_simulado)
        for esc, r in reporte["por_perfil"][nombre_perfil].items():
            inc = ", ".join(r["incidentes_confirmados"]) or "—"
            print(f"  {esc:12s} frames={r['n_frames']:3d} "
                  f"incidentes=[{inc}] "
                  f"lat={r['latencia_media_ms']:.0f} ms", flush=True)

    # ---- salidas: JSON + tabla MD en eda/salidas/ ----
    fecha = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = os.path.join("eda", "salidas", f"banco_vivo_{fecha}")
    os.makedirs(os.path.dirname(base), exist_ok=True)
    with open(base + ".json", "w", encoding="utf-8") as f:
        json.dump(reporte, f, ensure_ascii=False, indent=2)
    tabla = tabla_markdown(reporte)
    with open(base + ".md", "w", encoding="utf-8") as f:
        f.write(tabla)
    print(f"\n✅ reporte: {base}.json y {base}.md", flush=True)
    print(tabla)


if __name__ == "__main__":
    main()
