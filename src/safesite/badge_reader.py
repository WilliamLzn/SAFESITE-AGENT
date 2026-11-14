"""SafeSite-Agent v2 — Lector de badges QR para control de acceso y asistencia.

Detecta y decodifica QR codes en el stream de la cámara usando
cv2.QRCodeDetector (OpenCV integrado, sin dependencias externas del sistema).

El contenido de cada QR sigue el formato pipe generado por
scripts/generar_qr_badges.py:

    SAFESITE|BDG-XXX|EMP-XXX|nombre|puesto|turno|estado

Se integra con src/nomina/reglas.py para validar el badge contra la nómina
y registrar entrada/salida.
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import cv2

from . import config


@dataclass
class Badge:
    """Badge QR decodificado."""
    badge_id: str          # ej. BDG-001
    id_empleado: str       # ej. EMP-001
    nombre: str
    puesto: str
    turno: str             # MANANA / TARDE
    estado_badge: str      # activo / bloqueado
    crudo: str             # contenido completo del QR
    timestamp: float       # momento de la lectura
    valido: bool = True    # False si el formato no es el esperado


@dataclass
class LecturaBadge:
    """Resultado de una lectura de badge en un frame."""
    badge: Optional[Badge]
    caja: list               # [x1, y1, x2, y2] del QR en el frame
    conf: float              # confianza de detección (QRCodeDetector da 1.0 si decodifica)
    es_nuevo: bool           # True si es un badge distinto al último leído


class LectorBadgeQR:
    """Lee QRs de badges desde fotogramas de la cámara."""

    def __init__(self, cooldown_segundos=2.0):
        """
        cooldown_segundos: tiempo mínimo entre lecturas del mismo badge
                           para evitar re-leer constantemente mientras
                           el badge está frente a la cámara.
        """
        self.detector = cv2.QRCodeDetector()
        self.cooldown_segundos = cooldown_segundos
        self._ultima_lectura_por_badge = {}   # badge_id -> timestamp
        self._ultimo_badge_id = None          # último badge leído (cualquiera)
        self._historial = []                  # lista de LecturaBadge

    def detectar(self, frame):
        """Detecta y decodifica QRs en un frame.

        Devuelve lista[LecturaBadge] (puede estar vacía).
        """
        resultados = []
        try:
            data, puntos, _ = self.detector.detectAndDecode(frame)
        except Exception:
            data, puntos = None, None

        ahora = time.time()
        lecturas = []

        if data:
            # detectAndDecode puede devolver un solo string o lista
            datos_lista = data if isinstance(data, list) else [data]
            puntos_lista = puntos if puntos is not None else []

            for i, contenido in enumerate(datos_lista):
                if not contenido:
                    continue
                badge = self._parsear_qr(contenido, ahora)
                if badge is None:
                    continue

                # caja del QR (puntos de las esquinas)
                caja = self._extraer_caja(puntos_lista, i, frame.shape) \
                    if puntos_lista is not None and len(puntos_lista) > i \
                    else [0, 0, frame.shape[1], frame.shape[0]]

                # cooldown por badge
                ultima = self._ultima_lectura_por_badge.get(badge.badge_id, 0)
                hace = ahora - ultima
                es_nuevo = badge.badge_id != self._ultimo_badge_id

                if hace < self.cooldown_segundos and not es_nuevo:
                    # mismo badge reciente: no es lectura nueva
                    continue

                self._ultima_lectura_por_badge[badge.badge_id] = ahora
                self._ultimo_badge_id = badge.badge_id

                lectura = LecturaBadge(
                    badge=badge,
                    caja=caja,
                    conf=1.0,
                    es_nuevo=es_nuevo,
                )
                lecturas.append(lectura)
                self._historial.append(lectura)

        return lecturas

    @staticmethod
    def _parsear_qr(contenido, timestamp):
        """Parsea el formato pipe del QR.

        Formato esperado: SAFESITE|BDG-XXX|EMP-XXX|nombre|puesto|turno|estado
        Devuelve Badge o None si el formato es inválido.
        """
        partes = contenido.split("|")
        if len(partes) < 7 or partes[0] != "SAFESITE":
            return Badge(
                badge_id="", id_empleado="", nombre="", puesto="",
                turno="", estado_badge="", crudo=contenido,
                timestamp=timestamp, valido=False,
            )
        return Badge(
            badge_id=partes[1],
            id_empleado=partes[2],
            nombre=partes[3],
            puesto=partes[4],
            turno=partes[5],
            estado_badge=partes[6],
            crudo=contenido,
            timestamp=timestamp,
            valido=True,
        )

    @staticmethod
    def _extraer_caja(puntos_lista, idx, shape):
        """Extrae [x1, y1, x2, y2] de los puntos de una detección QR."""
        try:
            pts = puntos_lista[idx]
            xs = [float(p[0]) for p in pts]
            ys = [float(p[1]) for p in pts]
            h, w = shape[:2]
            x1 = max(0, min(w, int(min(xs))))
            y1 = max(0, min(h, int(min(ys))))
            x2 = max(0, min(w, int(max(xs))))
            y2 = max(0, min(h, int(max(ys))))
            return [x1, y1, x2, y2]
        except Exception:
            return [0, 0, shape[1], shape[0]]

    def historial_reciente(self, segundos=10):
        """Lecturas de los últimos `segundos` segundos."""
        ahora = time.time()
        return [l for l in self._historial if ahora - l.timestamp <= segundos]

    def reset(self):
        """Limpia el estado de cooldown y historial."""
        self._ultima_lectura_por_badge.clear()
        self._ultimo_badge_id = None
        self._historial.clear()
