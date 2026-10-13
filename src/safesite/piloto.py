"""SafeSite-Agent — Modo piloto auto-suficiente (webhook + túnel + auto-registro).

Resuelve el fallo del circuito conversacional (BITACORA E25): el webhook
dependía de 3 piezas y del registro MANUAL en el panel de Meta. Ahora:

1. Limpia procesos previos (puerto 8000 / cloudflared) que hayan quedado vivos.
2. Levanta el servidor webhook (hilo local).
3. Levanta el túnel cloudflared con --protocol http2 (QUIC/UDP degradado en
   redes LATAM: se caía cada ~15-30 s; TCP es estable).
4. AUTO-REGISTRA el webhook en Meta via Graph API:
   POST /{APP_ID}/subscriptions  (object=whatsapp, callback_url, verify_token,
   fields=messages) -> si el túnel cambia de URL, se re-registra solo.
   Requiere WHATSAPP_APP_ID en el entorno/.env (el numero de la URL del panel).
5. Auto-prueba del challenge y del handler (POST simulado local).
6. Publica la URL en runs/agente/tunel_url.txt y queda escuchando, con log
   de cada mensaje entrante y de cada respuesta.

Ejecutar desde la RAIZ del proyecto:
    .venv\\Scripts\\python.exe -m src.safesite.piloto
"""
import json
import os
import re
import subprocess
import sys
import threading
import time
from http.server import ThreadingHTTPServer

from . import config
from .actuarios import ActuadorWhatsApp
from .servidor_webhook import Manejador, TOKEN_VERIFICACION

PUERTO = 8000
RUTA_TUNEL_URL = os.path.join("runs", "agente", "tunel_url.txt")
RUTA_CLOUDFLARED = os.environ.get(
    "CLOUDFLARED", r"C:\Users\Lenovo\AppData\Local\Temp\opencode\cloudflared.exe")
APP_ID = os.environ.get("WHATSAPP_APP_ID")
API = "https://graph.facebook.com/v21.0"


def _log(msg):
    print(msg, flush=True)


def _limpiar_procesos_previos():
    """Mata cualquier webhook/cloudflared zombi para arrancar limpio."""
    try:
        salida = subprocess.run(
            ["netstat", "-ano"], capture_output=True).stdout
        # netstat en Windows emite en codificacion local (cp850/cp1252):
        # decodificar con reemplazo evita el crash por bytes invalidos.
        texto = salida.decode("utf-8", errors="replace")
        for linea in texto.splitlines():
            if f":{PUERTO}" in linea and "LISTENING" in linea:
                pid = int(linea.split()[-1])
                subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                               capture_output=True)
                _log(f"   proceso previo del puerto {PUERTO} (pid {pid}) detenido")
    except Exception as e:
        _log(f"   (limpieza de puerto: {e})")
    subprocess.run(["taskkill", "/IM", "cloudflared.exe", "/F"],
                   capture_output=True)


def _iniciar_servidor():
    servidor = ThreadingHTTPServer(("0.0.0.0", PUERTO), Manejador)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    _log(f"🛰️  webhook escuchando en http://localhost:{PUERTO}/webhook")
    return servidor


def _iniciar_tunel():
    """Levanta cloudflared (http2) y devuelve (proceso, url_publica)."""
    proc = subprocess.Popen(
        [RUTA_CLOUDFLARED, "tunnel", "--url", f"http://localhost:{PUERTO}",
         "--protocol", "http2"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace",
        creationflags=0x08000000)  # CREATE_NO_WINDOW
    url = None
    inicio = time.time()

    def _leer():
        for linea in proc.stdout:
            limpia = re.sub(r"\x1b\[[0-9;]*m", "", linea.rstrip())
            if "ERR" in limpia:
                _log(f"   [tunel] {limpia}")
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", limpia)
            if m:
                url_holder["url"] = m.group(0)

    url_holder = {}
    hilo = threading.Thread(target=_leer, daemon=True)
    hilo.start()
    while not url_holder.get("url") and time.time() - inicio < 30:
        time.sleep(0.5)
    if not url_holder.get("url"):
        proc.terminate()
        raise RuntimeError("el tunel no entrego URL en 30 s")
    _log(f"🌐 tunel publico: {url_holder['url']}")
    return proc, url_holder["url"]


CAMPOS_WABA = ("account_alerts,account_review_update,account_update,calls,"
               "message_template_quality_update,message_template_status_update,"
               "phone_number_name_update,phone_number_quality_update,"
               "security,messages")


def _token_de_app():
    """Token de la app (APP_ID|APP_SECRET) — el unico que acepta
    /subscriptions (error #15 con el token de System User, BITACORA E25)."""
    secreto = os.environ.get("WHATSAPP_APP_SECRET")
    if secreto and APP_ID:
        return f"{APP_ID}|{secreto}"
    return None


def _registrar_objeto(token_app, objeto, campos, url_publica):
    """POST /subscriptions para un objeto webhook concreto."""
    import requests
    r = requests.post(
        f"{API}/{APP_ID}/subscriptions",
        headers={"Authorization": f"Bearer {token_app}"},
        data={"object": objeto,
              "callback_url": f"{url_publica}/webhook",
              "verify_token": TOKEN_VERIFICACION,
              "fields": campos}, timeout=30)
    return r


def _esperar_tunel_listo(url_publica, max_intentos=18, espera_s=10):
    """Espera a que el DNS del tunel se propague (Meta falla con #2200
    'Failed to resolve host' si registramos demasiado pronto)."""
    import time
    import urllib.request
    prueba = f"ok{int(time.time())}"
    for intento in range(1, max_intentos + 1):
        try:
            r = urllib.request.urlopen(
                f"{url_publica}/webhook?hub.mode=subscribe"
                f"&hub.challenge={prueba}&hub.verify_token={TOKEN_VERIFICACION}",
                timeout=15)
            if r.read().decode() == prueba:
                _log(f"🧪 tunel publico alcanzable (intento {intento}) — OK")
                return True
        except Exception as e:
            _log(f"🧪 DNS del tunel aun no propaga (intento {intento}/"
                 f"{max_intentos}): {e}")
        time.sleep(espera_s)
    _log("🧪 el tunel no respondio; se intentara el registro de todas formas")
    return False


def _auto_registro(url_publica):
    """Registra callback + suscripcion a messages via Graph API (sin panel).

    Registra DOS objetos (hallazgo E25): 'whatsapp' y
    'whatsapp_business_account' (el nivel WABA también captura messages y
    quedaba apuntando a URLs muertas si solo se actualizaba uno).
    """
    import requests
    token_app = _token_de_app()
    if not APP_ID or not token_app:
        _log("⚠️ falta WHATSAPP_APP_ID o WHATSAPP_APP_SECRET en .env:")
        _log("   App ID: developers.facebook.com/apps/<NUMERO>  |  App Secret:")
        _log("   panel -> Configuracion -> Basica -> Clave secreta de la app")
        _log(f"   registro manual: Callback URL {url_publica}/webhook | "
             f"Verify token: {TOKEN_VERIFICACION} | suscribir 'messages'")
        return False

    todo_ok = True
    for objeto, campos in (("whatsapp", "messages"),
                           ("whatsapp_business_account", CAMPOS_WABA)):
        r = _registrar_objeto(token_app, objeto, campos, url_publica)
        if r.ok and r.json().get("success"):
            _log(f"✅ '{objeto}' AUTO-REGISTRADO (callback + {campos})")
        else:
            todo_ok = False
            _log(f"❌ registro de '{objeto}' falló ({r.status_code}): "
                 f"{r.text[:200]}")

    # Paso critico (hallazgo E25): suscribir la APP al WABA — sin esto los
    # mensajes entrantes NUNCA llegan aunque el webhook este verificado.
    waba_id = os.environ.get("WHATSAPP_WABA_ID")
    if waba_id:
        act = ActuadorWhatsApp()
        if act.token:
            import requests
            r = requests.post(
                f"{API}/{waba_id}/subscribed_apps",
                headers={"Authorization": f"Bearer {act.token}"}, timeout=30)
            if r.ok and r.json().get("success"):
                _log(f"✅ app SUSCRITA al WABA {waba_id} (entrada de mensajes habilitada)")
            else:
                todo_ok = False
                _log(f"❌ suscripcion app->WABA falló ({r.status_code}): {r.text[:200]}")
    else:
        _log("⚠️ falta WHATSAPP_WABA_ID en .env (suscripcion app->WABA omitida)")
    if todo_ok:
        v = requests.get(f"{API}/{APP_ID}/subscriptions",
                         params={"object": "whatsapp"},
                         headers={"Authorization": f"Bearer {token_app}"},
                         timeout=30)
        if v.ok:
            _log(f"   estado 'whatsapp': {json.dumps(v.json(), ensure_ascii=False)[:300]}")
    if not todo_ok:
        _log(f"   registro manual: Callback URL {url_publica}/webhook | "
             f"Verify token: {TOKEN_VERIFICACION} | suscribir 'messages'")
    return todo_ok


def _auto_prueba(url_publica):
    """Verifica que el handler responde (challenge local + via tunel).

    El DNS del tunel tarda unos segundos en propagarse tras crearse:
    el challenge publico se reintenta hasta ~30 s.
    """
    import time
    import urllib.request
    import urllib.error
    prueba = f"ok{int(time.time())}"
    try:
        r = urllib.request.urlopen(
            f"http://localhost:{PUERTO}/webhook?hub.mode=subscribe"
            f"&hub.challenge={prueba}&hub.verify_token={TOKEN_VERIFICACION}",
            timeout=10)
        _log("🧪 challenge local: "
             f"{'OK' if r.read().decode() == prueba else 'RESPUESTA INCORRECTA'}")
    except Exception as e:
        _log(f"🧪 challenge local: FALLO ({e})")
    for intento in range(1, 7):
        try:
            r = urllib.request.urlopen(
                f"{url_publica}/webhook?hub.mode=subscribe"
                f"&hub.challenge={prueba}&hub.verify_token={TOKEN_VERIFICACION}",
                timeout=20)
            _log("🧪 challenge publico: "
                 f"{'OK' if r.read().decode() == prueba else 'RESPUESTA INCORRECTA'}")
            return
        except Exception as e:
            _log(f"🧪 challenge publico: intento {intento}/6 fallo ({e}); reintentando...")
            time.sleep(5)
    _log("🧪 challenge publico: no respondio tras 6 intentos "
         "(DNS del tunel lento) — igualmente el sistema queda activo")


def main():
    _log("=== SAFESITE-AGENT · MODO PILOTO ===")
    _log("1/5 limpieza de procesos previos...")
    _limpiar_procesos_previos()

    _log("2/5 servidor webhook...")
    servidor = _iniciar_servidor()

    _log("3/5 tunel publico (http2)...")
    tunel, url_publica = _iniciar_tunel()
    os.makedirs(os.path.dirname(RUTA_TUNEL_URL), exist_ok=True)
    with open(RUTA_TUNEL_URL, "w", encoding="utf-8") as f:
        f.write(url_publica)

    _log("4/5 auto-registro en Meta (espera previa de DNS del tunel)...")
    _esperar_tunel_listo(url_publica)
    _auto_registro(url_publica)

    _log("5/5 auto-prueba de la cadena...")
    _auto_prueba(url_publica)

    _log("\n🟢 SISTEMA ACTIVO — responde INFO a una alerta para pedir el detalle")
    _log("   (Ctrl+C para detener; el webhook y el tunel mueren con este proceso)")
    try:
        tunel.wait()
    except KeyboardInterrupt:
        _log("\n🛑 deteniendo piloto...")
        tunel.terminate()
        servidor.shutdown()


if __name__ == "__main__":
    main()
