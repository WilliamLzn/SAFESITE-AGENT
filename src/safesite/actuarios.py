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

    def alertar_lote(self, incidentes, frame_anotado=None, ruta_frame=None):
        """Alerta consolidada: TODOS los incumplimientos del frame en un
        solo mensaje (optimiza mensajes y llamadas a la API). Por defecto
        degrada a alertas individuales."""
        for inc in incidentes:
            self.alertar(inc, frame_anotado=frame_anotado, ruta_frame=ruta_frame)


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

    def alertar_lote(self, incidentes, frame_anotado=None, ruta_frame=None):
        hora = getattr(incidentes[0], "hora", "")
        resumen = ", ".join(f"{i.clase} ({i.conf_media:.0%})"
                            for i in incidentes)
        print(f"\n🚨 ALERTA [{self.nombre}] zona={incidentes[0].zona} "
              f"lote={len(incidentes)}: {resumen} {hora}".strip())
        destino = None
        if frame_anotado is not None:
            import cv2
            nombre = (f"{incidentes[0].zona}_lote_"
                      f"{int(incidentes[0].t_confirmacion)}.jpg").replace(":", "-")
            destino = os.path.join(self.dir, nombre)
            cv2.imwrite(destino, frame_anotado)
            print(f"   evidencia: {destino}")
        return destino


class ActuadorWhatsApp(ActuadorBase):
    """Announcer de WhatsApp Business Cloud API (Meta).

    Credenciales por variables de entorno (NUNCA en el codigo/git):
      - WHATSAPP_TOKEN         (token de System User, permanente)
      - WHATSAPP_PHONE_ID      (ID del numero de la app)
      - WHATSAPP_DESTINATARIO  (celular del supervisor, ej. 573185469893)

    Modo de envio: texto libre + IMAGEN del frame anotado (valido con el
    numero de prueba de Meta hacia los destinatarios permitidos). Para pasar
    a produccion (numero de negocio real) se usara la plantilla `alerta_epp`
    aprobada por Meta (metodo construir_payload, ya implementado).

    Flujo de la imagen (API Cloud, 2 pasos):
      1) POST /{phone_id}/media   -> sube el JPEG y devuelve media_id
      2) POST /{phone_id}/messages -> envia el mensaje con image.id + caption
    Si la subida falla, degrada a texto puro: la alerta nunca se pierde.
    """

    nombre = "whatsapp"
    API_VERSION = "v21.0"

    def __init__(self, telefono_destinatario=None,
                 token_env="WHATSAPP_TOKEN", phone_id_env="WHATSAPP_PHONE_ID"):
        self.destinatario = telefono_destinatario or os.environ.get(
            "WHATSAPP_DESTINATARIO")
        self.token = os.environ.get(token_env)
        self.phone_id = os.environ.get(phone_id_env)
        self.tiempos_envio_ms = []

    @property
    def modo(self):
        return "ENVIO-REAL" if (self.token and self.phone_id
                                and self.destinatario) else "DRY-RUN"

    # ---------- capa HTTP ----------

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def _url(self, ruta):
        return (f"https://graph.facebook.com/{self.API_VERSION}/"
                f"{self.phone_id}/{ruta}")

    def _post(self, ruta, json=None, data=None, files=None):
        import requests
        import time
        t0 = time.perf_counter()
        resp = requests.post(self._url(ruta), headers=self._headers(),
                             json=json, data=data, files=files, timeout=30)
        self.tiempos_envio_ms.append((time.perf_counter() - t0) * 1000)
        return resp

    # ---------- envios ----------

    def enviar_texto(self, texto, para=None):
        """Envia un mensaje de texto libre (a `para` o al destinatario de config)."""
        resp = self._post("messages", json={
            "messaging_product": "whatsapp", "to": para or self.destinatario,
            "type": "text", "text": {"body": texto},
        })
        resp.raise_for_status()
        return resp.json()["messages"][0]["id"]

    def subir_imagen_bytes(self, jpeg_bytes, nombre="alerta.jpg"):
        """Paso 1: sube el JPEG (en memoria) y devuelve el media_id."""
        resp = self._post("media", data={"messaging_product": "whatsapp",
                                         "type": "image"},
                          files={"file": (nombre, jpeg_bytes, "image/jpeg")})
        resp.raise_for_status()
        return resp.json()["id"]

    def enviar_imagen(self, media_id, caption):
        """Paso 2: envia el mensaje con la imagen subida + caption."""
        resp = self._post("messages", json={
            "messaging_product": "whatsapp", "to": self.destinatario,
            "type": "image", "image": {"id": media_id, "caption": caption},
        })
        resp.raise_for_status()
        return resp.json()["messages"][0]["id"]

    # ---------- interfaz del actuador ----------

    # Lenguaje natural por clase de incumplimiento (para el mensaje al supervisor)
    DESCRIPCION_NATURAL = {
        7: "un trabajador SIN CASCO",
        8: "un trabajador SIN GAFAS de protección",
        9: "un trabajador SIN GUANTES",
        10: "un trabajador SIN BOTAS de seguridad",
    }

    @staticmethod
    def _resumen_lote(incidentes):
        """Frase natural con todas las faltas del frame (1 o varias)."""
        faltas = [ActuadorWhatsApp.DESCRIPCION_NATURAL.get(
            inc.clase_id, f"incumplimiento de EPP ({inc.clase})")
            for inc in incidentes]
        zona = incidentes[0].zona
        if len(incidentes) == 1:
            return f"Detectamos {faltas[0]} en la zona {zona}."
        lista = "\n".join(f"• {f.title()}" for f in faltas)
        return (f"Detectamos varios incumplimientos de EPP en la zona "
                f"{zona}:\n{lista}")

    @staticmethod
    def _caption(incidente):
        """Mensaje natural (no técnico) que acompaña la foto (alerta individual)."""
        from datetime import datetime
        descripcion = ActuadorWhatsApp.DESCRIPCION_NATURAL.get(
            incidente.clase_id, f"un incumplimiento de EPP ({incidente.clase})")
        hora = datetime.fromtimestamp(
            incidente.t_confirmacion).strftime("%I:%M %p").lstrip("0")
        return (
            f"🚨 Alerta SafeSite — {hora}\n\n"
            f"Detectamos {descripcion} en la zona {incidente.zona}.\n\n"
            f"📸 Te adjuntamos la foto del momento.\n\n"
            f"_Responde_ **INFO** _si quieres ver el detalle técnico._"
        )

    @staticmethod
    def _caption_lote(incidentes):
        """Mensaje natural consolidado: todas las faltas en un solo caption."""
        from datetime import datetime
        hora = datetime.fromtimestamp(
            incidentes[0].t_confirmacion).strftime("%I:%M %p").lstrip("0")
        return (
            f"🚨 Alerta SafeSite — {hora}\n\n"
            f"{ActuadorWhatsApp._resumen_lote(incidentes)}\n\n"
            f"📸 Te adjuntamos la foto del momento.\n\n"
            f"_Responde_ **INFO** _si quieres ver el detalle técnico._"
        )

    def alertar(self, incidente, frame_anotado=None, ruta_frame=None):
        caption = self._caption(incidente)
        if self.modo != "ENVIO-REAL":
            print(f"📲 WhatsApp[DRY-RUN] -> {caption} "
                  f"(sin credenciales en el entorno)")
            return None

        # 1) intentar con la imagen del frame anotado
        if frame_anotado is not None:
            try:
                import cv2
                ok, buf = cv2.imencode(".jpg", frame_anotado,
                                       [cv2.IMWRITE_JPEG_QUALITY, 85])
                if not ok:
                    raise RuntimeError("cv2.imencode fallo")
                media_id = self.subir_imagen_bytes(buf.tobytes(),
                                                   nombre="safesite_alerta.jpg")
                wamid = self.enviar_imagen(media_id, caption)
                print(f"📲 WhatsApp[ENVIO-REAL] imagen+caption enviado "
                      f"(wamid {wamid[:18]}...)")
                return wamid
            except Exception as e:
                print(f"⚠️ WhatsApp: fallo el envio con imagen ({e}); "
                      f"degradando a texto puro")

        # 2) fallback: texto puro (la alerta nunca se pierde)
        try:
            wamid = self.enviar_texto(caption)
            print(f"📲 WhatsApp[ENVIO-REAL] texto enviado "
                  f"(wamid {wamid[:18]}...)")
            return wamid
        except Exception as e:
            print(f"❌ WhatsApp: fallo tambien el envio de texto: {e}")
            return None

    def alertar_lote(self, incidentes, frame_anotado=None, ruta_frame=None):
        """Alerta CONSOLIDADA: un solo mensaje con todas las faltas del frame
        y una sola foto (optimiza mensajes, llamadas API y latencia)."""
        caption = self._caption_lote(incidentes)
        if self.modo != "ENVIO-REAL":
            print(f"📲 WhatsApp[DRY-RUN] lote ({len(incidentes)} faltas) -> "
                  f"{caption[:120]}...")
            return None

        if frame_anotado is not None:
            try:
                import cv2
                ok, buf = cv2.imencode(".jpg", frame_anotado,
                                       [cv2.IMWRITE_JPEG_QUALITY, 85])
                if not ok:
                    raise RuntimeError("cv2.imencode fallo")
                media_id = self.subir_imagen_bytes(buf.tobytes(),
                                                   nombre="safesite_alerta.jpg")
                wamid = self.enviar_imagen(media_id, caption)
                print(f"📲 WhatsApp[ENVIO-REAL] lote {len(incidentes)} faltas, "
                      f"imagen+caption enviado (wamid {wamid[:18]}...)")
                return wamid
            except Exception as e:
                print(f"⚠️ WhatsApp: fallo el lote con imagen ({e}); "
                      f"degradando a texto puro")

        try:
            wamid = self.enviar_texto(caption)
            print(f"📲 WhatsApp[ENVIO-REAL] lote {len(incidentes)} faltas, "
                  f"texto enviado (wamid {wamid[:18]}...)")
            return wamid
        except Exception as e:
            print(f"❌ WhatsApp: fallo tambien el texto del lote: {e}")
            return None

    # ---------- plantilla (produccion con numero de negocio real) ----------

    def construir_payload(self, incidente):
        """Payload con plantilla `alerta_epp` (requerida en produccion)."""
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
