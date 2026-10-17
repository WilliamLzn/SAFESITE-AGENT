"""Servidor de webhooks de WhatsApp —SafeSite-Agent (Fase 4, parte 2).

Permite la conversación de vuelta: cuando el supervisor responde INFO a una
alerta, este servidor recibe el mensaje entrante (webhook de Meta) y envía
el DETALLE TÉCNICO de la última alerta (métricas bajo demanda).

Arquitectura:
    WhatsApp del supervisor -> Meta -> [webhook POST /webhook] -> este server
    este server -> ActuadorWhatsApp -> Meta -> WhatsApp del supervisor

Sin dependencias nuevas (http.server de la stdlib). Ejecutar desde la raiz:
    .venv\\Scripts\\python.exe -m src.safesite.servidor_webhook --port 8000

Registro en Meta (una sola vez, lo hace el usuario en el panel):
    App -> WhatsApp -> Configuración -> Webhooks:
      - Callback URL: https://<tunel>/webhook
      - Verify token: safesite_verify   (o env WEBHOOK_VERIFY_TOKEN)
      - Suscribirse al campo "messages"
"""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import config
from .actuarios import ActuadorWhatsApp

TOKEN_VERIFICACION = os.environ.get("WEBHOOK_VERIFY_TOKEN", "safesite_verify")
PALABRAS_INFO = {"info", "métricas", "metricas", "detalle", "detalles", "1"}
PALABRAS_HOLA = {"hola", "hola!", "hi", "buenas"}


def _ultimos_incidentes():
    """Incidentes del ÚLTIMO LOTE: todos comparten t_confirmacion (las
    alertas van consolidadas — un mensaje con todas las faltas del frame)."""
    ruta = os.path.join(config.ARCHIVO_HISTORIAL)
    if not os.path.exists(ruta):
        return []
    lineas = [ln for ln in open(ruta, encoding="utf-8").read().splitlines()
              if ln.strip()]
    if not lineas:
        return []
    ultimo = json.loads(lineas[-1])
    t_lote = ultimo["t_confirmacion"]
    lote = []
    for ln in reversed(lineas):
        inc = json.loads(ln)
        if inc["t_confirmacion"] == t_lote:
            lote.append(inc)
        else:
            break
    return lote


def _texto_metricas(lote):
    """El detalle técnico 'bajo demanda' del mensaje natural (lote completo)."""
    if not lote:
        return ("Todavía no hay alertas registradas en esta sesión. "
                "Cuando ocurra un incumplimiento te avisaré primero. 🚨")
    lineas = [
        f"📊 Detalle técnico de la última alerta ({lote[0]['hora_local']}):",
        "",
        f"• Incumplimientos detectados: {len(lote)}",
    ]
    for inc in lote:
        lineas.append(f"   - {inc['clase']}: confianza {inc['conf_media']:.0%}")
    lineas += [
        f"• Zona: {lote[0]['zona']}",
        f"• Confirmación temporal: {lote[0]['frames_consecutivos']} frames "
        f"consecutivos (regla K={config.K_FRAMES_CONFIRMACION})",
        f"• Umbral de las clases no_*: {config.UMBRAL_INCUMPLIMIENTO:.0%}",
        f"• Cooldown entre alertas repetidas: {config.COOLDOWN_S:.0f} s",
        f"• Modelo: {os.path.basename(os.path.dirname(os.path.dirname(config.RUTA_MODELO)))}",
        "",
        "Si el incumplimiento sigue activo te volveré a alertar cuando "
        "el cooldown lo permita.",
    ]
    return "\n".join(lineas)


class Manejador(BaseHTTPRequestHandler):
    """Webhook de Meta: verificación (GET) y mensajes entrantes (POST)."""

    def _responder(self, codigo, cuerpo, tipo="text/plain"):
        cuerpo_b = cuerpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", f"{tipo}; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo_b)))
        self.end_headers()
        self.wfile.write(cuerpo_b)

    def do_GET(self):  # verificación del webhook (Meta manda hub.challenge)
        q = parse_qs(urlparse(self.path).query)
        if (q.get("hub.mode") == ["subscribe"]
                and q.get("hub.verify_token") == [TOKEN_VERIFICACION]):
            print("✅ Meta verificó el webhook (challenge respondido)")
            self._responder(200, q["hub.challenge"][0])
        else:
            self._responder(403, "token de verificacion incorrecto")

    def do_POST(self):  # mensajes entrantes del supervisor
        try:
            longitud = int(self.headers.get("Content-Length", 0))
            datos = json.loads(self.rfile.read(longitud) or b"{}")
        except (ValueError, json.JSONDecodeError):
            self._responder(200, "EVENTO RECIBIDO")  # nunca encolar reintentos
            return
        try:
            self._procesar_evento(datos)
        except Exception as e:
            print(f"⚠️ error procesando webhook: {e}")
        # Meta solo necesita un 200 rápido (si no, reintenta)
        self._responder(200, "EVENTO RECIBIDO")

    def _procesar_evento(self, datos):
        for entrada in datos.get("entry", []):
            for cambio in entrada.get("changes", []):
                valor = cambio.get("value", {})
                # estados de entrega de NUESTROS envios (sent/delivered/
                # failed/read) — diagnostico E37: sin esto, un mensaje
                # aceptado por la API pero no entregado es invisible
                for estado in valor.get("statuses", []):
                    errores = estado.get("errors") or []
                    extra = ""
                    if errores:
                        extra = " — errores: " + "; ".join(
                            f"{e.get('code')} {e.get('title')}"
                            for e in errores)
                    print(f"📤 estado de mensaje "
                          f"{str(estado.get('id', ''))[:30]}...: "
                          f"{estado.get('status')}{extra}", flush=True)
                for msj in valor.get("messages", []):
                    if msj.get("type") != "text":
                        continue
                    remitente = msj.get("from")
                    texto = (msj.get("text", {}).get("body", "")
                             ).strip().lower()
                    print(f"📩 mensaje entrante de {remitente}: '{texto}'")
                    act = ActuadorWhatsApp()
                    if act.modo != "ENVIO-REAL":
                        print("   (sin credenciales; no se puede responder)")
                        continue
                    if texto in PALABRAS_INFO:
                        act.enviar_texto(_texto_metricas(_ultimos_incidentes()),
                                         para=remitente)
                        print("   -> métricas del lote enviadas")
                    elif texto in PALABRAS_HOLA:
                        act.enviar_texto(
                            "¡Hola! Soy SafeSite-Agent 👷 Estoy vigilando el "
                            "uso de EPP. Si quieres el detalle técnico de mi "
                            "última alerta, respóndeme INFO.",
                            para=remitente)
                    else:
                        act.enviar_texto(
                            "Solo entiendo INFO (detalle técnico de la última "
                            "alerta) por ahora 🙂",
                            para=remitente)

    def log_message(self, formato, *args):
        pass  # silenciar el log por defecto (ya imprimimos lo relevante)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    servidor = ThreadingHTTPServer(("0.0.0.0", args.port), Manejador)
    print(f"🛰️  Webhook escuchando en http://localhost:{args.port}/webhook")
    print(f"   Verify token: {TOKEN_VERIFICACION}")
    print("   Esperando mensajes entrantes de Meta (Ctrl+C para parar)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")


if __name__ == "__main__":
    main()
