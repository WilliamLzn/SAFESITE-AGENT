"""SafeSite-Agent — Suite de pruebas de la Fase 3 (medidas de desempeno).

Convierte cada medida de desempeno SMART (reformulada y documentada en
el documento de la entrega) en pruebas con resultado numerico:

  M1  Recall de incidente  = escenas con alerta correcta / escenas incidente
      Umbral PRE-REGISTRADO: >= 0.70 (a nivel de escena, cualquier clase
      `no_*`; se reporta tambien por clase).
  M2  Falsas alarmas        = escenas control con alerta / escenas control
      Umbral PRE-REGISTRADO: <= 0.10.
  M3  Tiempo de notificacion = t(confirmacion) - t(inicio de la racha)
      + latencia de procesamiento de los K frames
      Umbral (del diseno original, se mantiene): < 10 s.
  M4  Cooldown anti-spam   = alertas duplicadas emitidas dentro de la
      ventana de cooldown / alertas reincidentes esperadas
      Umbral PRE-REGISTRADO: = 0.

Diseno de la prueba (enunciado de la entrega):
  - >= 10 escenarios: normales, limite y de falla esperada (S1-S13);
  - 5 repeticiones por escenario (media y desviacion estandar), con
    estado interno reiniciado en cada repeticion (agente.reset());
  - log de ejecucion con marca de tiempo (percepcion -> decision ->
    accion por frame) en runs/agente/pruebas/log_ejecucion.jsonl;
  - tabla de resultados (CSV + JSON + Markdown) para el documento.

Ejecutar desde la RAIZ del proyecto:
    .venv\\Scripts\\python.exe -m src.safesite.pruebas_medidas --device 0
"""
import argparse
import csv
import json
import os
import statistics
import time
from datetime import datetime

import cv2
import numpy as np

from . import config
from .actuarios import ActuadorBase, ActuadorWhatsApp
from .agente import SafeSiteAgent
from .demo import cargar_escenas
from .percepcion import Percepcion

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIR_PRUEBAS = os.path.join(BASE, "runs", "agente", "pruebas")
FPS_SIM = 2.0                 # cadencia simulada de frames
INTERVALO = 1.0 / FPS_SIM
REPETICIONES = 5              # enunciado: minimo 5 ejecuciones por escenario
SEED = 42

# --- umbrales PRE-REGISTRADOS (fijados ANTES de ejecutar las pruebas) ---
UMBRAL_M1 = 0.70              # recall de incidente (escena)
UMBRAL_M2 = 0.10               # tasa de falsas alarmas
UMBRAL_M3_S = 10.0            # tiempo de notificacion, segundos
UMBRAL_M4 = 0                 # alertas duplicadas dentro del cooldown

# Evidencia real previa (BITACORA E24/E28, WhatsApp con credenciales reales):
#   envio HTTP de la alerta: media 1.9 s, max 2.5 s (resumen_fase4_whatsapp.json)
#   ciclo completo webcam -> alerta con foto en el telefono: ~2.6 s (E28).


class ActuadorRegistro(ActuadorBase):
    """Actuador de prueba: registra alertas con marca de tiempo, sin
    efectos externos (no envia WhatsApp ni escribe frames)."""

    nombre = "registro"

    def __init__(self):
        self.alertas = []          # lista de dicts (una por incidente)

    def alertar_lote(self, incidentes, frame_anotado=None, ruta_frame=None):
        t = time.time()
        for inc in incidentes:
            self.alertas.append({"t_registro": t, **inc.como_dict()})

    def alertar(self, incidente, frame_anotado=None, ruta_frame=None):
        self.alertar_lote([incidente], frame_anotado, ruta_frame)


class ActuadorHTTPCaido(ActuadorWhatsApp):
    """Simula WhatsApp Cloud API caida: toda llamada HTTP lanza
    ConnectionError. Verifica la DEGRADACION diseniada: la alerta nunca
    se pierde (queda en el historial) y el agente no se detiene."""

    def __init__(self):
        super().__init__()
        # forzar modo ENVIO-REAL para pasar por la ruta de degradacion
        self.token, self.phone_id, self.destinatario = "x", "y", "z"

    def _post(self, ruta, json=None, data=None, files=None):
        import requests
        raise requests.exceptions.ConnectionError("simulacion: API caida")


# ---------------------------------------------------------------------------
# utilidades de seleccion determinista de escenarios
# ---------------------------------------------------------------------------

def cargar_gt(ruta_jpg, split):
    lbl = os.path.join(BASE, "dataset_v2", "labels", split,
                       os.path.basename(ruta_jpg)[:-4] + ".txt")
    ids = set()
    if os.path.exists(lbl):
        with open(lbl, encoding="utf-8") as f:
            for ln in f:
                p = ln.split()
                if len(p) == 5:
                    ids.add(int(p[0]))
    return ids


def elegir_escena(split, predicado):
    """Primera escena incidente del split que cumpla el predicado."""
    incidentes, _ = cargar_escenas(split)
    for ruta, gt in incidentes:
        if predicado(ruta, gt):
            return ruta, gt
    return None


def escena_persona_lejana(split="test"):
    """Escena incidente con la persona mas pequena del split."""
    incidentes, _ = cargar_escenas(split)
    mejor, mejor_h = None, 1e9
    for ruta, gt in incidentes:
        lbl = os.path.join(BASE, "dataset_v2", "labels", split,
                           os.path.basename(ruta)[:-4] + ".txt")
        for ln in open(lbl, encoding="utf-8"):
            p = ln.split()
            if len(p) == 5 and int(p[0]) == 6:
                if float(p[4]) < mejor_h:
                    mejor_h, mejor = float(p[4]), (ruta, gt)
    return mejor


def imagen_control_sin_personas(split="test"):
    """Escena control sin ninguna etiqueta Person en el GT."""
    _, control = cargar_escenas(split)
    for ruta, _ in control:
        if not cargar_gt(ruta, split) & {6}:
            return ruta
    return None


def frame_de(ruta):
    img = cv2.imread(ruta)
    if img is None:
        raise RuntimeError(f"no se pudo leer {ruta}")
    return img


# ---------------------------------------------------------------------------
# log de ejecucion (enunciado Fase 2: percepciones, decisiones, acciones)
# ---------------------------------------------------------------------------

class LogEjecucion:
    def __init__(self, ruta):
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        self.fh = open(ruta, "a", encoding="utf-8")

    def registrar(self, **campos):
        campos["t_wall"] = time.time()
        campos["hora_local"] = datetime.now().isoformat(timespec="milliseconds")
        self.fh.write(json.dumps(campos, ensure_ascii=False) + "\n")
        self.fh.flush()


# ---------------------------------------------------------------------------
# Parte A — M1 (recall de incidente) y M2 (falsas alarmas), val + test
# ---------------------------------------------------------------------------

def evaluar_split_log(agente, split, log, parte, rep):
    """Evalua todas las escenas de un split (incidente + control) con log
    por escena. Misma logica que demo.evaluar_split, con registro."""
    incidentes, control = cargar_escenas(split)
    por_clase = {c: [0, 0] for c in config.CLASES_INCUMPLIMIENTO}
    escenas_ok = 0
    t0 = 0.0
    for idx, (ruta, gt) in enumerate(incidentes):
        frame = frame_de(ruta)
        zona = f"{split}_{idx:04d}"
        r = _simular(agente, frame, zona, t0, gt, log, parte, rep, split, ruta)
        acierto = False
        for c in gt:
            por_clase[c][1] += 1
            if c in r["percibidas"]:
                por_clase[c][0] += 1
            if c in r["alertadas"]:
                acierto = True
        escenas_ok += int(acierto)
        t0 += 4 * INTERVALO
    falsas, clases_falsas = 0, {}
    for j, (ruta, _) in enumerate(control):
        frame = frame_de(ruta)
        zona = f"{split}_ctrl_{j:04d}"
        r = _simular(agente, frame, zona, t0, set(), log, parte, rep, split, ruta)
        if r["alertadas"]:
            falsas += 1
            for c in r["alertadas"]:
                clases_falsas[config.NOMBRES_CLASES[c]] = (
                    clases_falsas.get(config.NOMBRES_CLASES[c], 0) + 1)
        t0 += 4 * INTERVALO
    return {
        "recall_escena": round(escenas_ok / len(incidentes), 3) if incidentes else None,
        "n_incidentes": len(incidentes),
        "n_control": len(control),
        "falsas": falsas,
        "tasa_falsas": round(falsas / len(control), 3) if control else None,
        "clases_falsas": clases_falsas,
    }


def _simular(agente, frame, zona, t_inicial, gt, log, parte, rep, split, ruta):
    """4 frames de la escena por el agente, con registro por frame."""
    percibidas, alertadas = set(), set()
    for k in range(4):
        t = t_inicial + k * INTERVALO
        antes = agente.alertas_emitidas
        incidentes, filtradas = agente.procesar_frame(frame, zona=zona, t_stamp=t)
        for d in filtradas:
            if d.cls_id in config.CLASES_INCUMPLIMIENTO:
                percibidas.add(d.cls_id)
        for inc in incidentes:
            alertadas.add(inc.clase_id)
        log.registrar(
            parte=parte, rep=rep, split=split, zona=zona, frame_idx=k,
            origen=os.path.basename(ruta), gt=sorted(gt),
            percepcion={n: sum(1 for d in filtradas
                               if d.nombre == n)
                        for n in sorted({d.nombre for d in filtradas})},
            decision=[i.clase for i in incidentes],
            accion=(agente.alertas_emitidas - antes),
        )
    return {"percibidas": percibidas, "alertadas": alertadas}


# ---------------------------------------------------------------------------
# Parte B — escenarios S1-S13 (normales, limite, falla esperada)
# ---------------------------------------------------------------------------

def construir_escenarios():
    """>=10 escenarios: normales, limite y de falla esperada (enunciado)."""
    s2 = elegir_escena("test", lambda r, gt: 7 in gt)
    s3 = elegir_escena("test", lambda r, gt: 9 in gt and 7 not in gt)
    s4 = elegir_escena("test", lambda r, gt: len(gt) >= 2)
    s1 = None
    _, control = cargar_escenas("test")
    for ruta, _ in control:
        g = cargar_gt(ruta, "test")
        if {0, 2} <= g:              # casco + chaleco visibles
            s1 = ruta
            break
    s5 = escena_persona_lejana("test")
    s8_img = imagen_control_sin_personas("test")
    s8_spec = (dict(tipo="imagen", ruta=s8_img, frames=4, alerta_esperada=False)
               if s8_img else
               dict(tipo="sintetico", sintetico="ruido", frames=4,
                    alerta_esperada=False))
    return [
        ("S1", "normal", "Trabajador con EPP visible (casco+chaleco): sin alertas",
         dict(tipo="imagen", ruta=s1, frames=4, alerta_esperada=False)),
        ("S2", "normal", "Trabajador sin casco (solo no_helmet): alerta unica",
         dict(tipo="imagen", ruta=(s2[0] if s2 else None), frames=4,
              alerta_esperada=True, clases={7})),
        ("S3", "normal", "Trabajador sin guantes (escena con varias faltas): "
         "alerta por cada clase no_* confirmada",
         dict(tipo="imagen", ruta=(s3[0] if s3 else None), frames=4,
              alerta_esperada=True, clases={9})),
        ("S4", "limite", "Incumplimientos multiples en la misma escena: lote",
         dict(tipo="imagen", ruta=(s4[0] if s4 else None), frames=4,
              alerta_esperada=True, min_clases=2)),
        ("S5", "limite", "Persona lejana/pequena en escena incidente",
         dict(tipo="imagen", ruta=(s5[0] if s5 else None), frames=4,
              alerta_esperada=None)),
        ("S6", "limite", "Reincidencia dentro del cooldown (30 s): 1 sola alerta",
         dict(tipo="cooldown", ruta=(s2[0] if s2 else None),
              patron="reincidente-bloqueado", alertas_totales=1)),
        ("S7", "limite", "Reincidencia despues del cooldown: 2 alertas",
         dict(tipo="cooldown", ruta=(s2[0] if s2 else None),
              patron="reincidente-permitido", alertas_totales=2)),
        ("S8", "normal", "Escena sin personas: sin alertas", s8_spec),
        ("S9", "limite", "Frame negro (sensor sin senal): sin alertas ni error",
         dict(tipo="sintetico", sintetico="negro", frames=4,
              alerta_esperada=False)),
        ("S10", "falla", "Sensor sin dato (frame None): registrado, sin crash",
         dict(tipo="sintetico", sintetico="none", frames=4,
              alerta_esperada=False, fallos_esperados=4)),
        ("S11", "falla", "Entrada invalida (frame 1 canal): sin crash",
         dict(tipo="sintetico", sintetico="gris", frames=4,
              alerta_esperada=False, fallos_esperados=4)),
        ("S12", "falla", "WhatsApp Cloud API caida: degradacion, alerta persistida",
         dict(tipo="whatsapp_caido", ruta=(s2[0] if s2 else None), frames=4,
              alerta_esperada=True, clases={7})),
        ("S13", "falla", "Checkpoint inexistente: fallo de arranque controlado",
         dict(tipo="modelo_inexistente")),
    ]


def correr_escenario(agente, sid, spec, log, rep, actuario):
    """Ejecuta un escenario una vez; devuelve dict de resultados."""
    res = {"escenario": sid, "rep": rep, "excepcion": None}
    t_alerta_s = None
    try:
        if spec["tipo"] == "modelo_inexistente":
            try:
                Percepcion(ruta_modelo=os.path.join(
                    BASE, "runs", "safesite", "no_existe", "weights", "best.pt"))
                res["arranque_fallo"] = False      # no deberia llegar aqui
            except Exception as e:
                res["arranque_fallo"] = True
                res["mensaje_error"] = f"{type(e).__name__}"
            return res

        if spec["tipo"] == "sintetico":
            if spec["sintetico"] == "negro":
                frame = np.zeros((480, 640, 3), dtype=np.uint8)
            elif spec["sintetico"] == "ruido":
                rng = np.random.RandomState(SEED)
                frame = rng.randint(0, 256, (480, 640, 3), dtype=np.uint8)
            elif spec["sintetico"] == "gris":
                frame = np.zeros((480, 640), dtype=np.uint8)   # 1 canal
            else:
                frame = None
            fallos_antes = agente.frames_fallidos
            for k in range(spec["frames"]):
                incidentes, filtradas = agente.procesar_frame(
                    frame, zona=sid, t_stamp=100.0 + k * INTERVALO)
                _log_frame(log, "B", rep, sid, k, filtradas, incidentes, agente)
            res.update(alertas=len(actuario.alertas),
                       fallos_percepcion=agente.frames_fallidos - fallos_antes)
            return res

        if spec["tipo"] == "whatsapp_caido":
            frame = frame_de(spec["ruta"])
            actuario_caido = ActuadorHTTPCaido()
            agente.actuadores = [actuario_caido]
            n_historial_antes = len(agente.memoria.historial)
            for k in range(spec["frames"]):
                incidentes, filtradas = agente.procesar_frame(
                    frame, zona=sid, t_stamp=100.0 + k * INTERVALO)
                _log_frame(log, "B", rep, sid, k, filtradas, incidentes, agente)
            agente.actuadores = [actuario]
            # la alerta NO se perdio: quedo persistida en el historial del
            # agente aunque el canal externo estuviera caido
            n_historial = len(agente.memoria.historial)
            persistidas = n_historial - n_historial_antes
            res.update(alertas=persistidas,          # metrica principal
                       alertas_historial=persistidas,
                       excepcion_actuador=False)
            return res

        if spec["tipo"] == "cooldown":
            frame_inc = frame_de(spec["ruta"])
            _, control = cargar_escenas("test")
            frame_ctrl = frame_de(control[0][0]) if control else np.zeros(
                (480, 640, 3), np.uint8)
            fallos_seq = []
            if spec["patron"] == "reincidente-bloqueado":
                # racha 1 (t=0..1.0) -> alerta; pausa; racha 2 dentro de 30 s
                fallos_seq = [(0, frame_inc), (1, frame_inc), (2, frame_inc),
                              (3, frame_ctrl), (4, frame_ctrl),
                              (5, frame_inc), (6, frame_inc), (7, frame_inc)]
                t0 = 100.0
            else:
                # racha 2 empieza pasados los 30 s de cooldown
                fallos_seq = [(0, frame_inc), (1, frame_inc), (2, frame_inc),
                              (3, frame_ctrl), (4, frame_ctrl),
                              (64, frame_inc), (65, frame_inc), (66, frame_inc)]
                t0 = 100.0
            for k, (paso, frame) in enumerate(fallos_seq):
                incidentes, filtradas = agente.procesar_frame(
                    frame, zona=sid, t_stamp=t0 + paso * INTERVALO)
                _log_frame(log, "B", rep, sid, k, filtradas, incidentes, agente)
                for inc in incidentes:
                    if t_alerta_s is None:
                        t_alerta_s = inc.t_confirmacion - inc.t_inicio_deteccion
            res.update(alertas=len(actuario.alertas),
                       t_alerta_sim_s=t_alerta_s,
                       bloqueadas=agente.alertas_bloqueadas_cooldown)
            return res

        # escenario de imagen normal (S1-S5, S8)
        frame = frame_de(spec["ruta"])
        for k in range(spec["frames"]):
            incidentes, filtradas = agente.procesar_frame(
                frame, zona=sid, t_stamp=100.0 + k * INTERVALO)
            _log_frame(log, "B", rep, sid, k, filtradas, incidentes, agente)
            for inc in incidentes:
                if t_alerta_s is None:
                    t_alerta_s = inc.t_confirmacion - inc.t_inicio_deteccion
        res.update(alertas=len(actuario.alertas),
                   clases_alertadas=sorted({a["clase"] for a in actuario.alertas}),
                   t_alerta_sim_s=t_alerta_s)
    except Exception as e:                        # pragma: no cover
        res["excepcion"] = f"{type(e).__name__}: {e}"
    return res


def _log_frame(log, parte, rep, sid, k, filtradas, incidentes, agente):
    antes = agente.alertas_emitidas
    log.registrar(
        parte=parte, rep=rep, escenario=sid, frame_idx=k,
        percepcion={n: sum(1 for d in filtradas if d.nombre == n)
                    for n in sorted({d.nombre for d in filtradas})},
        decision=[i.clase for i in incidentes],
        accion=agente.alertas_emitidas - antes,
        latencia_ms=round(agente.latencias_ms[-1], 1) if agente.latencias_ms else 0,
    )


# ---------------------------------------------------------------------------
# agregacion y reporte
# ---------------------------------------------------------------------------

def media_std(valores):
    """(media, desviacion) redondeados; None si no hay datos."""
    if not valores:
        return None, None
    if len(valores) == 1:
        return round(valores[0], 3), 0.0
    return (round(statistics.mean(valores), 3),
            round(statistics.stdev(valores), 3))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--device", default=None,
                        help="'cpu' | '0' (GPU). Default: config.DEVICE_DEFECTO")
    parser.add_argument("--repeticiones", type=int, default=REPETICIONES)
    args = parser.parse_args()
    device = args.device or config.DEVICE_DEFECTO

    os.makedirs(DIR_PRUEBAS, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    ruta_log = os.path.join(DIR_PRUEBAS, "log_ejecucion.jsonl")
    ruta_csv = os.path.join(DIR_PRUEBAS, f"resultados_{marca}.csv")
    ruta_json = os.path.join(DIR_PRUEBAS, f"resultados_{marca}.json")
    ruta_md = os.path.join(DIR_PRUEBAS, f"tabla_resultados_{marca}.md")
    log = LogEjecucion(ruta_log)

    print(f"Suite de pruebas Fase 3 | modelo: {config.RUTA_MODELO} | "
          f"device: {device} | reps: {args.repeticiones}", flush=True)
    agente = SafeSiteAgent(device=device, actuadores=[ActuadorRegistro()])
    actuario = agente.actuadores[0]

    # ---------------- Parte A: M1 + M2 (val + test, con repeticiones) ------
    parte_a = {}
    for split in ("val", "test"):
        recalls, falsas, por_rep = [], [], []
        for rep in range(1, args.repeticiones + 1):
            agente.reset()
            actuario.alertas.clear()
            r = evaluar_split_log(agente, split, log, "A", rep)
            recalls.append(r["recall_escena"])
            falsas.append(r["tasa_falsas"])
            por_rep.append(r)
        media_rec, std_rec = media_std(recalls)
        media_fa, std_fa = media_std(falsas)
        parte_a[split] = {
            "formula_M1": "escenas incidente con >=1 alerta / escenas incidente",
            "umbral_M1": UMBRAL_M1,
            "casos_M1": por_rep[0]["n_incidentes"],
            "recall_media": media_rec, "recall_std": std_rec,
            "cumple_M1": media_rec is not None and media_rec >= UMBRAL_M1,
            "formula_M2": "escenas control con alerta / escenas control",
            "umbral_M2": UMBRAL_M2,
            "casos_M2": por_rep[0]["n_control"],
            "falsas_media": media_fa, "falsas_std": std_fa,
            "cumple_M2": media_fa is not None and media_fa <= UMBRAL_M2,
        }
        print(f"[A] {split}: recall={media_rec}±{std_rec} "
              f"(umbral>={UMBRAL_M1}) | falsas={media_fa}±{std_fa} "
              f"(umbral<={UMBRAL_M2})", flush=True)

    # ---------------- Parte B: escenarios S1-S13 --------------------------
    escenarios = construir_escenarios()
    filas_csv, resultados_b = [], []
    for sid, tipo, desc, spec in escenarios:
        if spec.get("ruta") is None and spec["tipo"] in ("imagen", "cooldown",
                                                         "whatsapp_caido"):
            print(f"[B] {sid}: SIN escena disponible en el split — omitido",
                  flush=True)
            continue
        por_rep = []
        for rep in range(1, args.repeticiones + 1):
            agente.reset()
            actuario.alertas.clear()
            agente.actuadores = [actuario]
            r = correr_escenario(agente, sid, spec, log, rep, actuario)
            r["tipo"] = tipo
            r["descripcion"] = desc
            r["latencia_media_ms"] = round(agente.latencia_media_ms, 1)
            por_rep.append(r)
            filas_csv.append({"escenario": sid, "tipo": tipo, "rep": rep,
                              "alertas": r.get("alertas"),
                              "t_alerta_sim_s": r.get("t_alerta_sim_s"),
                              "latencia_ms": r.get("latencia_media_ms"),
                              "fallos": r.get("fallos_percepcion"),
                              "excepcion": r.get("excepcion")})
        alertas = [r.get("alertas") for r in por_rep]
        t_alertas = [r.get("t_alerta_sim_s") for r in por_rep if r.get("t_alerta_sim_s") is not None]
        media_al, std_al = media_std([a for a in alertas if a is not None])
        media_t, std_t = media_std(t_alertas)
        resultados_b.append({
            "escenario": sid, "tipo": tipo, "descripcion": desc,
            "alertas_media": media_al, "alertas_std": std_al,
            "t_alerta_sim_media_s": media_t, "t_alerta_sim_std_s": std_t,
            "excepciones": [r.get("excepcion") for r in por_rep
                            if r.get("excepcion")],
            "detalle_ultima_rep": por_rep[-1],
        })
        print(f"[B] {sid} ({tipo}): alertas={media_al}±{std_al} "
              f"t_alerta={media_t}±{std_t} excepciones="
              f"{sum(1 for r in por_rep if r.get('excepcion'))}", flush=True)

    # ---------------- veredictos M3/M4 -------------------------------------
    # M3: tiempo de notificacion (sim + latencia de los K frames + envio)
    t_alerta_todos = [r["t_alerta_sim_media_s"] for r in resultados_b
                      if r["t_alerta_sim_media_s"] is not None]
    lats = [f["latencia_ms"] for f in filas_csv if f["latencia_ms"]]
    latencia_media = round(statistics.mean(lats), 1) if lats else None
    # latencia por frame medida en la Parte B; envio real WhatsApp (E24):
    envio_whatsapp_s = 1.9
    media_t, std_t = media_std(t_alerta_todos)
    t_total = (media_t + config.K_FRAMES_CONFIRMACION * (latencia_media or 0) / 1000.0
               + envio_whatsapp_s) if media_t is not None else None
    s6 = next((r for r in resultados_b if r["escenario"] == "S6"), None)
    s7 = next((r for r in resultados_b if r["escenario"] == "S7"), None)
    m4_ok = bool(s6 and s7
                 and s6["alertas_media"] == 1 and s7["alertas_media"] == 2)

    resumen = {
        "suite": "Fase 3 — pruebas contra medidas de desempeno (enunciado)",
        "fecha": marca,
        "config": {
            "modelo": config.RUTA_MODELO, "device": device,
            "k_frames": config.K_FRAMES_CONFIRMACION,
            "cooldown_s": config.COOLDOWN_S,
            "umbral_incumplimiento": config.UMBRAL_INCUMPLIMIENTO,
            "repeticiones": args.repeticiones, "seed": SEED,
            "fps_simulado": FPS_SIM,
        },
        "M1_recall_incidente": parte_a,
        "M2_falsas_alarmas": {s: {
            "media": parte_a[s]["falsas_media"], "std": parte_a[s]["falsas_std"],
            "casos": parte_a[s]["casos_M2"]} for s in parte_a},
        "M3_tiempo_notificacion": {
            "formula": "t(confirmacion) - t(inicio racha) + K*latencia_frame "
                       "+ envio WhatsApp (medido E24)",
            "umbral_s": UMBRAL_M3_S,
            "t_sim_media_s": media_t, "t_sim_std_s": std_t,
            "latencia_frame_ms": latencia_media,
            "envio_whatsapp_s": envio_whatsapp_s,
            "t_total_estimado_s": round(t_total, 2) if t_total else None,
            "cumple": t_total is not None and t_total < UMBRAL_M3_S,
        },
        "M4_cooldown": {
            "formula": "alertas duplicadas dentro del cooldown / reincidentes",
            "umbral": UMBRAL_M4,
            "S6_alertas": s6["alertas_media"] if s6 else None,
            "S7_alertas": s7["alertas_media"] if s7 else None,
            "cumple": m4_ok,
        },
        "escenarios": resultados_b,
        "evidencia": {
            "log_ejecucion": ruta_log,
            "csv": ruta_csv,
            "json": ruta_json,
            "historial_incidentes": config.ARCHIVO_HISTORIAL,
            "nota": "envio WhatsApp real (E24): media 1.9 s, max 2.5 s; "
                    "ciclo completo en vivo (E28): ~2.6 s por alerta",
        },
    }

    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump(resumen, f, ensure_ascii=False, indent=2)
    with open(ruta_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "escenario", "tipo", "rep", "alertas", "t_alerta_sim_s",
            "latencia_ms", "fallos", "excepcion"])
        w.writeheader()
        w.writerows(filas_csv)

    # tabla Markdown lista para pegar en el documento de la entrega
    filas_md = []
    for split in ("val", "test"):
        a = parte_a[split]
        filas_md.append(
            f"| M1 Recall de incidente ({split}) | escenas con alerta / escenas "
            f"incidente | ≥ {UMBRAL_M1} | {a['casos_M1']} escenas × "
            f"{args.repeticiones} reps | {a['recall_media']} ± {a['recall_std']} "
            f"| {'✅' if a['cumple_M1'] else '❌'} | `log_ejecucion.jsonl`, "
            f"`resultados_{marca}.csv` |")
        filas_md.append(
            f"| M2 Falsas alarmas ({split}) | escenas control con alerta / "
            f"escenas control | ≤ {UMBRAL_M2} | {a['casos_M2']} escenas × "
            f"{args.repeticiones} reps | {a['falsas_media']} ± {a['falsas_std']} "
            f"| {'✅' if a['cumple_M2'] else '❌'} | `log_ejecucion.jsonl` |")
    filas_md.append(
        f"| M3 Tiempo de notificación | t(confirmación) − t(inicio racha) + "
        f"K×latencia + envío WhatsApp | < {UMBRAL_M3_S} s | "
        f"{len(t_alerta_todos)} escenarios con alerta × {args.repeticiones} reps "
        f"| {round(t_total, 2) if t_total else '—'} s (media {media_t} ± {std_t} s "
        f"sim) | {'✅' if resumen['M3_tiempo_notificacion']['cumple'] else '❌'} "
        f"| `resultados_{marca}.csv`; en vivo E28: ~2.6 s |")
    filas_md.append(
        f"| M4 Cooldown anti-spam | duplicadas dentro de la ventana / "
        f"reincidentes | = {UMBRAL_M4} | S6 + S7 × {args.repeticiones} reps | "
        f"S6={s6['alertas_media'] if s6 else '—'} alerta(s), "
        f"S7={s7['alertas_media'] if s7 else '—'} alerta(s) "
        f"| {'✅' if m4_ok else '❌'} | `log_ejecucion.jsonl` (S6/S7) |")
    tabla_md = (
        "# Tabla de resultados — Fase 3 (suite `src/safesite/pruebas_medidas.py`)\n\n"
        f"Modelo: `{config.RUTA_MODELO}` · device: `{device}` · "
        f"K={config.K_FRAMES_CONFIRMACION} · cooldown={config.COOLDOWN_S}s · "
        f"reps={args.repeticiones} · fecha: {marca}\n\n"
        "| Medida de desempeño | Fórmula | Umbral | Casos ejecutados | "
        "Resultado obtenido | ¿Cumple? | Evidencia |\n|---|---|---|---|---|---|---|\n"
        + "\n".join(filas_md) + "\n\n## Detalle por escenario\n\n"
        "| ID | Tipo | Descripción | Alertas (media±σ) | t_alerta s | "
        "Excepciones |\n|---|---|---|---|---|---|\n"
        + "\n".join(
            f"| {r['escenario']} | {r['tipo']} | {r['descripcion']} | "
            f"{r['alertas_media']} ± {r['alertas_std']} | "
            f"{r['t_alerta_sim_media_s']} | {len(r['excepciones'])} |"
            for r in resultados_b))
    with open(ruta_md, "w", encoding="utf-8") as f:
        f.write(tabla_md)

    print("\n" + tabla_md, flush=True)
    print(f"\nJSON : {ruta_json}\nCSV  : {ruta_csv}\nLOG  : {ruta_log}"
          f"\nMD   : {ruta_md}", flush=True)


if __name__ == "__main__":
    main()
