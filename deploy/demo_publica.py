"""SafeSite-Agent — demo pública desde el PC, sin costos (página + túnel).

Hugging Face ya no hospeda gratis los Spaces de Gradio (el tier cpu-basic
pide suscripción PRO; el intento de subida terminó en 402 Payment
Required, BITACORA E48). Esta es la alternativa gratuita: la página corre
en el PC — la GPU local procesa más rápido que el CPU del Space — y
cloudflared la publica en una URL https pública, el mismo mecanismo del
túnel que ya usa el modo piloto.

Qué hace:
1. Busca un puerto local libre (desde el 7860) — no mata procesos ajenos
   (lección E15/E16), así puede convivir con la sesión que ya tengas.
2. Levanta deploy/app.py como subprocess (acepta --tema y --device).
3. Espera a que la página responda en local (importar torch tarda un poco).
4. Levanta el túnel cloudflared (--protocol http2: QUIC/UDP degradado en
   redes LATAM, BITACORA E24) y captura la URL pública.
5. Verifica que la URL responde desde fuera ANTES de anunciarla y la
   deja en pantalla y en runs/agente/demo_url.txt.

La URL dura mientras no cierres este proceso (Ctrl+C); al reiniciar,
saldrá una nueva. Es https, así que la webcam de la demo funciona desde
cualquier navegador, incluido el celular.

Ejecutar desde la RAIZ del proyecto:
    .venv\\Scripts\\python.exe deploy\\demo_publica.py
    .venv\\Scripts\\python.exe deploy\\demo_publica.py --tema rosa
    .venv\\Scripts\\python.exe deploy\\demo_publica.py --device cpu
"""
import argparse
import os
import re
import socket
import subprocess
import sys
import threading
import time
import urllib.request

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
RUTA_URL = os.path.join(RAIZ, "runs", "agente", "demo_url.txt")


def _rutar_cloudflared():
    """cloudflared instalado, el que usa el piloto, o nada (con aviso)."""
    candidatos = [
        os.environ.get("CLOUDFLARED", ""),
        r"C:\Program Files (x86)\cloudflared\cloudflared.exe",
        r"C:\Users\Lenovo\AppData\Local\Temp\opencode\cloudflared.exe",
    ]
    for ruta in candidatos:
        if ruta and os.path.exists(ruta):
            return ruta
    raise SystemExit(
        "No se encontró cloudflared. Instálalo con:\n"
        "    winget install --id Cloudflare.cloudflared\n"
        "y vuelve a correr este script.")


def _log(msg):
    print(msg, flush=True)


def _puerto_libre(desde=7860, hasta=7870):
    for puerto in range(desde, hasta + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", puerto))
                return puerto
            except OSError:
                _log(f"   puerto {puerto} ocupado, probando el siguiente…")
    raise SystemExit(f"No hay puertos libres entre {desde} y {hasta}.")


def _esperar_http(url, max_s, cada_s=2.0):
    """True en cuanto la url responde; False si se agota el plazo."""
    inicio = time.time()
    while time.time() - inicio < max_s:
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(cada_s)
    return False


def _iniciar_tunel(puerto):
    """Levanta cloudflared (http2) y devuelve (proceso, url_publica)."""
    proc = subprocess.Popen(
        [_rutar_cloudflared(), "tunnel", "--url", f"http://localhost:{puerto}",
         "--protocol", "http2"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace",
        creationflags=0x08000000)  # CREATE_NO_WINDOW
    url_holder = {}
    inicio = time.time()

    def _leer():
        for linea in proc.stdout:
            limpia = re.sub(r"\x1b\[[0-9;]*m", "", linea.rstrip())
            if "ERR" in limpia:
                _log(f"   [tunel] {limpia}")
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", limpia)
            if m:
                url_holder["url"] = m.group(0)

    hilo = threading.Thread(target=_leer, daemon=True)
    hilo.start()
    while not url_holder.get("url") and time.time() - inicio < 45:
        time.sleep(0.5)
    if not url_holder.get("url"):
        proc.terminate()
        raise SystemExit("El túnel no entregó URL en 45 s "
                         "(¿internet caída? ¿bloqueo del ISP?).")
    return proc, url_holder["url"]


def _detener(proc):
    """Apaga un proceso y su árbol, sin tocar procesos ajenos."""
    try:
        subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                       capture_output=True)
    except Exception as e:
        _log(f"   (al detener pid {proc.pid}: {e})")


def main():
    parser = argparse.ArgumentParser(
        description="Demo pública de SafeSite-Agent: página local + túnel.")
    parser.add_argument("--tema", default=None,
                        help="tema de la página: esmeralda (default), "
                             "grafito, rosa, ambar, azul, ocean o neon")
    parser.add_argument("--device", default="0",
                        help="donde corre la inferencia: 0 (GPU, default) "
                             "o cpu")
    parser.add_argument("--puerto", type=int, default=None,
                        help="puerto local fijo; por defecto se busca uno "
                             "libre desde el 7860")
    args = parser.parse_args()

    # consolas cp1252 no imprimen emojis (lección E36)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    _log("=== SAFESITE-AGENT · DEMO PÚBLICA ===")
    puerto = args.puerto or _puerto_libre()
    _log(f"1/4 página local en el puerto {puerto} "
         f"(GPU device={args.device}, tema={args.tema or 'esmeralda'})…")
    env = os.environ.copy()
    env["SAFESITE_PUERTO"] = str(puerto)
    env["SAFESITE_DEVICE"] = args.device
    cmd = [sys.executable, os.path.join(AQUI, "app.py")]
    if args.tema:
        cmd += ["--tema", args.tema]
    app = subprocess.Popen(cmd, cwd=RAIZ, env=env)

    if not _esperar_http(f"http://localhost:{puerto}", max_s=180):
        _detener(app)
        raise SystemExit(f"La página no respondió en {puerto} tras 3 min; "
                         "revisa los mensajes que imprimió arriba.")
    _log(f"   página arriba en http://localhost:{puerto}")

    _log("2/4 túnel público (http2, igual que el piloto)…")
    tunel, url_publica = _iniciar_tunel(puerto)

    _log("3/4 verificando que la URL responde desde fuera…")
    if _esperar_http(url_publica, max_s=90, cada_s=3.0):
        _log("   URL pública verificada ✅")
    else:
        _log("   la URL aún no responde (DNS del túnel lento); "
             "suele bastar esperar un minuto y recargar")

    os.makedirs(os.path.dirname(RUTA_URL), exist_ok=True)
    with open(RUTA_URL, "w", encoding="utf-8") as f:
        f.write(url_publica)

    _log("4/4 listo.\n")
    _log("🟢 DEMO PÚBLICA ACTIVA")
    _log(f"   → {url_publica}")
    _log(f"   (copia también en {os.path.relpath(RUTA_URL, RAIZ)})")
    _log("   Deja esta consola abierta: la URL vive mientras este proceso")
    _log("   no se detenga. Ctrl+C para terminar.")
    try:
        tunel.wait()
    except KeyboardInterrupt:
        pass
    finally:
        _log("\n🛑 deteniendo la demo (página y túnel)…")
        _detener(tunel)
        _detener(app)
        _log("   todo detenido.")


if __name__ == "__main__":
    main()
