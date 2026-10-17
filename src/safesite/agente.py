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
                 actuadores=None, cooldown_s=None, guardar_frames=True,
                 perfil_umbrales=None, coherencia=None):
        self.perfil_umbrales = perfil_umbrales   # E33: None=evaluacion | dict=vivo
        self.coherencia = coherencia             # E35: regla por persona (vivo)
        self.percepcion = Percepcion(ruta_modelo=ruta_modelo, device=device)
        self.razonamiento = Razonamiento(
            umbrales_incumplimiento=perfil_umbrales, coherencia=coherencia)
        self.memoria = Memoria(cooldown_s=cooldown_s)
        self.guardar_frames = guardar_frames
        self.actuadores = actuadores or [ActuadorConsola(), ActuadorWhatsApp()]
        self.latencias_ms = []       # metrica: tiempo end-to-end por frame
        self.alertas_emitidas = 0
        self.alertas_bloqueadas_cooldown = 0
        self.frames_fallidos = 0     # percepciones que fallaron (sensor sin dato)

    def reset(self):
        """Reinicia el estado interno (rachas, cooldown y contadores).

        Usado por la suite de pruebas (Fase 3 del enunciado) para repetir
        escenarios con el agente en estado limpio, sin recargar el modelo.
        El perfil de umbrales y la regla de coherencia (E33/E35) se
        CONSERVAN entre resets.
        """
        self.razonamiento = Razonamiento(
            umbrales_incumplimiento=self.perfil_umbrales,
            coherencia=self.coherencia)
        self.memoria = Memoria()
        self.latencias_ms.clear()
        self.alertas_emitidas = 0
        self.alertas_bloqueadas_cooldown = 0
        self.frames_fallidos = 0

    def procesar_frame(self, frame, zona, t_stamp=None, origen=""):
        """Un ciclo completo del agente sobre un fotograma.

        Tolerancia a falla del sensor (enunciado Fase 2, "sensor sin
        dato"): si la percepcion lanza (frame corrupto, None, formato
        invalido), el agente lo registra, NO actua y continua con el
        siguiente frame. La racha de confirmacion temporal NO se rompe
        ante un fallo transitorio (decision documentada).
        """
        t0 = time.perf_counter()
        t_stamp = t_stamp if t_stamp is not None else t0

        # 1) PERCIBIR
        frame_invalido = (
            frame is None
            or not hasattr(frame, "shape")
            or getattr(frame, "ndim", 0) < 3
            or frame.size == 0
        )
        if frame_invalido:
            # sensor sin dato (frame corrupto, negro, None o formato invalido):
            # registrar, NO actuar y continuar con el siguiente frame. La
            # racha de confirmacion temporal NO se rompe ante un fallo
            # transitorio (decision documentada en la bitacora).
            self.frames_fallidos += 1
            print(f"⚠️ percepcion sin dato (frame invalido) zona={zona} "
                  f"origen={origen}", flush=True)
            return [], []
        try:
            detecciones = self.percepcion.detectar(frame)
        except Exception as e:
            self.frames_fallidos += 1
            print(f"⚠️ percepcion fallo zona={zona} origen={origen}: "
                  f"{type(e).__name__}: {e}", flush=True)
            return [], []

        # 2) RAZONAR (umbral por clase + confirmacion temporal)
        filtradas = self.razonamiento.filtrar_por_clase(detecciones)
        incidentes = self.razonamiento.evaluar(zona, t_stamp, filtradas,
                                               origen=origen)

        # 3) ACTUAR — LOTE CONSOLIDADO: todas las faltas del frame en un
        #    solo mensaje (cooldown por (zona, clase) como antes)
        nuevos = [inc for inc in incidentes
                  if self.memoria.debe_alertar(inc, t_stamp)]
        self.alertas_bloqueadas_cooldown += len(incidentes) - len(nuevos)
        if nuevos:
            frame_anotado = None
            if self.guardar_frames:
                frame_anotado = self.percepcion.anotar(frame, filtradas)
            for act in self.actuadores:
                act.alertar_lote(nuevos, frame_anotado=frame_anotado)
            for inc in nuevos:
                self.memoria.registrar_alerta(inc, t_stamp)
                self.alertas_emitidas += 1

        self.latencias_ms.append((time.perf_counter() - t0) * 1000)
        return incidentes, filtradas

    @property
    def latencia_media_ms(self):
        return (sum(self.latencias_ms) / len(self.latencias_ms)
                if self.latencias_ms else 0.0)

    def resumen_ejecucion(self):
        return {
            "frames_procesados": len(self.latencias_ms),
            "frames_fallidos": self.frames_fallidos,
            "latencia_media_ms": round(self.latencia_media_ms, 1),
            "latencia_max_ms": round(max(self.latencias_ms), 1) if self.latencias_ms else 0,
            "alertas_emitidas": self.alertas_emitidas,
            "alertas_bloqueadas_por_cooldown": self.alertas_bloqueadas_cooldown,
        }
