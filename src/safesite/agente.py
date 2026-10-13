"""SafeSite-Agent — Orquestador del ciclo percibir -> razonar -> actuar.

El agente es un agente reactivo basado en modelos (model-based reflex) con
componente de utilidad, segun el documento de diseno del proyecto:
percibe fotogramas, mantiene estado interno (rachas por zona/clase + cooldown)
y actua mediante actuadores cuando confirma un incumplimiento.
"""
import time

from . import config
from .memoria import Memoria
from .percepcion import Percepcion
from .razonamiento import Razonamiento
from .actuarios import ActuadorConsola, ActuadorWhatsApp


class SafeSiteAgent:
    def __init__(self, ruta_modelo=None, device=None,
                 actuadores=None, cooldown_s=None, guardar_frames=True):
        self.percepcion = Percepcion(ruta_modelo=ruta_modelo, device=device)
        self.razonamiento = Razonamiento()
        self.memoria = Memoria(cooldown_s=cooldown_s)
        self.guardar_frames = guardar_frames
        self.actuadores = actuadores or [ActuadorConsola(), ActuadorWhatsApp()]
        self.latencias_ms = []       # metrica: tiempo end-to-end por frame
        self.alertas_emitidas = 0
        self.alertas_bloqueadas_cooldown = 0

    def procesar_frame(self, frame, zona, t_stamp=None, origen=""):
        """Un ciclo completo del agente sobre un fotograma."""
        t0 = time.perf_counter()
        t_stamp = t_stamp if t_stamp is not None else t0

        # 1) PERCIBIR
        detecciones = self.percepcion.detectar(frame)

        # 2) RAZONAR (umbral por clase + confirmacion temporal)
        filtradas = self.razonamiento.filtrar_por_clase(detecciones)
        incidentes = self.razonamiento.evaluar(zona, t_stamp, filtradas,
                                               origen=origen)

        # 3) ACTUAR (con filtro de cooldown en la memoria)
        for inc in incidentes:
            if self.memoria.debe_alertar(inc, t_stamp):
                frame_anotado = None
                if self.guardar_frames:
                    frame_anotado = self.percepcion.anotar(frame, filtradas)
                for act in self.actuadores:
                    act.alertar(inc, frame_anotado=frame_anotado)
                self.memoria.registrar_alerta(inc, t_stamp)
                self.alertas_emitidas += 1
            else:
                self.alertas_bloqueadas_cooldown += 1

        self.latencias_ms.append((time.perf_counter() - t0) * 1000)
        return incidentes, filtradas

    @property
    def latencia_media_ms(self):
        return (sum(self.latencias_ms) / len(self.latencias_ms)
                if self.latencias_ms else 0.0)

    def resumen_ejecucion(self):
        return {
            "frames_procesados": len(self.latencias_ms),
            "latencia_media_ms": round(self.latencia_media_ms, 1),
            "latencia_max_ms": round(max(self.latencias_ms), 1) if self.latencias_ms else 0,
            "alertas_emitidas": self.alertas_emitidas,
            "alertas_bloqueadas_por_cooldown": self.alertas_bloqueadas_cooldown,
        }
