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

    # ---------- anclaje anatomico (E30) ----------

    @staticmethod
    def _persona_contenedora(deteccion, personas):
        """Persona cuya caja mejor contiene la deteccion (None si <30%)."""
        x1, y1, x2, y2 = deteccion.caja
        area = max((x2 - x1) * (y2 - y1), 1e-6)
        mejor, mejor_frac = None, 0.0
        for p in personas:
            px1, py1, px2, py2 = p.caja
            ix = max(0.0, min(x2, px2) - max(x1, px1))
            iy = max(0.0, min(y2, py2) - max(y1, py1))
            frac = (ix * iy) / area
            if frac > mejor_frac:
                mejor_frac, mejor = frac, p
        return mejor if mejor_frac >= 0.3 else None

    @staticmethod
    def _casco_de_persona(persona, cascos, ref_x):
        """Casco/no_helmet sobre la cabeza de `persona` mas cercano a ref_x."""
        px1, py1, px2, py2 = persona.caja
        mejor, mejor_d = None, float("inf")
        for c in cascos:
            cx = (c.caja[0] + c.caja[2]) / 2
            cy = (c.caja[1] + c.caja[3]) / 2
            en_cabeza = py1 <= cy <= py1 + 0.35 * (py2 - py1)
            if px1 <= cx <= px2 and en_cabeza:
                if abs(cx - ref_x) < mejor_d:
                    mejor_d, mejor = abs(cx - ref_x), c
        return mejor

    @staticmethod
    def _reanclar_a_ojos(caja, persona, casco):
        """Reposiciona la caja (goggles/no_goggle) a nivel de ojos (E30/E34).

        El dataset fuente etiqueta 'goggles' con sesgo hacia abajo (mediana
        14.5% de la altura de la persona vs ~8% de los ojos humanos). Al
        dibujar se ancla la caja DONDE DEBERIAN estar las gafas.

        E34: la geometria depende del REGIMEN de la imagen —
        - fotos de obra (cuerpo completo): las cajas de casco del dataset
          vienen infladas hacia el rostro (borde inferior ~18% de la
          persona) -> los ojos caen DENTRO de la caja: centro - 15% altura;
        - webcam primer plano: la caja del casco es ajustada y los ojos
          caen JUSTO DEBAJO de su borde inferior (brim) -> borde + 20% de
          la altura de la propia caja de gafas;
        - cabeza descubierta (no_helmet): caja = cabeza, ojos a la mitad
          superior (50%).
        Solo desplaza HACIA ARRIBA (nunca baja una caja correcta) y limita
        el ancla a un rango anatomico sensato (3%-35% de la persona).
        """
        x1, y1, x2, y2 = caja
        h = y2 - y1
        cy = (y1 + y2) / 2
        py1, py2 = persona.caja[1], persona.caja[3]
        ph = py2 - py1
        if casco is not None:
            if casco.cls_id == 7:
                # cabeza descubierta: ojos a la mitad superior de la cabeza
                ch = casco.caja[3] - casco.caja[1]
                objetivo = casco.caja[1] + 0.5 * ch
            else:
                ch = casco.caja[3] - casco.caja[1]
                # fracción de persona donde termina el casco -> regimen
                borde = (casco.caja[3] - py1) / ph
                if borde <= 0.25:
                    # full-body (MOCS: casco inflado, ojos dentro de la caja)
                    objetivo = (casco.caja[1] + casco.caja[3]) / 2 - 0.15 * ch
                else:
                    # primer plano (casco ajustado): ojos bajo el brim
                    objetivo = casco.caja[3] + 0.20 * h
        else:
            objetivo = py1 + config.FRACCION_OJOS * ph
        # clamp anatomico: los ojos quedan entre el 6% y el 45% de la
        # altura de la persona (en primer plano estan por el 38-40%, en
        # plano general por el 8%). El piso es 6% y no 3% para que una
        # caja de cabeza incompleta no arrastre la gafa por encima de la
        # frente, cosa que se veia en un par de fotos del dataset.
        objetivo = min(max(objetivo, py1 + 0.06 * ph), py1 + 0.45 * ph)
        # y sin salir por arriba de la persona
        objetivo = max(objetivo, py1 + h / 2 + 2)
        if cy <= objetivo + 0.25 * h:
            return [x1, y1, x2, y2]        # ya esta a nivel de ojos (zona muerta)
        delta = objetivo - cy
        return [x1, y1 + delta, x2, y2 + delta]

    @staticmethod
    def _etiqueta_con_fondo(img, texto, x, y, color, escala=0.5, grosor=1):
        """Texto blanco sobre rectangulo solido del color de la clase."""
        (tw, th), base = cv2.getTextSize(texto, cv2.FONT_HERSHEY_SIMPLEX,
                                         escala, grosor)
        y_txt = max(th + base + 4, y)
        cv2.rectangle(img, (x - 1, y_txt - th - base - 3),
                      (x + tw + 1, y_txt + 2), color, -1)
        cv2.putText(img, texto, (x, y_txt - base - 1),
                    cv2.FONT_HERSHEY_SIMPLEX, escala, (255, 255, 255), grosor)

    @staticmethod
    def _deduplicar_visual(detecciones, iou_umbral=0.3):
        """Al dibujar, no repite cajas de una misma clase que estén muy
        solapadas (se queda con la de mayor confianza).

        El motivo: el NMS de la librería deja pasar pares con 30-49% de
        solape, y eso hacía que se vieran dos cajas de botas sobre el
        mismo pie. Persona no se deduplica porque en escenas amontonadas
        dos personas distintas pueden solapar sus cajas sin ser
        duplicados.

        Ojo: esto solo cambia el dibujo. Las decisiones y las métricas
        usan la lista original sin filtrar."""
        conservadas, por_clase = [], {}
        for d in sorted(detecciones, key=lambda x: -x.conf):
            if d.cls_id == 6:                      # Persona: sin dedup
                conservadas.append(d)
                continue
            duplicado = False
            for otra in por_clase.get(d.cls_id, []):
                a, b = d.caja, otra.caja
                ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
                iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
                inter = ix * iy
                un = ((a[2] - a[0]) * (a[3] - a[1])
                      + (b[2] - b[0]) * (b[3] - b[1]) - inter)
                if un > 0 and inter / un >= iou_umbral:
                    duplicado = True
                    break
            if not duplicado:
                por_clase.setdefault(d.cls_id, []).append(d)
                conservadas.append(d)
        return conservadas

    @staticmethod
    def anotar(frame, detecciones, grueso=2):
        """Dibuja las detecciones con anclaje anatomico y etiquetas legibles.

        - rojo = incumplimiento (`no_*`), verde = EPP correcto,
          celeste = Persona (caja mas gruesa);
        - etiquetas en espanol con fondo solido (legibles en video);
        - `goggles`/`no_goggle` se re-anclan a nivel de ojos de la persona
          que las contiene (E30: el dataset fuente las etiqueta por debajo
          de la cara; ver config y BITACORA);
        - cajas de la misma clase muy solapadas no se dibujan dos veces
          (solo presentación, ver `_deduplicar_visual`).
        """
        anotado = frame.copy()
        detecciones = Percepcion._deduplicar_visual(detecciones)
        personas = [d for d in detecciones if d.cls_id == 6]
        cascos = [d for d in detecciones if d.cls_id in (0, 7)]
        # 1) personas primero (las cajas de EPP van encima)
        for d in personas:
            x1, y1, x2, y2 = [int(v) for v in d.caja]
            cv2.rectangle(anotado, (x1, y1), (x2, y2), (255, 200, 100),
                          grueso + 1)
            Percepcion._etiqueta_con_fondo(
                anotado, f"Persona {d.conf:.2f}", x1, y1 - 2, (180, 120, 40))
        # 2) EPP e incumplimientos (la clase 5 'none' no se dibuja: no es
        #    alerta ni informa al supervisor; solo anade ruido visual)
        for d in detecciones:
            if d.cls_id in (5, 6):
                continue
            color = ((0, 0, 255) if d.cls_id in config.CLASES_INCUMPLIMIENTO
                     else (0, 200, 0))
            caja = d.caja
            if d.cls_id in config.CLASES_OJOS:
                persona = Percepcion._persona_contenedora(d, personas)
                if persona is not None:
                    casco = Percepcion._casco_de_persona(
                        persona, cascos, (caja[0] + caja[2]) / 2)
                    caja = Percepcion._reanclar_a_ojos(caja, persona, casco)
            x1, y1, x2, y2 = [int(v) for v in caja]
            cv2.rectangle(anotado, (x1, y1), (x2, y2), color, grueso)
            Percepcion._etiqueta_con_fondo(
                anotado, f"{config.NOMBRES_ES[d.cls_id]} {d.conf:.2f}",
                x1, y1 - 2, color)
        return anotado
