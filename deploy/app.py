"""SafeSite-Agent — página de demostración (Gradio, para Hugging Face Spaces).

La página ejecuta el agente de verdad, en el momento: no hay resultados
guardados ni capturas pregrabadas. Todo pasa por el mismo código del
repositorio (src/safesite).

Pestañas: demo en vivo (webcam, imágenes propias o fotos del set de test,
con simulación de fallas del sensor), la suite de pruebas corriendo en el
navegador, los resultados oficiales, el EDA con las métricas y las
instrucciones.

Detalles de despliegue que conviene conocer:
- En el Space nunca hay credenciales (el .env no se sube), así que el canal
  de WhatsApp solo construye el mensaje para mostrarlo.
- El repo del Space es un espejo de la raíz del proyecto, y por eso las
  rutas de src/safesite, dataset_v2 y runs funcionan sin tocar nada.

Para probarla local, desde la raíz del repo:
    .venv\\Scripts\\python.exe deploy\\app.py     -> http://localhost:7860
"""
import json
import os
import random
import sys
import threading
import time
import uuid
from datetime import datetime

# localizar la raíz del proyecto: sirve igual si se corre desde deploy/
# (repo local) que desde la raíz de un Space
AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = AQUI if os.path.isdir(os.path.join(AQUI, "src")) else os.path.dirname(AQUI)
sys.path.insert(0, RAIZ)
os.chdir(RAIZ)

import cv2  # noqa: E402
import numpy as np  # noqa: E402
import gradio as gr  # noqa: E402

from src.safesite import config  # noqa: E402
from src.safesite import pruebas_medidas as suite  # noqa: E402
from src.safesite.actuarios import ActuadorBase, ActuadorWhatsApp  # noqa: E402
from src.safesite.agente import SafeSiteAgent  # noqa: E402
from src.safesite.demo import cargar_escenas, clases_de_ruta  # noqa: E402
from src.safesite.percepcion import Percepcion  # noqa: E402


class ActuadorNulo(ActuadorBase):
    """Actuador que no hace nada, para que la demo no tenga efectos
    externos (ni siquiera en consola ni guardando frames).

    Ojo: pasar `actuadores=[]` no sirve para esto, porque el agente
    interpreta la lista vacía como "usa los de siempre" (consola y
    WhatsApp), y con credenciales en el .env el WhatsApp manda mensajes
    de verdad. El historial de incidentes no depende de esto y se
    registra igual."""

    nombre = "nulo"

    def alertar(self, incidente, frame_anotado=None, ruta_frame=None):
        return None

    def alertar_lote(self, incidentes, frame_anotado=None, ruta_frame=None):
        return None

DEVICE = os.environ.get("SAFESITE_DEVICE", "cpu")
FRAMES_POR_ESCENA = 4          # la suite simula la escena con 4 frames a 2 fps
INTERVALO_S = 0.5
CORRIDA_OFICIAL = "20261014_170459"   # la corrida que vale para la entrega
DIR_PRUEBAS_WEB = os.path.join("runs", "agente", "pruebas_web")

# el modelo se carga una sola vez por agente; el de la demo y el de la
# suite viven separados. Los locks son porque ultralytics no es thread-safe
# y Gradio atiende las sesiones en hilos.
_lock_demo = threading.Lock()
_lock_suite = threading.Lock()
_agente_demo = None
_agente_suite = None
_ww = ActuadorWhatsApp()   # solo para construir el payload y mostrarlo


def agente_demo():
    global _agente_demo
    if _agente_demo is None:
        _agente_demo = SafeSiteAgent(device=DEVICE, actuadores=[ActuadorNulo()])
    return _agente_demo


def agente_suite():
    global _agente_suite
    if _agente_suite is None:
        _agente_suite = SafeSiteAgent(device=DEVICE,
                                       actuadores=[suite.ActuadorRegistro()])
    return _agente_suite


def tag_modelo():
    return os.path.basename(os.path.dirname(os.path.dirname(config.RUTA_MODELO)))


# --- demo en vivo: percibir, decidir, actuar ---

def _procesar_burst(agente, frame, zona, n_frames=FRAMES_POR_ESCENA):
    """Pasa el mismo frame varias veces seguidas, como video corto (igual
    que hace demo.simular_escena con las escenas del dataset)."""
    t0 = time.time()
    pasos = []
    for k in range(n_frames):
        incidentes, filtradas = agente.procesar_frame(
            frame, zona=zona, t_stamp=t0 + k * INTERVALO_S)
        pasos.append((filtradas, incidentes))
    return pasos


def _linea_tiempo(pasos, t_total_ms):
    """Texto del razonamiento temporal frame a frame (racha -> confirmacion)."""
    lineas, rachas = [], {}
    for k, (filtradas, incidentes) in enumerate(pasos, start=1):
        presentes = sorted({d.cls_id for d in filtradas
                            if d.cls_id in config.CLASES_INCUMPLIMIENTO})
        confirmadas = {i.clase_id for i in incidentes}
        frag = []
        for c in list(rachas):
            if c not in presentes:
                del rachas[c]
        for c in presentes:
            confs = [d.conf for d in filtradas if d.cls_id == c]
            rachas[c] = rachas.get(c, 0) + 1
            if c in confirmadas:
                frag.append(f"**{config.NOMBRES_ES[c]} confirmado** "
                            f"(confianza {max(confs):.2f}): se alerta al "
                            f"supervisor")
            elif rachas[c] < config.K_FRAMES_CONFIRMACION:
                frag.append(f"{config.NOMBRES_ES[c]} visto "
                            f"(confianza {max(confs):.2f}), "
                            f"racha {rachas[c]} de "
                            f"{config.K_FRAMES_CONFIRMACION}")
            else:
                frag.append(f"{config.NOMBRES_ES[c]} sigue presente, pero ya "
                            f"se alertó (pasa el cooldown de "
                            f"{config.COOLDOWN_S:.0f} s)")
        cuerpo = " · ".join(frag) if frag else "no se ve ningún incumplimiento"
        lineas.append(f"| {k} | t+{(k - 1) * INTERVALO_S:.1f} s | {cuerpo} |")
    cab = ("| Frame | Tiempo | Qué decide el agente |\n|---|---|---|\n")
    pie = (f"\nEl detector tardó unos {t_total_ms / len(pasos):.0f} ms por "
           f"frame. Las reglas: confirmar tras {config.K_FRAMES_CONFIRMACION} "
           f"frames seguidos y no repetir la misma alerta antes de "
           f"{config.COOLDOWN_S:.0f} s.")
    return cab + "\n".join(lineas) + pie


def _tabla_detecciones(filtradas):
    filas = []
    for d in sorted(filtradas, key=lambda x: -x.conf):
        if d.cls_id == 5:      # 'none': no se dibuja ni reporta (ruido)
            continue
        tipo = ("⚠️ Incumplimiento" if d.cls_id in config.CLASES_INCUMPLIMIENTO
                else "👤 Persona" if d.cls_id == 6 else "✅ EPP presente")
        filas.append([config.NOMBRES_ES[d.cls_id], f"{d.conf:.2f}", tipo])
    return filas


def _payload_md(incidentes):
    """Arma el mensaje tal como lo mandaría el canal de WhatsApp, solo para
    mostrarlo. El número del supervisor va enmascarado por si las moscas,
    aunque en un despliegue normal no habría credenciales."""
    if not incidentes:
        return ("**Mensaje al supervisor:** sin faltas confirmadas, no se "
                "envía nada.")
    caption = ActuadorWhatsApp._caption_lote(incidentes)
    plantilla = _ww.construir_payload(incidentes[0])
    para = str(plantilla.get("to", ""))
    if para and not para.startswith("<"):
        plantilla["to"] = para[:4] + "••••••" + para[-2:] \
            if len(para) > 8 else "••• (enmascarado)"
    return ("**Mensaje que recibiría el supervisor** (aquí solo se muestra, "
            "no se envía):\n\n"
            f"> {caption.replace(chr(10), chr(10) + '> ')}\n\n"
            "El mismo mensaje, como iría en la API de WhatsApp (plantilla de "
            "producción):\n\n"
            f"```json\n{json.dumps(plantilla, ensure_ascii=False, indent=2)}\n```")


def _log_linea(ses, texto):
    hora = datetime.now().strftime("%H:%M:%S")
    ses["log"].append(f"[{hora}] {texto}")
    if len(ses["log"]) > 200:
        ses["log"] = ses["log"][-200:]
    return "\n".join(ses["log"][-25:])


def verificar(img_rgb, zona, gt, ses):
    """Ciclo completo del agente sobre una imagen del navegador: se
    convierte a BGR, se procesa como video corto y se arma la respuesta
    (imagen anotada, decisión, mensaje y bitácora de la sesión)."""
    if ses is None or not isinstance(ses, dict):
        ses = {"verificaciones": 0, "alertas": 0, "frames_fallidos": 0,
               "log": []}
    if img_rgb is None:
        _log_linea(ses, "procesar sin imagen: se ignoró")
        return (None, "Todavía no hay imagen. Toma una foto con la webcam, "
                "sube un archivo o trae una del set de test.",
                [], _payload_md([]), _resumen_md(zona, ses),
                "\n".join(ses["log"][-25:]), ses)

    frame = cv2.cvtColor(np.asarray(img_rgb), cv2.COLOR_RGB2BGR)
    ag = agente_demo()
    fallidos_antes = ag.frames_fallidos
    with _lock_demo:
        t0 = time.perf_counter()
        pasos = _procesar_burst(ag, frame, zona)
        t_ms = (time.perf_counter() - t0) * 1000
    fallidos = ag.frames_fallidos - fallidos_antes

    incidentes_totales = [i for _, inc in pasos for i in inc]
    filtradas_ultimo = pasos[-1][0]
    anotado = Percepcion.anotar(frame, filtradas_ultimo)
    anotado_rgb = cv2.cvtColor(anotado, cv2.COLOR_BGR2RGB)

    ses["verificaciones"] += 1
    ses["alertas"] += len(incidentes_totales)
    ses["frames_fallidos"] += fallidos

    # veredicto contra el ground truth (solo fotos del set de test)
    veredicto = ""
    if gt:
        esperadas = {config.NOMBRES_CLASES[c] for c in gt["esperado_no"]}
        alertadas = {i.clase for i in incidentes_totales}
        if gt["tipo"] == "incidente":
            ok = bool(alertadas & esperadas)
            veredicto = (f"\n\nComparado con la etiqueta oficial: "
                         f"{'✅ acierta' if ok else '❌ falla'} — debía "
                         f"alertar {', '.join(sorted(esperadas)) or 'nada'} "
                         f"y alertó {', '.join(sorted(alertadas)) or 'nada'}.")
        else:
            if not alertadas:
                detalle = "✅ se comporta bien: sin faltas, no alerta nada"
            else:
                detalle = ("❌ falsa alarma: alertó "
                           + ", ".join(sorted(alertadas))
                           + " sin que hubiera falta etiquetada")
            veredicto = ("\n\nEsta escena es de control (sin faltas "
                         "etiquetadas): " + detalle + ".")

    titulo = ("### Detectó faltas: se prepara la alerta" if incidentes_totales
              else "### Sin faltas confirmadas")
    decisiones_md = (titulo + "\n\n" + _linea_tiempo(pasos, t_ms) + veredicto)

    origen = f" · foto test: `{gt['ruta']}`" if gt else ""
    _log_linea(ses, f"verificación {ses['verificaciones']} zona={zona}{origen} "
                    f"→ {len(incidentes_totales)} incidente(s): "
                    f"{', '.join(i.clase for i in incidentes_totales) or 'ninguno'}")

    return (anotado_rgb, decisiones_md, _tabla_detecciones(filtradas_ultimo),
            _payload_md(incidentes_totales), _resumen_md(zona, ses),
            "\n".join(ses["log"][-25:]), ses)


def _resumen_md(zona, ses):
    return (f"Sesión {zona}: {ses['verificaciones']} imágenes procesadas, "
            f"{ses['alertas']} alertas, {ses['frames_fallidos']} frames "
            f"fallidos. Modelo {tag_modelo()} en {DEVICE}.")


def foto_aleatoria(seed, ses):
    """Sortea una foto del set de test y muestra su etiqueta oficial, para
    saber si el agente acierta antes de procesarla. La semilla es de la
    sesión: la misma semilla da el mismo orden de fotos, cambiarla da
    otras fotos."""
    if ses is None or not isinstance(ses, dict):
        ses = {"verificaciones": 0, "alertas": 0, "frames_fallidos": 0,
               "log": [], "seed": 42, "sorteos": 0}
    try:
        seed = int(seed)
    except (TypeError, ValueError):
        seed = 42
    if seed != ses.get("seed"):
        ses["seed"] = seed
        ses["sorteos"] = 0
    ses["sorteos"] = ses.get("sorteos", 0) + 1
    rng = random.Random(f"{ses['seed']}-{ses['sorteos']}")
    incidentes, control = cargar_escenas("test")
    es_incidente = (rng.random()
                    < len(incidentes) / (len(incidentes) + len(control)))
    if es_incidente:
        ruta, gt_ids = rng.choice(incidentes)
        tipo = "incidente"
    else:
        ruta, _ = rng.choice(control)
        gt_ids = set()
        tipo = "control"
    lbl = os.path.join(RAIZ, "dataset_v2", "labels", "test",
                       os.path.basename(ruta)[:-4] + ".txt")
    todas = clases_de_ruta(lbl) if os.path.exists(lbl) else set()
    nombres = lambda ids: ", ".join(config.NOMBRES_ES.get(i, str(i)) for i in sorted(ids))

    gt = {"ruta": os.path.basename(ruta), "tipo": tipo,
          "esperado_no": sorted(gt_ids), "todas": sorted(todas)}
    seed_nota = (f"\n\nSemilla {ses['seed']}, sorteo {ses['sorteos']}: con "
                 f"la misma semilla salen las mismas fotos en el mismo "
                 f"orden; cámbiala para ver otras.")
    if tipo == "incidente":
        info = (f"Foto: `{gt['ruta']}`\n\n"
                f"La etiqueta oficial dice que en esta escena hay "
                f"{nombres(todas) or '—'}. Faltas que debería detectar: "
                f"**{nombres(gt_ids)}**. Procesa la imagen y compara."
                + seed_nota)
    else:
        info = (f"Foto: `{gt['ruta']}`\n\n"
                f"La etiqueta oficial dice que en esta escena hay "
                f"{nombres(todas) or '—'} y ninguna falta: el agente "
                f"debería quedarse callado." + seed_nota)
    log = _log_linea(ses, f"foto sorteada (semilla {ses['seed']}, "
                          f"n.{ses['sorteos']}): {gt['ruta']} (tipo {tipo})")
    return cv2.cvtColor(cv2.imread(ruta), cv2.COLOR_BGR2RGB), info, gt, log, ses


FALLAS = {
    "none": ("Frame None (sensor sin dato)", None),
    "negro": ("Frame negro (señal sin contenido)",
              np.zeros((480, 640, 3), dtype=np.uint8)),
    "gris": ("Frame de 1 canal (formato inválido)",
             np.full((480, 640), 128, dtype=np.uint8)),
}
ETIQUETA_A_CLAVE = {v[0]: k for k, v in FALLAS.items()}


def simular_falla(opcion, zona, ses):
    """Caso de falla del sensor: muestra lo que llegó y qué hizo el agente
    con cada frame, no solo un mensaje de texto."""
    if ses is None or not isinstance(ses, dict):
        ses = {"verificaciones": 0, "alertas": 0, "frames_fallidos": 0,
               "log": []}
    opcion = ETIQUETA_A_CLAVE.get(opcion, opcion)
    frame = FALLAS[opcion][1]
    ag = agente_demo()
    fallidos_antes = ag.frames_fallidos
    with _lock_demo:
        pasos = _procesar_burst(ag, frame, zona)

    # lo que el sensor entregó, para verlo además de leerlo
    if frame is None:
        canvas = np.zeros((480, 640, 3), dtype=np.uint8)
        titulo = "SIN DATO (frame None)"
    elif opcion == "negro":
        canvas = frame.copy()
        titulo = "frame negro"
    else:
        canvas = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
        titulo = "frame de 1 canal"
    cv2.putText(canvas, titulo, (40, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                (255, 255, 255), 2)
    cv2.putText(canvas, "lo que recibió el agente", (40, 265),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (170, 170, 170), 1)

    delta = ag.frames_fallidos - fallidos_antes
    ses["frames_fallidos"] += delta

    # reacción del agente, frame por frame
    que = ("percepción fallida registrada" if delta else "sin detecciones")
    filas = [f"| {k} | {que} |" for k in range(1, len(pasos) + 1)]
    tabla = ("| Frame | Qué hizo el agente |\n|---|---|\n" + "\n".join(filas))

    if opcion == "negro":
        md = ("### Señal sin contenido (frame negro)\n\n" + tabla +
              "\n\nUn frame negro sí es un frame válido: el agente lo mira, "
              "no encuentra nada y por eso no alerta. No cuenta como falla "
              "del sensor.")
    else:
        causa = ("el sensor no entregó datos (frame `None`)"
                 if opcion == "none" else
                 "la entrada no es una imagen a color válida (un solo canal)")
        md = (f"### Falla del sensor: {FALLAS[opcion][0]}\n\n" + tabla +
              f"\n\nLo que pasó: {causa}. El agente anotó {delta} frames "
              "fallidos y siguió trabajando normal: no se cayó y no "
              "inventó alertas.")
    log = _log_linea(ses, f"falla simulada ({FALLAS[opcion][0]}) -> "
                          f"frames fallidos +{delta}")
    return canvas, md, _resumen_md(zona, ses), log, ses


# --- pruebas en vivo: la suite del proyecto corriendo en el navegador ---

def _nueva_marca():
    os.makedirs(DIR_PRUEBAS_WEB, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    return marca, os.path.join(DIR_PRUEBAS_WEB, marca)


def correr_parte_b(repeticiones=5):
    """Corre los 13 escenarios de la suite con sus repeticiones, y va
    actualizando la tabla a medida que avanza (es un generador). Usa los
    escenarios y las funciones de pruebas_medidas.py tal cual."""
    agente = agente_suite()
    actuario = agente.actuadores[0]
    marca, dir_marca = _nueva_marca()
    log = suite.LogEjecucion(os.path.join(dir_marca, "log_ejecucion.jsonl"))
    escenarios = [e for e in suite.construir_escenarios()
                  if e[3].get("ruta") is not None
                  or e[3]["tipo"] in ("sintetico", "modelo_inexistente")]
    total = len(escenarios) * repeticiones
    filas_csv, resultados, hechos, estado = [], [], 0, ""

    for sid, tipo, desc, spec in escenarios:
        por_rep = []
        for rep in range(1, repeticiones + 1):
            agente.reset()
            actuario.alertas.clear()
            agente.actuadores = [actuario]
            r = suite.correr_escenario(agente, sid, spec, log, rep, actuario)
            r["tipo"], r["descripcion"] = tipo, desc
            r["latencia_media_ms"] = round(agente.latencia_media_ms, 1)
            por_rep.append(r)
            filas_csv.append({"escenario": sid, "tipo": tipo, "rep": rep,
                              "alertas": r.get("alertas"),
                              "t_alerta_sim_s": r.get("t_alerta_sim_s"),
                              "latencia_ms": r.get("latencia_media_ms"),
                              "fallos": r.get("fallos_percepcion"),
                              "excepcion": r.get("excepcion")})
            hechos += 1
            estado = (f"Corriendo {sid} ({tipo}), repetición {rep} de "
                      f"{repeticiones} — van {hechos} de {total} corridas")
            yield estado, _filas_b(resultados), "", None, None, None
        alertas = [r.get("alertas") for r in por_rep]
        ts = [r.get("t_alerta_sim_s") for r in por_rep if r.get("t_alerta_sim_s")]
        m_al, s_al = suite.media_std([a for a in alertas if a is not None])
        m_t, s_t = suite.media_std(ts)
        resultados.append({"escenario": sid, "tipo": tipo, "descripcion": desc,
                           "alertas_media": m_al, "alertas_std": s_al,
                           "t_alerta_sim_media_s": m_t, "t_alerta_sim_std_s": s_t,
                           "excepciones": sum(1 for r in por_rep
                                              if r.get("excepcion"))})

    # veredictos M3/M4 (misma agregacion que pruebas_medidas.main)
    ts_medios = [r["t_alerta_sim_media_s"] for r in resultados
                 if r["t_alerta_sim_media_s"] is not None]
    lats = [f["latencia_ms"] for f in filas_csv if f["latencia_ms"]]
    lat_media = round(sum(lats) / len(lats), 1) if lats else None
    m_t, s_t = suite.media_std(ts_medios)
    t_total = (m_t + config.K_FRAMES_CONFIRMACION * (lat_media or 0) / 1000.0
               + 1.9) if m_t is not None else None   # +1.9 s envio real (E24)
    s6 = next((r for r in resultados if r["escenario"] == "S6"), None)
    s7 = next((r for r in resultados if r["escenario"] == "S7"), None)
    m4_ok = bool(s6 and s7 and s6["alertas_media"] == 1 and s7["alertas_media"] == 2)

    veredicto = ("### Resultado de esta corrida\n\n"
                 f"| Medida | Umbral | Resultado | ¿Cumple? |\n|---|---|---|---|\n"
                 f"| **M3** Tiempo de notificación | < {suite.UMBRAL_M3_S} s | "
                 f"{round(t_total, 2) if t_total else '—'} s "
                 f"(sim {m_t} ± {s_t} s + {config.K_FRAMES_CONFIRMACION}×"
                 f"{lat_media} ms + 1.9 s envío) | "
                 f"{'✅' if t_total and t_total < suite.UMBRAL_M3_S else '❌'} |\n"
                 f"| **M4** Cooldown anti-spam | duplicadas = {suite.UMBRAL_M4} | "
                 f"S6 = {s6['alertas_media'] if s6 else '—'} alerta(s) · "
                 f"S7 = {s7['alertas_media'] if s7 else '—'} alerta(s) | "
                 f"{'✅' if m4_ok else '❌'} |\n\n"
                 f"El log de esta corrida, frame por frame con marca de "
                 f"tiempo, quedó en `{dir_marca}/log_ejecucion.jsonl` y se "
                 f"puede descargar abajo ({repeticiones} repeticiones, "
                 f"semilla 42).")

    ruta_csv = os.path.join(dir_marca, f"resultados_{marca}.csv")
    ruta_json = os.path.join(dir_marca, f"resultados_{marca}.json")
    with open(ruta_csv, "w", newline="", encoding="utf-8") as f:
        import csv as _csv
        w = _csv.DictWriter(f, fieldnames=["escenario", "tipo", "rep",
                                           "alertas", "t_alerta_sim_s",
                                           "latencia_ms", "fallos", "excepcion"])
        w.writeheader()
        w.writerows(filas_csv)
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump({"marca": marca, "reps": repeticiones,
                   "M3_t_total_s": round(t_total, 2) if t_total else None,
                   "M4_cumple": m4_ok, "escenarios": resultados},
                  f, ensure_ascii=False, indent=2)

    yield ("Listo: los 13 escenarios corrieron completos "
           f"({total} corridas) y el log quedó guardado.",
           _filas_b(resultados), veredicto, ruta_csv, ruta_json,
           os.path.join(dir_marca, "log_ejecucion.jsonl"))


def _filas_b(resultados):
    return [[r["escenario"], r["tipo"], r["descripcion"],
             f"{r['alertas_media']} ± {r['alertas_std']}",
             f"{r['t_alerta_sim_media_s']} ± {r['t_alerta_sim_std_s']}"
             if r["t_alerta_sim_media_s"] is not None else "—",
             r["excepciones"]] for r in resultados]


def _evaluar_split_progreso(agente, split, log, rep=1):
    """M1 y M2 sobre todas las escenas del split, avisando el avance escena
    por escena. Hace lo mismo que evaluar_split_log de la suite, pero
    rendiendo el progreso."""
    incidentes, control = suite.cargar_escenas(split)
    escenas_ok, t0 = 0, 0.0
    for idx, (ruta, gt) in enumerate(incidentes, start=1):
        frame = suite.frame_de(ruta)
        r = suite._simular(agente, frame, f"{split}_{idx:04d}", t0, gt, log,
                           "A", rep, split, ruta)
        escenas_ok += int(any(c in r["alertadas"] for c in gt))
        t0 += 4 * suite.INTERVALO
        yield (f"M1 en {split}: van {idx} de {len(incidentes)} escenas con "
               f"falta, {escenas_ok} aciertos hasta ahora")
    falsas, t0 = 0, 0.0
    for j, (ruta, _) in enumerate(control, start=1):
        frame = suite.frame_de(ruta)
        r = suite._simular(agente, frame, f"{split}_ctrl_{j:04d}", t0, set(),
                           log, "A", rep, split, ruta)
        falsas += int(bool(r["alertadas"]))
        t0 += 4 * suite.INTERVALO
        yield (f"M2 en {split}: van {j} de {len(control)} escenas de control, "
               f"{falsas} falsas alarmas hasta ahora")
    yield (split, {"recall": round(escenas_ok / len(incidentes), 3)
                   if incidentes else None,
                   "n_incidentes": len(incidentes),
                   "falsas": falsas,
                   "tasa_falsas": round(falsas / len(control), 3)
                   if control else None,
                   "n_control": len(control)})


def correr_parte_a():
    """M1 (recall de incidente) y M2 (falsas alarmas) sobre todas las
    escenas de val y test, una sola pasada: en CPU la inferencia es
    determinista y da el mismo número que la corrida oficial de 5."""
    agente = agente_suite()
    actuario = agente.actuadores[0]
    marca, dir_marca = _nueva_marca()
    log = suite.LogEjecucion(os.path.join(dir_marca, "log_ejecucion.jsonl"))
    resumen = {}
    for split in ("val", "test"):
        agente.reset()
        actuario.alertas.clear()
        ultimo = None
        for estado in _evaluar_split_progreso(agente, split, log):
            if isinstance(estado, tuple):
                ultimo = estado
            else:
                yield estado, "", None, None
        resumen[ultimo[0]] = ultimo[1]

    tabla = ("### Resultado de M1 y M2 en esta corrida\n\n"
             "| Medida | Split | Fórmula | Umbral | Casos | Resultado | ¿Cumple? |\n"
             "|---|---|---|---|---|---|---|\n")
    for s, r in resumen.items():
        tabla += (f"| **M1** Recall de incidente | {s} | escenas con alerta / "
                  f"escenas incidente | ≥ {suite.UMBRAL_M1} | {r['n_incidentes']} "
                  f"| {r['recall']} | "
                  f"{'✅' if r['recall'] is not None and r['recall'] >= suite.UMBRAL_M1 else '❌'} |\n"
                  f"| **M2** Falsas alarmas | {s} | escenas control con alerta / "
                  f"escenas control | ≤ {suite.UMBRAL_M2} | {r['n_control']} "
                  f"| {r['tasa_falsas']} | "
                  f"{'✅' if r['tasa_falsas'] is not None and r['tasa_falsas'] <= suite.UMBRAL_M2 else '❌'} |\n")
    tabla += ("\nEn CPU la inferencia es determinista: la misma imagen da "
              "siempre el mismo resultado. Por eso esta pasada única da el "
              "mismo número que la corrida oficial de 5 repeticiones, y la "
              "variabilidad en el tiempo se mide en la pestaña de los 13 "
              "escenarios.")

    ruta_json = os.path.join(dir_marca, f"resultados_M1M2_{marca}.json")
    with open(ruta_json, "w", encoding="utf-8") as f:
        json.dump({"marca": marca, "splits": resumen}, f,
                  ensure_ascii=False, indent=2)
    yield ("Listo: M1 y M2 corrieron sobre las 283 escenas de val y test "
           "(4 frames simulados por escena).",
           tabla, ruta_json, os.path.join(dir_marca, "log_ejecucion.jsonl"))


# --- resultados oficiales y métricas ---

def _cargar_oficial():
    base = os.path.join(RAIZ, "runs", "agente", "pruebas")
    tabla = os.path.join(base, f"tabla_resultados_{CORRIDA_OFICIAL}.md")
    if not os.path.exists(tabla):
        return ("_No se encontró la tabla oficial "
                f"`tabla_resultados_{CORRIDA_OFICIAL}.md` en este despliegue._", {})
    with open(tabla, encoding="utf-8") as f:
        contenido = f.read()
    json_of = os.path.join(base, f"resultados_{CORRIDA_OFICIAL}.json")
    resumen = {}
    if os.path.exists(json_of):
        with open(json_of, encoding="utf-8") as f:
            resumen = json.load(f)
    return contenido, resumen


def _cargar_metricas():
    """Lee las métricas del detector (P/R/F1/AP50 por clase en val y test)
    y las del agente por escena, que quedaron guardadas tras validar el
    modelo sobre los splits oficiales."""
    ruta = os.path.join(RAIZ, "eda", "salidas", "metricas_e44.json")
    if not os.path.exists(ruta):
        return None
    with open(ruta, encoding="utf-8") as f:
        return json.load(f)


def _tabla_detector(metricas, split):
    """Filas [Clase, P, R, F1, AP50] de un split, con la fila global arriba."""
    s = metricas["splits"][split]
    p, r = s["precision_media"], s["recall_media"]
    f1_g = round(2 * p * r / (p + r), 3) if (p + r) else 0.0
    filas = [["TODAS (media)", f"{p:.3f}", f"{r:.3f}", f"{f1_g:.3f}",
              f"{s['mAP50']:.3f}"]]
    filas += [[c["clase"], f"{c['P']:.3f}", f"{c['R']:.3f}",
               f"{c['F1']:.3f}", f"{c['AP50']:.3f}"]
              for c in s["por_clase"]]
    return filas


# --- la interfaz ---

def _tema():
    """Tema de la página. Se cambia con SAFESITE_TEMA=<nombre>:
    esmeralda (por defecto) | ambar | azul | grafito | ocean | neon.
    El neutral 'stone' hace que el modo oscuro sea un grafito cálido
    en vez de negro puro."""
    nombre = os.environ.get("SAFESITE_TEMA", "esmeralda").lower()
    if nombre == "ocean":
        return gr.themes.Ocean()
    if nombre == "neon":
        return gr.themes.Neon()
    hues = {"esmeralda": ("emerald", "stone"), "ambar": ("amber", "stone"),
            "azul": ("blue", "slate"), "grafito": ("stone", "stone")}
    primario, neutral = hues.get(nombre, hues["esmeralda"])
    return gr.themes.Soft(primary_hue=primario, neutral_hue=neutral)


def construir_ui():
    tabla_oficial, json_oficial = _cargar_oficial()
    with gr.Blocks(title="SafeSite Agent — Demo en vivo") as demo:
        gr.Markdown(
            f"# SafeSite Agent — monitoreo de EPP en obra\n\n"
            f"Este agente revisa imágenes de obra buscando trabajadores sin "
            f"su equipo de protección (casco, gafas, guantes, botas). Cuando "
            f"una falta aparece en {config.K_FRAMES_CONFIRMACION} frames "
            f"seguidos, se arma el mensaje que le llegaría al supervisor por "
            f"WhatsApp. Todo se calcula en el momento en el servidor; el "
            f"mensaje solo se muestra, no se envía desde esta página.")

        st_zona = gr.State("")
        st_ses = gr.State(None)
        st_gt = gr.State(None)

        # ---------------- pestana 1: demo en vivo ----------------
        with gr.Tab("Demo en vivo"):
            gr.Markdown(
                "Toma una foto con la webcam, sube una imagen o trae una del "
                "set de test. Cada imagen se procesa como un video corto de "
                "cuatro fotogramas: la falta solo se confirma si aparece en "
                "los tres primeros.")
            with gr.Row():
                with gr.Column(scale=1):
                    img_in = gr.Image(sources=["webcam", "upload"],
                                     type="numpy", label="Imagen de entrada "
                                     "(webcam o archivo)")
                    seed_in = gr.Number(
                        label="Semilla del sorteo (cámbiala para ver otras "
                              "fotos; con la misma, el mismo orden)",
                        precision=0)
                    btn_foto = gr.Button("🎲 Traer una foto del set de test",
                                         variant="secondary")
                    gt_md = gr.Markdown("")
                    btn_ver = gr.Button("Procesar esta imagen",
                                        variant="primary")
                    gr.Markdown("---")
                    gr.Markdown("Caso de falla (sensor sin dato o entrada "
                                "inválida — lo pide el enunciado)")
                    radio_falla = gr.Radio(
                        choices=list(ETIQUETA_A_CLAVE.keys()),
                        value=FALLAS["none"][0],
                        label="Tipo de falla a simular")
                    btn_falla = gr.Button("Simular la falla")
                with gr.Column(scale=1):
                    img_out = gr.Image(label="La misma imagen, con las "
                                       "detecciones dibujadas", type="numpy")
                    decision_md = gr.Markdown("Procesa una imagen para ver "
                                              "la decisión del agente.")
            with gr.Row():
                with gr.Column(scale=1):
                    det_df = gr.Dataframe(
                        headers=["Clase", "Confianza", "Tipo"],
                        label="Lo que detectó (con los umbrales aplicados)",
                        interactive=False)
                with gr.Column(scale=1):
                    payload_md = gr.Markdown(
                        "**Mensaje al supervisor:** aún no hay nada "
                        "procesado.")
            with gr.Row():
                resumen_md = gr.Markdown("")
                log_txt = gr.Textbox(label="Bitácora de la sesión (qué "
                                        "procesó y qué decidió, con hora)",
                                     lines=8, interactive=False)

        # ---------------- pestana 2: pruebas en vivo ----------------
        with gr.Tab("Pruebas (M1–M4)"):
            gr.Markdown(
                "Aquí corre en vivo la misma suite de pruebas del proyecto "
                "(`src/safesite/pruebas_medidas.py`). Los resultados van "
                "apareciendo mientras se ejecuta y al final puedes descargar "
                "el log frame por frame y los resultados (CSV/JSON), en el "
                "formato de la entrega.\n\n"
                "Tiempos aproximados: los 13 escenarios, entre 2 y 5 "
                "minutos; los M1 y M2 sobre todas las escenas, entre 15 y "
                "30 minutos. Puedes usar las otras pestañas mientras corre.")
            with gr.Row():
                btn_b = gr.Button("Correr los 13 escenarios × 5 repeticiones",
                                  variant="primary")
                btn_a = gr.Button("Correr M1 y M2 sobre todos los escenarios "
                                  "(tarda, pero vale la pena)",
                                  variant="secondary")
            estado_b = gr.Markdown("")
            tabla_b = gr.Dataframe(
                headers=["ID", "Tipo", "Descripción", "Alertas (media±σ)",
                         "t_alerta s (media±σ)", "Excepciones"],
                label="Escenarios S1–S13, según van corriendo",
                interactive=False)
            veredicto_b = gr.Markdown("")
            with gr.Row():
                csv_b = gr.File(label="Resultados de esta corrida (CSV)")
                json_b = gr.File(label="Resultados de esta corrida (JSON)")
                log_b = gr.File(label="Log frame por frame (JSONL)")
            gr.Markdown("---")
            estado_a = gr.Markdown("")
            tabla_a = gr.Markdown("")
            with gr.Row():
                json_a = gr.File(label="Resultados M1/M2 (JSON)")
                log_a = gr.File(label="Log M1/M2 frame por frame (JSONL)")

        # ---------------- pestana 3: resultados oficiales ----------------
        with gr.Tab("Resultados oficiales"):
            gr.Markdown(
                f"Corrida oficial de la suite, hecha en el equipo local con "
                f"GPU y 5 repeticiones (14 de octubre de 2026): "
                f"`resultados_{CORRIDA_OFICIAL}`. Si corres las pruebas de "
                f"la pestaña anterior, los números deben coincidir con "
                f"estos.")
            gr.Markdown(tabla_oficial)
            if json_oficial:
                with gr.Accordion("JSON completo de la corrida oficial",
                                  open=False):
                    gr.JSON(json_oficial)
            base = os.path.join(RAIZ, "runs", "agente", "pruebas")
            with gr.Row():
                gr.File(value=os.path.join(base, f"resultados_{CORRIDA_OFICIAL}.csv"),
                        label="CSV oficial")
                gr.File(value=os.path.join(base, f"resultados_{CORRIDA_OFICIAL}.json"),
                        label="JSON oficial")
                gr.File(value=os.path.join(base, "log_ejecucion.jsonl"),
                        label="Log oficial por frame (JSONL)")
                gr.File(value=os.path.join(base, f"tabla_resultados_{CORRIDA_OFICIAL}.md"),
                        label="Tabla oficial (Markdown)")

        # ---------------- pestana 4: EDA y metricas ----------------
        with gr.Tab("EDA y métricas"):
            figuras = os.path.join(RAIZ, "eda", "figuras")
            metricas = _cargar_metricas()
            gr.Markdown(
                "De dónde salen los datos del agente, qué se verificó antes "
                "de construirlo y con qué números quedó.")
            with gr.Accordion("1. El dataset y los supuestos que se "
                              "validaron", open=True):
                gr.Markdown(
                    "1,416 imágenes de obra (Construction PPE de "
                    "Ultralytics) con 11 clases: persona, 5 equipos de "
                    "protección, 4 faltas `no_*` y una de ruido. Las fotos "
                    "del botón de foto aleatoria salen del split de test "
                    "(140 imágenes; el train tiene 1,130 y la validación "
                    "143).\n\n"
                    "Antes de construir el agente, cada supuesto se "
                    "verificó midiendo. Varios resultaron falsos, y esas "
                    "correcciones definieron al agente que estás usando.")
                gr.Markdown(
                    "| Supuesto | Qué se encontró al medirlo | Qué se decidió |\n"
                    "|---|---|---|\n"
                    "| Las etiquetas YOLO están bien escritas | Confirmado: las "
                    "1,129 etiquetas de train se verificaron una por una contra "
                    "el NDJSON oficial, sin una sola discrepancia | No había "
                    "nada que re-etiquetar |\n"
                    "| Los splits de train/val/test estaban bien repartidos | "
                    "Falso: 112 imágenes del test oficial estaban metidas en el "
                    "train, y no existía set de validación | Se rehízo el split "
                    "completo (el `dataset_v2` que usa esta página) y se creó "
                    "el set de validación que faltaba |\n"
                    "| Hay suficientes ejemplos de faltas para aprender | Falso: "
                    "solo el 20.3% de las imágenes de train muestra alguna falta "
                    "`no_*`, y `no_boots` apenas aparece | Umbrales bajos (0.15) "
                    "y confirmación temporal K=3; el proyecto se mide por "
                    "recall por clase, no por exactitud global |\n"
                    "| 'Sin casco' se puede deducir buscando el casco dentro de "
                    "la caja de la persona | Falso: esa regla falla el 38.2% de "
                    "las veces | Las decisiones usan únicamente las clases `no_*` "
                    "explícitas del detector |\n"
                    "| Las cajas de gafas están a la altura de los ojos | Falso: "
                    "la mediana queda al 14.5% de la altura de la persona, "
                    "cuando los ojos reales van por el ~8% (509 cajas medidas) | "
                    "Re-anclaje visual a nivel de ojos (solo presentación: no "
                    "toca detecciones ni métricas) |\n"
                    "| Todas las imágenes son parecidas | No tanto: el 21.2% no "
                    "es de 640×640 y el 4.5% de la muestra es muy oscura | La "
                    "inferencia se mantiene en 640 o más; el aumento de datos "
                    "nocturno queda como recomendación para cámaras 24/7 |")
                with gr.Row():
                    gr.Image(value=os.path.join(figuras, "fig1_clases.png"),
                             label="Distribución de clases: las faltas no_* "
                                   "son minoría")
                    gr.Image(value=os.path.join(figuras, "fig3_splits.png"),
                             label="La contaminación de splits que obligó a "
                                   "rehacerlos")
                with gr.Row():
                    gr.Image(value=os.path.join(figuras,
                                                "fig2_cajas_por_imagen.png"),
                             label="Cajas por imagen: escenas densas")
                    gr.Image(value=os.path.join(figuras, "fig6_brillo.png"),
                             label="Brillo: el 4.5% de la muestra es muy "
                                   "oscura")
            with gr.Accordion("2. Lo que no se pudo validar (y la foto del "
                              "fútbol)", open=False):
                gr.Markdown(
                    "Tres supuestos quedaron sin verificar, y así quedó "
                    "escrito en el informe: la calidad de las etiquetas "
                    "hechas por humanos, posibles imágenes casi duplicadas "
                    "entre splits, y que toda foto viniera de una obra.\n\n"
                    "El último falló en la práctica: en una foto de un "
                    "partido de fútbol el detector marcó botas sobre los "
                    "tenis y dejó una gafa por encima de los ojos. Al barrer "
                    "las 1,413 imágenes se encontraron 9 pares de cajas de "
                    "botas repetidas y 2 gafas fuera de lugar. La corrección "
                    "fue solo visual (no repetir cajas solapadas, y el "
                    "re-anclaje de gafas ya no sube tanto): las alertas y "
                    "las métricas no cambiaron — se re-corró la suite para "
                    "comprobarlo. La lección queda escrita: el agente es "
                    "para obras; otros contextos exigen otros datos.")
            with gr.Accordion("3. Métricas del detector (nivel caja)", 
                              open=False):
                if metricas:
                    gr.Markdown(
                        "Precisión, recall y F1 por clase del detector "
                        "(IoU 0.5), en el punto donde cada clase alcanza "
                        "su mejor F1.\n\n"
                        "¿Y la *accuracy* del detector? En detección no se "
                        "usa: una imagen tiene muchos objetos a la vez y el "
                        "fondo acierta solo, así que un accuracy global "
                        "saldría inflado y no diría nada. La exactitud del "
                        "agente sí se puede medir bien, por escena: está "
                        "en la sección 4.")
                    for split in ("val", "test"):
                        s = metricas["splits"][split]
                        gr.Markdown(f"**Split {split}** — mAP50 = "
                                    f"{s['mAP50']:.3f}")
                        gr.Dataframe(
                            value=_tabla_detector(metricas, split),
                            headers=["Clase", "Precisión", "Recall", "F1",
                                     "AP50"],
                            interactive=False,
                            label=f"Detector por clase — {split}")
                else:
                    gr.Markdown("_(no se encontró "
                                "`eda/salidas/metricas_e44.json`)_")
            with gr.Accordion("4. Métricas del agente (nivel escena — las "
                              "que valen)", open=False):
                if metricas:
                    ag = metricas["agente_escena"]
                    gr.Markdown(
                        "El agente acierta o falla **por escena**: si había "
                        "falta y alertó, acierto (TP); había falta y no "
                        "alertó, se le escapó (FN); no había falta y "
                        "alertó, falsa alarma (FP). Con los umbrales reales "
                        "de operación quedó así:")
                    gr.Dataframe(
                        value=[[sp.title(), a["escenas_incidente"],
                                a["escenas_control"], a["TP"], a["FN"],
                                a["FP"], a["TN"], f"{a['accuracy_escena']:.3f}",
                                f"{a['precision_escena']:.3f}",
                                f"{a['recall_escena_M1']:.3f}",
                                f"{a['f1_escena']:.3f}"]
                               for sp, a in ag.items()],
                        headers=["Split", "Escenas con falta", "Escenas "
                                 "control", "TP", "FN", "FP", "TN",
                                 "Accuracy", "Precisión", "Recall (M1)",
                                 "F1"],
                        interactive=False,
                        label="Resultados por escena")
                    gr.Markdown(
                        "**Las medidas pre-registradas de la entrega "
                        "(corrida oficial, 5 repeticiones):**\n\n"
                        "| Medida | Fórmula | Umbral | Resultado |\n"
                        "|---|---|---|---|\n"
                        "| M1 recall de incidente | escenas con alerta / "
                        "escenas con falta | ≥ 0.70 | **0.964 val / 0.962 "
                        "test** ✅ |\n"
                        "| M2 falsas alarmas | escenas de control alertadas / "
                        "control | ≤ 0.10 | **0.035 val / 0.026 test** ✅ |\n"
                        "| M3 tiempo de notificación | confirmación + "
                        "procesamiento + envío WhatsApp | < 10 s | "
                        "**2.99 s** ✅ (en vivo: ~2.6 s) |\n"
                        "| M4 cooldown anti-spam | duplicadas dentro de la "
                        "ventana | = 0 | S6 = 1 alerta, S7 = 2 ✅ |")
                    gr.Markdown(
                        "La idea central del proyecto está en el contraste "
                        "con la sección 3: el detector falla mucho caja por "
                        "caja en las faltas (`no_boots` y `no_goggle` tienen "
                        "F1 casi nulo), pero el agente las confirma viéndolas "
                        "3 frames seguidos y llega a un F1 de escena de "
                        "0.92. La confirmación temporal compensa la "
                        "debilidad del detector.")
                else:
                    gr.Markdown("_(no se encontró "
                                "`eda/salidas/metricas_e44.json`)_")

        # ---------------- pestana 5: instrucciones ----------------
        with gr.Tab("Cómo probar"):
            gr.Markdown(INSTRUCCIONES)

        # ---------------- eventos ----------------
        def _nueva_sesion():
            zona = f"web_{uuid.uuid4().hex[:8]}"
            ses = {"verificaciones": 0, "alertas": 0, "frames_fallidos": 0,
                   "log": [], "seed": random.randint(1, 9999), "sorteos": 0}
            return zona, ses, _resumen_md(zona, ses), ses["seed"]

        demo.load(_nueva_sesion, None,
                  [st_zona, st_ses, resumen_md, seed_in])
        btn_ver.click(verificar, [img_in, st_zona, st_gt, st_ses],
                      [img_out, decision_md, det_df, payload_md, resumen_md,
                       log_txt, st_ses])
        btn_foto.click(foto_aleatoria, [seed_in, st_ses],
                       [img_in, gt_md, st_gt, log_txt, st_ses])
        btn_falla.click(simular_falla, [radio_falla, st_zona, st_ses],
                        [img_out, decision_md, resumen_md, log_txt, st_ses])
        btn_b.click(correr_parte_b, None,
                    [estado_b, tabla_b, veredicto_b, csv_b, json_b, log_b])
        btn_a.click(correr_parte_a, None,
                    [estado_a, tabla_a, json_a, log_a])
    return demo


INSTRUCCIONES = """
### Cómo probar el agente (10 a 15 minutos)

**1. Una foto con falta (el caso típico)**
Trae una foto del set de test hasta que salga una con faltas (la página te
dice cuáles, según la etiqueta oficial). Procesa la imagen y fíjate en las
cajas rojas, en la línea de tiempo (la falta se confirma a la tercera vez
que se ve) y en el mensaje que le llegaría al supervisor.

**2. Una foto sin faltas (el caso control)**
Trae más fotos hasta que salga una de control: el agente debería quedarse
callado. Las pocas veces que alerte en una escena así son las falsas
alarmas que mide M2.

**3. El caso de falla del sensor**
Elige un tipo de falla y simúlala: el agente registra el frame fallido y
sigue trabajando, no se cae. Con el frame negro no hay falla: es una imagen
válida sin contenido, no detecta nada y no alerta.

**4. Con tu propia cámara**
Autoriza la webcam y toma una captura: si apareces con la cabeza descubierta
en primer plano, lo más probable es que te marque como "SIN CASCO".

**5. Las pruebas de desempeño**
Corre los 13 escenarios en la pestaña de pruebas y compara con la corrida
oficial de la tercera pestaña: en CPU deben salir iguales.

### Qué hace cada parte
- El que ve es el detector (YOLOv8s, una herramienta externa): encuentra
  cascos, guantes, chalecos, botas, gafas y las faltas `no_*` en cada imagen.
- Las decisiones son código propio: umbrales por clase, confirmar una falta
  solo tras verla 3 veces seguidas, y no repetir la misma alerta antes de
  30 segundos.
- La acción arma el mensaje de WhatsApp; en esta página solo se muestra.

El código, el entrenamiento y la bitácora del proyecto están en el
repositorio (el enlace va en el documento de la entrega).
"""


def main():
    demo = construir_ui()
    puerto = int(os.environ.get("SAFESITE_PUERTO", "7860"))
    # En el Space hay que escuchar en 0.0.0.0; local, en 127.0.0.1 para que
    # la URL impresa sea abrible en el navegador (0.0.0.0 no se abre).
    en_space = bool(os.environ.get("HF_SPACE_ID")
                    or os.environ.get("SPACE_ID"))
    server = "0.0.0.0" if en_space else "127.0.0.1"
    print(f"\nAbre el navegador en: http://localhost:{puerto}\n")
    demo.queue().launch(server_name=server, server_port=puerto,
                        theme=_tema(), show_error=True)


if __name__ == "__main__":
    main()
