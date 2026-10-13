"""SafeSite-Agent — núcleo del agente de monitoreo de EPP.

Modulos:
- config: umbrales por clase, K de confirmacion, cooldown, rutas
- percepcion: fuentes de frames + inferencia YOLO + anotacion
- razonamiento: reglas temporales (K frames consecutivos) sobre clases no_*
- memoria: cooldown anti-spam + historial persistente de incidentes
- actuarios: consola/panel + announcer de WhatsApp Business
- agente: orquestador del ciclo percibir -> razonar -> actuar
"""

import os

__version__ = "0.1.0"


def _cargar_env():
    """Carga credenciales desde .env (si existe) sin sobreescribir el entorno.

    El .env vive en la RAIZ del proyecto y esta en .gitignore: los secretos
    (WHATSAPP_TOKEN, etc.) jamas se versionan. Las variables de entorno reales
    tienen prioridad sobre el archivo (os.environ.setdefault).
    """
    raiz = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    ruta = os.path.join(raiz, ".env")
    if not os.path.exists(ruta):
        return
    # utf-8-sig: en Windows, PowerShell/escribores suelen anteponer BOM
    # (EF BB BF); utf-8-sig lo elimina y tambien lee utf-8 plano.
    with open(ruta, encoding="utf-8-sig") as f:
        for linea in f:
            linea = linea.strip()
            if not linea or linea.startswith("#") or "=" not in linea:
                continue
            clave, valor = linea.split("=", 1)
            os.environ.setdefault(clave.strip(), valor.strip())


_cargar_env()
