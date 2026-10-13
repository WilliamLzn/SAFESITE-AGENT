"""SafeSite-Agent — Actuadores: canales de salida de las alertas.

- ActuadorConsola: imprime la alerta y guarda el frame anotado (evidencia
  para el panel de supervision).
- ActuadorWhatsApp: prepara el payload exacto del mensaje para la API de
  WhatsApp Business Cloud (Meta) y lo deja listo/envia si hay credenciales.

NOTA de despliegue (Fase 4 del roadmap): para enviar de verdad se requieren
credenciales de Meta (WHATSAPP_TOKEN y WHATSAPP_PHONE_ID de una app en
developers.facebook.com + plantilla de mensaje aprobada). Sin credenciales,
el actuador opera en modo DRY-RUN: construye el mensaje y lo registra.
"""
import os

from . import config


class ActuadorBase:
    nombre = "base"

    def alertar(self, incidente, frame_anotado=None, ruta_frame=None):
        raise NotImplementedError


class ActuadorConsola(ActuadorBase):
    """Alerta legible en consola + persistencia del frame anotado."""

    nombre = "consola"

    def __init__(self, dir_alertas=None):
        self.dir = dir_alertas or config.DIR_ALERTAS
        os.makedirs(self.dir, exist_ok=True)

    def alertar(self, incidente, frame_anotado=None, ruta_frame=None):
        print(f"\n🚨 ALERTA [{self.nombre}] "
              f"zona={incidente.zona} clase={incidente.clase} "
              f"conf={incidente.conf_media:.2f} "
              f"frames={incidente.frames_consecutivos} "
              f"hora={getattr(incidente, 'hora', '')}".strip())
        if frame_anotado is not None:
            import cv2
            nombre = (f"{incidente.zona}_{incidente.clase}_"
                      f"{int(incidente.t_confirmacion)}.jpg").replace(":", "-")
            destino = os.path.join(self.dir, nombre)
            cv2.imwrite(destino, frame_anotado)
            return destino
        return ruta_frame


class ActuadorWhatsApp(ActuadorBase):
    """Announcer de WhatsApp Business Cloud API (modo DRY-RUN sin credenciales).

    Plantilla del mensaje (los parametros se mapean 1:1 a la API de Meta):
      template: alerta_epp  |  lenguage: es
      params: [zona, clase_de_epp_faltante, hora_local, conf]
    Adjunto: frame anotado del incidente (media del mensaje).
    """

    nombre = "whatsapp"

    def __init__(self, telefono_destinatario=None,
                 token_env="WHATSAPP_TOKEN", phone_id_env="WHATSAPP_PHONE_ID"):
        import os as _os
        self.destinatario = telefono_destinatario
        self.token = _os.environ.get(token_env)
        self.phone_id = _os.environ.get(phone_id_env)

    @property
    def modo(self):
        return "ENVIO-REAL" if (self.token and self.phone_id) else "DRY-RUN"

    def construir_payload(self, incidente):
        from datetime import datetime
        return {
            "messaging_product": "whatsapp",
            "to": self.destinatario or "<numero_supervisor_hse>",
            "type": "template",
            "template": {
                "name": "alerta_epp",
                "language": {"code": "es"},
                "components": [{
                    "type": "body",
                    "parameters": [
                        {"type": "text", "text": incidente.zona},
                        {"type": "text", "text": incidente.clase},
                        {"type": "text",
                         "text": datetime.fromtimestamp(
                             incidente.t_confirmacion).strftime("%H:%M:%S")},
                        {"type": "text",
                         "text": f"{incidente.conf_media:.0%}"},
                    ],
                }],
            },
        }

    def alertar(self, incidente, frame_anotado=None, ruta_frame=None):
        payload = self.construir_payload(incidente)
        print(f"📲 WhatsApp[{self.modo}] -> payload listo: {payload}")
        if self.modo == "ENVIO-REAL":
            import requests
            url = (f"https://graph.facebook.com/v21.0/{self.phone_id}/messages")
            resp = requests.post(
                url, json=payload,
                headers={"Authorization": f"Bearer {self.token}"}, timeout=15)
            print(f"   respuesta API: {resp.status_code}")
            return resp.status_code
        return None
