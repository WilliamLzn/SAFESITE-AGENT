"""SafeSite-Agent — Percepcion: fuentes de video e inferencia YOLO.

Percibir = obtener fotogramas (camara IP, webcam, archivo de video o carpeta
de imagenes para simulacion) y ejecutar el detector sobre ellos.
"""
import os
import time
from dataclasses import dataclass, field

import cv2

from . import config


@dataclass
class Deteccion:
    """Una deteccion del modelo sobre un fotograma."""
    cls_id: int
    nombre: str
    conf: float
    caja: list  # [x1, y1, x2, y2] en pixeles


@dataclass
class Observacion:
    """Lo que el agente percibe en un instante (frame + metadatos)."""
    frame: object            # numpy BGR
    zona: str                # identificador de camara/zona (en demo: escena)
    t_stamp: float           # timestamp unix del fotograma
    detecciones: list = field(default_factory=list)
    t_inferencia_ms: float = 0.0


class FuenteCarpeta:
    """Simula video continuo a partir de imagenes en carpeta.

    Cada imagen se repite `frames_por_escena` veces consecutivas para
    simular que la escena persiste en el tiempo (un trabajador sin EPP
    no desaparece entre fotogramas). Sirve para demos sin camara.
    """

    def __init__(self, rutas_imagenes, zona="obra_demo",
                 frames_por_escena=4, fps_simulado=2.0):
        if not rutas_imagenes:
            raise ValueError("la lista de imagenes esta vacia")
        self.rutas = list(rutas_imagenes)
        self.zona = zona
        self.frames_por_escena = frames_por_escena
        self.intervalo = 1.0 / fps_simulado

    def iterar(self):
        t0 = time.time()
        n = 0
        for idx, ruta in enumerate(self.rutas):
            frame = cv2.imread(ruta)
            if frame is None:
                continue
            for _ in range(self.frames_por_escena):
                # timestamps simulados a fps_simulado
                yield frame, {"zona": self.zona,
                              "t_stamp": t0 + n * self.intervalo,
                              "escena_id": f"{idx:04d}",
                              "origen": os.path.basename(ruta)}
                n += 1


class Percepcion:
    """Ejecuta el detector YOLO sobre fotogramas."""

    def __init__(self, ruta_modelo=None, device=None, conf=None, iou=0.5):
        from ultralytics import YOLO  # import diferido (arranque mas limpio)
        self.ruta_modelo = ruta_modelo or config.RUTA_MODELO
        self.device = device or config.DEVICE_DEFECTO
        self.conf = conf if conf is not None else config.UMBRAL_INCUMPLIMIENTO
        self.iou = iou
        self.modelo = YOLO(self.ruta_modelo)

    def detectar(self, frame, conf=None):
        """Inferencia cruda; devuelve lista[Deteccion] sin filtrar por clase.

        El umbral de inferencia es el mas bajo de la config, y el
        razonamiento aplica el umbral POR CLASE (mas alto para positivas).
        """
        resultado = self.modelo.predict(
            frame, conf=conf if conf is not None else self.conf,
            iou=self.iou, device=self.device, verbose=False)[0]
        detecciones = []
        if resultado.boxes is not None:
            for caja in resultado.boxes:
                x1, y1, x2, y2 = caja.xyxy[0].tolist()
                detecciones.append(Deteccion(
                    cls_id=int(caja.cls[0]),
                    nombre=config.NOMBRES_CLASES[int(caja.cls[0])],
                    conf=float(caja.conf[0]),
                    caja=[x1, y1, x2, y2],
                ))
        return detecciones

    @staticmethod
    def anotar(frame, detecciones, grueso=2):
        """Dibuja las detecciones: rojo si es incumplimiento, verde si es EPP."""
        anotado = frame.copy()
        for d in detecciones:
            color = (0, 0, 255) if d.cls_id in config.CLASES_INCUMPLIMIENTO else (0, 200, 0)
            x1, y1, x2, y2 = [int(v) for v in d.caja]
            cv2.rectangle(anotado, (x1, y1), (x2, y2), color, grueso)
            etiqueta = f"{d.nombre} {d.conf:.2f}"
            cv2.putText(anotado, etiqueta, (x1, max(15, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
        return anotado
