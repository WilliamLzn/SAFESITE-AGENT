"""SafeSite-Agent — Memoria: cooldown anti-spam e historial persistente.

Roles (segun el documento de diseno del agente):
- memoria de corto plazo: evitar notificaciones duplicadas por (zona, clase)
  dentro de una ventana de cooldown;
- historial: registro persistente de incidentes por zona/horario
  (insumo para priorizar patrones recurrentes — componente de utilidad).
"""
import json
import os
import time

from . import config


class Memoria:
    def __init__(self, cooldown_s=None, archivo_historial=None):
        self.cooldown = cooldown_s if cooldown_s is not None else config.COOLDOWN_S
        self.archivo = archivo_historial or config.ARCHIVO_HISTORIAL
        self._ultimas_alertas = {}   # (zona, clase_id) -> t_stamp de la ultima alerta

    def debe_alertar(self, incidente, t_stamp=None):
        """True si el cooldown de (zona, clase) ya vencio (o nunca se alerto)."""
        t = t_stamp if t_stamp is not None else incidente.t_confirmacion
        clave = (incidente.zona, incidente.clase_id)
        t_previa = self._ultimas_alertas.get(clave)
        if t_previa is not None and (t - t_previa) < self.cooldown:
            return False
        return True

    def registrar_alerta(self, incidente, t_stamp=None):
        """Marca la alerta como emitida y persiste el incidente en historial."""
        t = t_stamp if t_stamp is not None else incidente.t_confirmacion
        self._ultimas_alertas[(incidente.zona, incidente.clase_id)] = t
        os.makedirs(os.path.dirname(self.archivo), exist_ok=True)
        with open(self.archivo, "a", encoding="utf-8") as f:
            f.write(json.dumps(incidente.como_dict(), ensure_ascii=False) + "\n")

    @property
    def historial(self):
        """Lee el historial persistido (lista de dicts)."""
        if not os.path.exists(self.archivo):
            return []
        salida = []
        with open(self.archivo, encoding="utf-8") as f:
            for linea in f:
                if linea.strip():
                    salida.append(json.loads(linea))
        return salida
