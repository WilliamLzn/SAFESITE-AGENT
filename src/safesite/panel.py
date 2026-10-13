"""SafeSite-Agent — Panel web de supervisión con detección EN VIVO por webcam.

Fase 4 (final): conecta el agente al mundo físico. Arquitectura:

    webcam → hilo de captura → agente completo (percepción → razonamiento
    K frames → memoria/cooldown) ─┬→ MJPEG al navegador (video con cajas)
                                  └→ cola + worker → WhatsApp (asíncrono:
                                     el video NUNCA se congela por un envío)

El webhook INFO sigue funcionando durante la sesión en vivo (el historial
lo escribe la Memoria del agente).

Uso (desde la RAIZ del proyecto):
    .venv\\Scripts\\python.exe -m src.safesite.panel            # GPU, zona obra_cam1
    .venv\\Scripts\\python.exe -m src.safesite.panel --device cpu
    .venv\\Scripts\\python.exe -m src.safesite.panel --zona entrada_obra
Abre http://localhost:5000 en el navegador.
"""
import argparse
import collections
import queue
import threading
import time

import cv2
from flask import Flask, Response, jsonify

from . import config
from .actuarios import ActuadorConsola, ActuadorWhatsApp
from .agente import SafeSiteAgent
from .percepcion import Percepcion

PAGINA = """<!DOCTYPE html>
<html lang="es"><head>
<meta charset="utf-8"><title>SafeSite-Agent · Panel en vivo</title>
<style>
  :root { --fondo:#0f172a; --tarjeta:#1e293b; --texto:#e2e8f0; --verde:#22c55e;
          --rojo:#ef4444; --gris:#64748b; }
  body { background:var(--fondo); color:var(--texto); font-family:system-ui,
         sans-serif; margin:0; padding:20px; }
  h1 { font-size:1.4rem; margin:0 0 4px; }
  .sub { color:var(--gris); font-size:.85rem; margin-bottom:16px; }
  .layout { display:grid; grid-template-columns:2fr 1fr; gap:16px; }
  @media (max-width:900px){ .layout{grid-template-columns:1fr;} }
  .video { width:100%; border-radius:10px; background:#000; aspect-ratio:4/3;
           object-fit:contain; }
  .tarjetas { display:grid; grid-template-columns:repeat(auto-fill,minmax(110px,1fr));
              gap:8px; margin-top:12px; }
  .tarjeta { background:var(--tarjeta); border-radius:10px; padding:10px;
             text-align:center; }
  .tarjeta .num { font-size:1.6rem; font-weight:700; }
  .tarjeta .etq { font-size:.7rem; color:var(--gris); text-transform:uppercase; }
  .ok { color:var(--verde); } .falta { color:var(--rojo); }
  .panel { background:var(--tarjeta); border-radius:10px; padding:14px; }
  .panel h2 { font-size:.95rem; margin:0 0 10px; color:var(--gris);
              text-transform:uppercase; }
  #log { max-height:420px; overflow-y:auto; font-size:.8rem; }
  .incidente { border-left:3px solid var(--rojo); padding:6px 10px;
               margin-bottom:8px; background:#0f172a; border-radius:6px; }
  .incidente .hora { color:var(--gris); font-size:.7rem; }
  .vacio { color:var(--gris); font-style:italic; }
  .estado-linea { font-size:.75rem; color:var(--gris); margin-top:10px; }
  .punto { display:inline-block; width:9px; height:9px; border-radius:50%;
           background:var(--verde); margin-right:6px; animation:pulso 1.5s infinite; }
  @keyframes pulso { 50%{opacity:.3;} }
</style></head><body>
<h1>👷 SafeSite-Agent — Supervisión en vivo</h1>
<div class="sub" id="sub">conectando con la cámara…</div>
<div class="layout">
  <div>
    <img class="video" src="/video" alt="video en vivo">
    <div class="tarjetas" id="tarjetas"></div>
  </div>
  <div class="panel">
    <h2>🚨 Incidentes confirmados</h2>
    <div id="log"><div class="vacio">sin incidentes todavía…</div></div>
    <div class="estado-linea" id="estado"></div>
  </div>
</div>
<script>
let ultimosIds = "";
async function refrescar() {
  try {
    const r = await fetch('/estado');
    const e = await r.json();
    document.getElementById('sub').textContent =
      `zona: ${e.zona} · modelo: ${e.modelo} · ${e.whatsapp}`;
    const nombres = {'Person':'Personas','helmet':'Cascos','no_helmet':'SIN CASCO',
      'gloves':'Guantes','no_gloves':'SIN GUANTES','vest':'Chalecos',
      'boots':'Botas','no_boots':'SIN BOTAS','goggles':'Gafas',
      'no_goggle':'SIN GAFAS','none':'None'};
    document.getElementById('tarjetas').innerHTML = Object.entries(e.detecciones)
      .map(([k,v]) => `<div class="tarjeta"><div class="num ${k.startsWith('no_')&&v>0?'falta':'ok'}">${v}</div><div class="etq">${nombres[k]||k}</div></div>`)
      .join('');
    const ids = e.incidentes.map(i=>i.t).join(',');
    if (ids !== ultimosIds) {
      ultimosIds = ids;
      document.getElementById('log').innerHTML = e.incidentes.length
        ? e.incidentes.map(i=>`<div class="incidente"><div class="hora">${i.t} · zona ${i.zona}</div>${i.faltas}</div>`).join('')
        : '<div class="vacio">sin incidentes todavía…</div>';
    }
    document.getElementById('estado').innerHTML =
      `<span class="punto"></span>procesando a ${e.fps} FPS · latencia ${e.latencia_ms} ms/frame · ${e.frames} frames`;
  } catch (err) { /* reintenta en el proximo tick */ }
}
setInterval(refrescar, 1500); refrescar();
</script></body></html>"""


class ActuadorWhatsAppAsync(ActuadorWhatsApp):
    """Encola los envíos: el worker los manda por HTTP sin congelar el video."""

    def __init__(self, cola):
        super().__init__()
        self.cola = cola

    def alertar_lote(self, incidentes, frame_anotado=None, ruta_frame=None):
        import copy
        frame = frame_anotado.copy() if frame_anotado is not None else None
        self.cola.put((incidentes, frame))
        clases = ", ".join(i.clase for i in incidentes)
        print(f"📨 encolado para WhatsApp ({len(incidentes)} faltas): {clases}",
              flush=True)

    def alertar(self, incidente, frame_anotado=None, ruta_frame=None):
        self.alertar_lote([incidente], frame_anotado, ruta_frame)


class PanelSafeSite:
    def __init__(self, zona, device, usar_whatsapp=True):
        self.zona = zona
        self.cola = queue.Queue()
        actuadores = [ActuadorConsola()]
        self.whatsapp_real = ActuadorWhatsApp() if usar_whatsapp else None
        if usar_whatsapp:
            actuadores.append(ActuadorWhatsAppAsync(self.cola))
        self.agente = SafeSiteAgent(device=device, actuadores=actuadores)
        self.lock = threading.Lock()
        self.ultimo_frame = None          # anotado, para el stream
        self.latencias = collections.deque(maxlen=30)
        self.frames = 0
        self.marca_fps = time.time()
        self.fps = 0.0
        self.incidentes = collections.deque(maxlen=50)

    # ---------- bucle de captura ----------
    def _capturar(self):
        cam = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not cam.isOpened():
            raise RuntimeError("no se pudo abrir la webcam (¿la usa otra app?)")
        cam.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cam.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        print(f"🎥 webcam abierta ({int(cam.get(3))}x{int(cam.get(4))})", flush=True)
        while True:
            ok, frame = cam.read()
            if not ok:
                time.sleep(0.05)
                continue
            incidentes, filtradas = self.agente.procesar_frame(
                frame, zona=self.zona, t_stamp=time.time())
            anotado = self.agente.percepcion.anotar(frame, filtradas)
            with self.lock:
                self.ultimo_frame = anotado
                self._conteos = self._contar(filtradas)
            self.frames += 1
            ahora = time.time()
            if ahora - self.marca_fps >= 1.0:
                self.fps = round(self.frames / (ahora - self.marca_fps), 1)
                self.frames = 0
                self.marca_fps = ahora
            for inc in incidentes:
                self.incidentes.append({
                    "t": time.strftime("%H:%M:%S"),
                    "zona": inc.zona,
                    "faltas": f"<b>{inc.clase}</b> (conf {inc.conf_media:.0%}, "
                              f"{inc.frames_consecutivos} frames)",
                })

    @staticmethod
    def _contar(filtradas):
        conteos = {nombre: 0 for nombre in config.NOMBRES_CLASES.values()}
        for d in filtradas:
            conteos[d.nombre] = conteos.get(d.nombre, 0) + 1
        return conteos

    # ---------- worker de WhatsApp ----------
    def _enviar_whatsapp(self):
        while True:
            incidentes, frame = self.cola.get()
            if self.whatsapp_real is None:
                continue
            try:
                self.whatsapp_real.alertar_lote(incidentes, frame_anotado=frame)
            except Exception as e:
                print(f"❌ worker WhatsApp: {e}", flush=True)

    def iniciar(self):
        threading.Thread(target=self._capturar, daemon=True).start()
        if self.whatsapp_real is not None:
            threading.Thread(target=self._enviar_whatsapp, daemon=True).start()

    # ---------- endpoints ----------
    def frame_jpeg(self):
        with self.lock:
            frame = self.ultimo_frame
        if frame is None:
            return None
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        return buf.tobytes() if ok else None

    def estado(self):
        with self.lock:
            conteos = dict(getattr(self, "_conteos", {}))
        return {
            "zona": self.zona,
            "modelo": config.RUTA_MODELO.split("\\")[-3],
            "fps": self.fps,
            "latencia_ms": round(self.agente.latencia_media_ms, 1),
            "detecciones": conteos,
            "incidentes": list(self.incidentes),
        }


def main():
    parser = argparse.ArgumentParser(
        description="Panel web de SafeSite-Agent con detección en vivo")
    parser.add_argument("--zona", default="obra_cam1")
    parser.add_argument("--device", default="0")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--sin-whatsapp", action="store_true",
                        help="desactiva el envío real de WhatsApp")
    args = parser.parse_args()

    panel = PanelSafeSite(args.zona, args.device,
                          usar_whatsapp=not args.sin_whatsapp)
    app = Flask(__name__)

    @app.route("/")
    def indice():
        return PAGINA

    @app.route("/video")
    def video():
        def flujo():
            while True:
                jpeg = panel.frame_jpeg()
                if jpeg:
                    yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
                           + jpeg + b"\r\n")
                time.sleep(1 / 15)
        return Response(flujo(),
                        mimetype="multipart/x-mixed-replace; boundary=frame")

    @app.route("/estado")
    def estado():
        return jsonify(panel.estado())

    panel.iniciar()
    modo_wa = (panel.whatsapp_real.modo if panel.whatsapp_real
               else "DESHABILITADO")
    print(f"🖥️  panel en http://localhost:{args.port} | zona: {args.zona} | "
          f"device: {args.device} | WhatsApp: {modo_wa}", flush=True)
    app.run(host="127.0.0.1", port=args.port, threaded=True,
            use_reloader=False, debug=False)


if __name__ == "__main__":
    main()
