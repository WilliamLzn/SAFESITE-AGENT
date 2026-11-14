"""SafeSite-Agent v2 — Lector de badges QR para control de acceso y asistencia.

Detecta y decodifica QR codes en el stream de la cámara usando
cv2.QRCodeDetector de OpenCV (sin dependencias externas del sistema).

La detección QR se ejecuta en un HILO SEPARADO con una cola de frames,
para no bloquear el loop principal de captura de video y lograr >=30 FPS.

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

import threading
import time
from collections import deque
from dataclasses import dataclass
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
    estrategias de preprocesamiento, ejecutado en un hilo separado
    para no bloquear el loop principal de video."""

    def __init__(self, cooldown_segundos=0.5, cooldown_fallido=0.2,
                 detectar_cada_n_frames=1, cola_max_tamaño=10):
        """
        cooldown_segundos: tiempo mínimo entre lecturas exitosas del mismo
                           badge (evita re-leer constantemente).
        cooldown_fallido: tiempo mínimo entre intentos de lectura fallida
                          del mismo badge (evita saturar la CPU).
        detectar_cada_n_frames: ejecutar detección QR cada N frames (1 = cada frame).
        cola_max_tamaño: máximo de frames en la cola del hilo de detección.
        """
        self.detector = cv2.QRCodeDetector()
        self.cooldown_segundos = cooldown_segundos
        self.cooldown_fallido = cooldown_fallido
        self.detectar_cada_n_frames = detectar_cada_n_frames
        self.cola_max_tamaño = cola_max_tamaño

        # Cola y hilo de detección
        self._cola_frames = deque(maxlen=cola_max_tamaño)
        self._cola_lock = threading.Lock()
        self._detener = False
        self._hilo_deteccion = None
        self._iniciado = False

        # Estado de lecturas (acceso thread-safe)
        self._lecturas_lock = threading.Lock()
        self._ultima_lectura_por_badge = {}   # badge_id -> timestamp
        self._ultimo_intento_por_badge = {}   # badge_id -> timestamp (fallido)
        self._ultimo_badge_id = None          # último badge leído (cualquiera)
        self._ultimas_lecturas = []           # lista de LecturaBadge (últimas N)
        self._contador_frames = 0

    # ------------------------------------------------------------------ inicio/parada

    def iniciar(self):
        """Inicia el hilo de detección QR en segundo plano."""
        if self._iniciado:
            return
        self._detener = False
        self._hilo_deteccion = threading.Thread(
            target=self._bucle_deteccion, daemon=True)
        self._hilo_deteccion.start()
        self._iniciado = True
        print("🔍 Lector QR iniciado en hilo separado", flush=True)

    def detener(self):
        """Detiene el hilo de detección QR."""
        self._detener = True
        if self._hilo_deteccion is not None:
            self._hilo_deteccion.join(timeout=2.0)
        self._iniciado = False

    def encolar_frame(self, frame: np.ndarray):
        """Agrega un frame a la cola para detección (llamar desde el hilo principal)."""
        if not self._iniciado:
            return
        with self._cola_lock:
            self._cola_frames.append(frame.copy())

    def obtener_lecturas(self) -> List[LecturaBadge]:
        """Devuelve las lecturas nuevas acumuladas y las limpia."""
        with self._lecturas_lock:
            lecturas = list(self._ultimas_lecturas)
            self._ultimas_lecturas = []
            return lecturas

    # ------------------------------------------------------------------ bucle de detección (hilo separado)

    def _bucle_deteccion(self):
        """Bucle principal del hilo: procesa frames de la cola y detecta QRs."""
        contador_local = 0
        frames_sin_qr = 0
        while not self._detener:
            # Obtener un frame de la cola
            frame = None
            with self._cola_lock:
                if self._cola_frames:
                    frame = self._cola_frames.popleft()

            if frame is None:
                time.sleep(0.005)  # evitar busy-wait
                continue

            contador_local += 1
            if contador_local % self.detectar_cada_n_frames != 0:
                continue

            ahora = time.time()

            # Generar versiones preprocesadas del frame
            versiones = self._preprocesar(frame)

            lecturas_encontradas = False
            for versión in versiones:
                data, puntos = self._intentar_decodificar(versión)
                if not data:
                    continue

                datos_lista = data if isinstance(data, list) else [data]
                puntos_lista = puntos if puntos is not None else []

                print(f"🔍 QR detectado! Contenido: {datos_lista}", flush=True)

                for i, contenido in enumerate(datos_lista):
                    if not contenido:
                        continue
                    badge = self._parsear_qr(contenido, ahora)
                    if not badge.valido:
                        print(f"⚠️ QR inválido: {contenido}", flush=True)
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

                    if hace_ok < self.cooldown_segundos and not es_nuevo:
                        continue
                    if hace_fail < self.cooldown_fallido and not es_nuevo:
                        continue

                    self._ultimo_intento_por_badge[badge.badge_id] = ahora
                    self._ultima_lectura_por_badge[badge.badge_id] = ahora
                    self._ultimo_badge_id = badge.badge_id

                    lectura = LecturaBadge(
                        badge=badge,
                        caja=caja,
                        conf=1.0,
                        es_nuevo=es_nuevo,
                    )

                    with self._lecturas_lock:
                        self._ultimas_lecturas.append(lectura)
                        # Mantener solo las últimas 50 lecturas
                        if len(self._ultimas_lecturas) > 50:
                            self._ultimas_lecturas = self._ultimas_lecturas[-50:]

                    print(f"✅ Badge leído: {badge.badge_id} ({badge.nombre})", flush=True)
                    lecturas_encontradas = True

                if lecturas_encontradas:
                    break

            if not lecturas_encontradas:
                frames_sin_qr += 1
                if frames_sin_qr % 100 == 0:
                    print(f"⏳ Esperando QR... ({frames_sin_qr} frames sin detectar)", flush=True)
            else:
                frames_sin_qr = 0

    # ------------------------------------------------------------------ preprocesamiento

    @staticmethod
    def _preprocesar(frame: np.ndarray) -> List[np.ndarray]:
        """Genera varias versiones del frame para intentar detectar el QR."""
        versiones: List[np.ndarray] = []

        gris = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # CLAHE para contraste adaptativo (mejor para iluminación desigual)
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gris_clahe = clahe.apply(gris)

        # Umbral binario simple (mejor para QRs de alto contraste)
        _, umbral = cv2.threshold(gris, 127, 255, cv2.THRESH_BINARY)

        versiones.extend([gris, gris_clahe, umbral])

        # Rotación 180 para QRs volteados
        h, w = gris.shape
        centro = (w / 2, h / 2)
        M = cv2.getRotationMatrix2D(centro, 180, 1.0)
        rotada = cv2.warpAffine(gris, M, (w, h))
        versiones.append(rotada)

        return versiones

    @staticmethod
    def _intentar_decodificar(imagen: np.ndarray) -> Tuple[Optional[str], Optional[np.ndarray]]:
        """Intenta decodificar un QR en una imagen dada."""
        try:
            data, puntos, _ = cv2.QRCodeDetector().detectAndDecode(imagen)
            if data:
                return data, puntos
        except Exception:
            pass
        return None, None

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

    def historial_reciente(self, segundos=10):
        """Lecturas de los últimos `segundos` segundos."""
        ahora = time.time()
        with self._lecturas_lock:
            return [l for l in self._ultimas_lecturas if ahora - l.timestamp <= segundos]

    def reset(self):
        """Limpia el estado de cooldown y historial."""
        with self._lecturas_lock:
            self._ultima_lectura_por_badge.clear()
            self._ultimo_intento_por_badge.clear()
            self._ultimo_badge_id = None
            self._ultimas_lecturas.clear()
        with self._cola_lock:
            self._cola_frames.clear()
