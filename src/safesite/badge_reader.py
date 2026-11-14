"""SafeSite-Agent v2 — Lector de badges QR para control de acceso y asistencia.

Detecta y decodifica QR codes en el stream de la cámara usando
cv2.QRCodeDetector de OpenCV (sin dependencias externas del sistema).

Mejoras de precisión:
- Preprocesamiento: escala de gris, CLAHE (contraste adaptativo),
  umbral adaptativo y desenfoque gaussiano para reducir ruido.
- Múltiples escalas: prueba con el frame original, reducido y aumentado
  para detectar QRs pequeños o lejanos.
- Múltiples orientaciones: rota la imagen 0°, 90°, 180°, 270° para
  detectar QRs girados.
- Cooldown inteligente: menor cooldown para lecturas exitosas, mayor
  para fallidas, evitando re-leer constantemente el mismo badge.

El contenido de cada QR sigue el formato pipe generado por
scripts/generar_qr_badges.py:

    SAFESITE|BDG-XXX|EMP-XXX|nombre|puesto|turno|estado

Se integra con src/nomina/reglas.py para validar el badge contra la nómina
y registrar entrada/salida.
"""

import time
from dataclasses import dataclass, field
from typing import Optional, List, Tuple

import cv2
import numpy as np


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
    conf: float              # confianza de detección (0.0 a 1.0)
    es_nuevo: bool           # True si es un badge distinto al último leído


class LectorBadgeQR:
    """Lee QRs de badges desde fotogramas de la cámara con múltiples
    estrategias de preprocesamiento para mejorar la detección."""

    def __init__(self, cooldown_segundos=1.5, cooldown_fallido=0.5):
        """
        cooldown_segundos: tiempo mínimo entre lecturas exitosas del mismo
                           badge (evita re-leer constantemente).
        cooldown_fallido: tiempo mínimo entre intentos de lectura fallida
                          del mismo badge (evita saturar la CPU).
        """
        self.detector = cv2.QRCodeDetector()
        self.cooldown_segundos = cooldown_segundos
        self.cooldown_fallido = cooldown_fallido
        self._ultima_lectura_por_badge = {}   # badge_id -> timestamp
        self._ultimo_intento_por_badge = {}   # badge_id -> timestamp (fallido)
        self._ultimo_badge_id = None          # último badge leído (cualquiera)
        self._historial = []                  # lista de LecturaBadge

    # ------------------------------------------------------------------ preprocesamiento

    @staticmethod
    def _preprocesar(frame: np.ndarray) -> List[np.ndarray]:
        """Genera varias versiones del frame para intentar detectar el QR.

        Devuelve una lista de imágenes (gris, CLAHE, umbral, rotaciones).
        """
        versiones: List[np.ndarray] = []

        # 1) Escala de gris
        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # 2) CLAHE para mejorar contraste local (ayuda con iluminación desigual)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gris_clahe = clahe.apply(gris)

        # 3) Umbral adaptativo (binarización para QRs de bajo contraste)
        _, umbral = cv2.threshold(
            gris_clahe, 0, 255,
            cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 4) Desenfoque ligero para reducir ruido
        suave = cv2.GaussianBlur(gris_clahe, (3, 3), 0)

        versiones.extend([gris, gris_clahe, umbral, suave])

        # 5) Rotaciones para detectar QRs girados
        for angulo in (90, 180, 270):
            h, w = gris.shape
            centro = (w / 2, h / 2)
            M = cv2.getRotationMatrix2D(centro, angulo, 1.0)
            rotada = cv2.warpAffine(gris, M, (w, h))
            versiones.append(rotada)

        # 6) Versiones escaladas (reducido y aumentado) para QRs pequeños/lejanos
        for escala in (0.7, 1.3):
            if escala != 1.0:
                nueva_w = int(frame.shape[1] * escala)
                nueva_h = int(frame.shape[0] * escala)
                escalado = cv2.resize(
                    gris, (nueva_w, nueva_h),
                    interpolation=cv2.INTER_LINEAR)
                versiones.append(escalado)

        return versiones

    @staticmethod
    def _extraer_caja(puntos_lista, idx, shape):
        """Extrae [x1, y1, x2, y2] de los puntos de una detección QR."""
        try:
            if puntos_lista is None or idx >= len(puntos_lista):
                return [0, 0, shape[1], shape[0]]
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

    # ------------------------------------------------------------------ detección

    def _intentar_decodificar(self, imagen: np.ndarray) -> Tuple[Optional[str], Optional[np.ndarray]]:
        """Intenta decodificar un QR en una imagen dada.

        Devuelve (datos, puntos) o (None, None).
        """
        try:
            data, puntos, _ = self.detector.detectAndDecode(imagen)
            if data:
                return data, puntos
        except Exception:
            pass
        return None, None

    def detectar(self, frame):
        """Detecta y decodifica QRs en un frame usando múltiples estrategias.

        Devuelve lista[LecturaBadge] (puede estar vacía).
        """
        ahora = time.time()
        lecturas: List[LecturaBadge] = []

        # Generar versiones preprocesadas del frame
        versiones = self._preprocesar(frame)

        for versión in versiones:
            data, puntos = self._intentar_decodificar(versión)
            if not data:
                continue

            # detectAndDecode puede devolver string o lista
            datos_lista = data if isinstance(data, list) else [data]
            puntos_lista = puntos if puntos is not None else []

            for i, contenido in enumerate(datos_lista):
                if not contenido:
                    continue
                badge = self._parsear_qr(contenido, ahora)
                if not badge.valido:
                    continue

                caja = self._extraer_caja(
                    puntos_lista, i, frame.shape) \
                    if puntos_lista is not None and len(puntos_lista) > i \
                    else [0, 0, frame.shape[1], frame.shape[0]]

                # --- lógica de cooldown ---
                ultima_ok = self._ultima_lectura_por_badge.get(
                    badge.badge_id, 0)
                hace_ok = ahora - ultima_ok

                ultima_fail = self._ultimo_intento_por_badge.get(
                    badge.badge_id, 0)
                hace_fail = ahora - ultima_fail

                es_nuevo = badge.badge_id != self._ultimo_badge_id

                # Si es el mismo badge y ya se leyó recientemente, saltar
                if hace_ok < self.cooldown_segundos and not es_nuevo:
                    continue

                # Si hubo un intento fallido muy reciente, no saturar
                if hace_fail < self.cooldown_fallido and not es_nuevo:
                    continue

                # Registrar intento (exitoso o no)
                self._ultimo_intento_por_badge[badge.badge_id] = ahora

                # Lectura exitosa: actualizar cooldown de éxito
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

            # Si ya encontramos lecturas en esta versión, no necesitamos probar más
            if lecturas:
                break

        return lecturas

    def historial_reciente(self, segundos=10):
        """Lecturas de los últimos `segundos` segundos."""
        ahora = time.time()
        return [l for l in self._historial if ahora - l.timestamp <= segundos]

    def reset(self):
        """Limpia el estado de cooldown y historial."""
        self._ultima_lectura_por_badge.clear()
        self._ultimo_intento_por_badge.clear()
        self._ultimo_badge_id = None
        self._historial.clear()
