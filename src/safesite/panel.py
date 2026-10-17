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
from datetime import datetime

import cv2
from flask import Flask, Response, jsonify

from . import config
from .actuarios import ActuadorConsola, ActuadorWhatsApp
from .agente import SafeSiteAgent
from .percepcion import Percepcion
from .razonamiento import Incidente

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
  .controles { display:flex; gap:10px; flex-wrap:wrap; margin-bottom:14px; }
  .boton { background:var(--tarjeta); color:var(--texto);
           border:1px solid var(--gris); border-radius:8px; padding:8px 14px;
           cursor:pointer; font-size:.85rem; transition:border-color .15s; }
  .boton:hover { border-color:var(--verde); }
  .boton:disabled { opacity:.5; cursor:wait; }
  .boton.apagado { border-color:var(--rojo); color:var(--rojo); }
  .faltas-badge { font-size:.75rem; color:var(--rojo); align-self:center; }
</style></head><body>
<h1>👷 SafeSite-Agent — Supervisión en vivo</h1>
<div class="sub" id="sub">conectando con la cámara…</div>
<div class="controles">
  <button id="btn-wa" class="boton" onclick="toggleWA()">⏸️ Pausar WhatsApp</button>
  <button id="btn-alerta" class="boton" onclick="alertaManual()">📨 Enviar alerta ahora</button>
  <span class="faltas-badge" id="faltas-badge"></span>
</div>
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

function actualizarBotonWA(activo) {
  const b = document.getElementById('btn-wa');
  b.textContent = activo ? '⏸️ Pausar WhatsApp' : '▶️ Reanudar WhatsApp';
  b.classList.toggle('apagado', !activo);
}

async function toggleWA() {
  try {
    const r = await fetch('/whatsapp/toggle', {method:'POST'});
    const e = await r.json();
    actualizarBotonWA(e.whatsapp_activo);
  } catch (err) { /* el proximo refresco resincroniza */ }
}

async function alertaManual() {
  const b = document.getElementById('btn-alerta');
  b.disabled = true; b.textContent = '⏳ enviando…';
  try {
    const r = await fetch('/alerta/manual', {method:'POST'});
    const e = await r.json();
    b.textContent = e.ok ? (e.faltas && e.faltas.length
        ? '✅ Enviada (' + e.faltas.join(', ') + ')'
        : '✅ Enviada (sin faltas)')
      : '⚠️ ' + (e.detalle || 'sin enviar');
  } catch (err) { b.textContent = '⚠️ error de red'; }
  setTimeout(() => {
    b.disabled = false; b.textContent = '📨 Enviar alerta ahora';
  }, 2500);
}

async function refrescar() {
  try {
    const r = await fetch('/estado');
    const e = await r.json();
    document.getElementById('sub').textContent =
      `zona: ${e.zona} · perfil: ${e.perfil} · modelo: ${e.modelo} · ${e.whatsapp_modo}`;
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
    actualizarBotonWA(e.whatsapp_activo);
    document.getElementById('faltas-badge').textContent =
      e.faltas_actuales.length
        ? '⚠️ faltas actuales: ' + e.faltas_actuales.map(f=>f.clase).join(', ')
        : '';
    document.getElementById('estado').innerHTML =
      `<span class="punto"></span>procesando a ${e.fps} FPS · latencia ${e.latencia_ms} ms/frame · ${e.frames} frames`;
  } catch (err) { /* reintenta en el proximo tick */ }
}
setInterval(refrescar, 1500); refrescar();
</script></body></html>"""


class ActuadorWhatsAppAsync(ActuadorWhatsApp):
    """Encola los envíos: el worker los manda por HTTP sin congelar el video.

    E32: bandera `activo` (pausa desde el panel). En pausa, los incidentes
    se siguen confirmando y registrando en el panel/historial, pero NO se
    envían por WhatsApp.
    """

    def __init__(self, cola):
        super().__init__()
        self.cola = cola
        self.activo = True

    def alertar_lote(self, incidentes, frame_anotado=None, ruta_frame=None):
        if not self.activo:
            clases = ", ".join(i.clase for i in incidentes)
            print(f"🔕 WhatsApp PAUSADO: lote ({len(incidentes)} faltas: "
                  f"{clases}) registrado en panel/historial, NO enviado",
                  flush=True)
            return None
        import copy
        frame = frame_anotado.copy() if frame_anotado is not None else None
        self.cola.put((incidentes, frame))
        clases = ", ".join(i.clase for i in incidentes)
        print(f"📨 encolado para WhatsApp ({len(incidentes)} faltas): {clases}",
              flush=True)

    def alertar(self, incidente, frame_anotado=None, ruta_frame=None):
        self.alertar_lote([incidente], frame_anotado, ruta_frame)


class PanelSafeSite:
    def __init__(self, zona, device, usar_whatsapp=True, perfil="vivo"):
        self.zona = zona
        self.perfil = perfil
        self.cola = queue.Queue()
        actuadores = [ActuadorConsola()]
        self.whatsapp_real = ActuadorWhatsApp() if usar_whatsapp else None
        self.actuador_async = None
        if usar_whatsapp:
            self.actuador_async = ActuadorWhatsAppAsync(self.cola)
            actuadores.append(self.actuador_async)
        # E33/E35: el panel corre por defecto con el perfil VIVO (umbrales
        # por clase + regla de coherencia calibrados en el piloto);
        # --perfil evaluacion reproduce el umbral global 0.15 de la suite.
        perfil_umbrales = (config.UMBRALES_INCUMPLIMIENTO_VIVO
                           if perfil == "vivo" else None)
        coherencia = (config.REGLA_COHERENCIA_VIVO
                      if perfil == "vivo" else None)
        self.agente = SafeSiteAgent(device=device, actuadores=actuadores,
                                    perfil_umbrales=perfil_umbrales,
                                    coherencia=coherencia)
        self.lock = threading.Lock()
        self.ultimo_frame = None          # anotado, para el stream
        self._faltas = []                 # detecciones no_* del ultimo frame
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
                self._faltas = [d for d in filtradas
                                if d.cls_id in config.CLASES_INCUMPLIMIENTO]
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

    # ---------- control del canal WhatsApp (E32) ----------

    def toggle_whatsapp(self):
        """Alterna la pausa del envío de WhatsApp.

        En pausa: los incidentes se confirman y quedan en el log del panel
        y en el historial, pero no llegan al teléfono. El botón 'Enviar
        alerta ahora' sigue funcionando (petición explícita)."""
        if self.actuador_async is None:
            return None
        self.actuador_async.activo = not self.actuador_async.activo
        estado = "REANUDADO" if self.actuador_async.activo else "PAUSADO"
        print(f"🔔 WhatsApp {estado} desde el panel", flush=True)
        return self.actuador_async.activo

    def enviar_alerta_manual(self):
        """Envía por WhatsApp el estado actual de la zona bajo petición
        explícita (forzar=True: bypass de pausa y de límites anti-spam)."""
        if self.whatsapp_real is None:
            return {"ok": False,
                    "detalle": "panel iniciado con --sin-whatsapp"}
        with self.lock:
            faltas = list(self._faltas)
            frame = self.ultimo_frame
        frame = frame.copy() if frame is not None else None
        ahora = time.time()
        # deduplicar por clase (dos personas sin casco = 1 falta en el msg)
        por_clase = {}
        for d in faltas:
            if d.cls_id not in por_clase or d.conf > por_clase[d.cls_id].conf:
                por_clase[d.cls_id] = d
        incidentes = [
            Incidente(zona=self.zona, clase_id=d.cls_id, clase=d.nombre,
                      conf_media=d.conf, frames_consecutivos=0,
                      t_confirmacion=ahora, t_inicio_deteccion=ahora,
                      origen_ultimo_frame="manual")
            for d in sorted(por_clase.values(), key=lambda x: x.cls_id)]
        if incidentes:
            wamid = self.whatsapp_real.alertar_lote(
                incidentes, frame_anotado=frame, forzar=True)
            return {"ok": bool(wamid),
                    "faltas": [i.clase for i in incidentes],
                    "detalle": None if wamid else "envío falló (ver consola)"}
        # sin faltas actuales: mensaje de estado de prueba del canal
        if self.whatsapp_real.modo != "ENVIO-REAL":
            print("📲 WhatsApp[DRY-RUN] manual: zona sin incumplimientos",
                  flush=True)
            return {"ok": True, "faltas": [], "detalle": "dry-run"}
        try:
            hora = datetime.now().strftime("%I:%M %p").lstrip("0")
            self.whatsapp_real.enviar_texto(
                f"✅ SafeSite — {hora}\n\nZona {self.zona}: sin "
                f"incumplimientos en el último fotograma (prueba manual "
                f"del canal desde el panel).")
            return {"ok": True, "faltas": [], "detalle": None}
        except Exception as e:
            print(f"❌ WhatsApp manual: {e}", flush=True)
            return {"ok": False, "faltas": [], "detalle": str(e)[:80]}

    def estado(self):
        with self.lock:
            conteos = dict(getattr(self, "_conteos", {}))
            faltas = [{"clase": d.nombre, "conf": round(d.conf, 2)}
                      for d in getattr(self, "_faltas", [])]
        return {
            "zona": self.zona,
            "perfil": self.perfil,
            "modelo": config.RUTA_MODELO.split("\\")[-3],
            "fps": self.fps,
            "latencia_ms": round(self.agente.latencia_media_ms, 1),
            "detecciones": conteos,
            "incidentes": list(self.incidentes),
            "whatsapp_activo": (self.actuador_async.activo
                                if self.actuador_async else False),
            "whatsapp_modo": (self.whatsapp_real.modo
                              if self.whatsapp_real else "DESHABILITADO"),
            "faltas_actuales": faltas,
        }


def main():
    parser = argparse.ArgumentParser(
        description="Panel web de SafeSite-Agent con detección en vivo")
    parser.add_argument("--zona", default="obra_cam1")
    parser.add_argument("--device", default="0")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--perfil", default="vivo",
                        choices=("vivo", "evaluacion"),
                        help="umbrales por clase: vivo (calibrado en piloto) "
                             "o evaluacion (umbral global 0.15 de la suite)")
    parser.add_argument("--sin-whatsapp", action="store_true",
                        help="desactiva el envío real de WhatsApp")
    args = parser.parse_args()

    panel = PanelSafeSite(args.zona, args.device,
                          usar_whatsapp=not args.sin_whatsapp,
                          perfil=args.perfil)
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

    @app.route("/whatsapp/toggle", methods=["POST"])
    def whatsapp_toggle():
        nuevo = panel.toggle_whatsapp()
        return jsonify({
            "whatsapp_activo": nuevo,
            "whatsapp_modo": (panel.whatsapp_real.modo
                              if panel.whatsapp_real else "DESHABILITADO"),
        })

    @app.route("/alerta/manual", methods=["POST"])
    def alerta_manual():
        return jsonify(panel.enviar_alerta_manual())

    panel.iniciar()
    modo_wa = (panel.whatsapp_real.modo if panel.whatsapp_real
               else "DESHABILITADO")
    print(f"🖥️  panel en http://localhost:{args.port} | zona: {args.zona} | "
          f"perfil: {args.perfil} | device: {args.device} | "
          f"WhatsApp: {modo_wa}", flush=True)
    app.run(host="127.0.0.1", port=args.port, threaded=True,
            use_reloader=False, debug=False)


if __name__ == "__main__":
    main()
