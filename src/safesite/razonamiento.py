"""SafeSite-Agent — Razonamiento: reglas de decision con memoria de corto plazo.

Decisiones basadas SOLO en las clases `no_*` explicitas (EDA F6: la regla de
anidamiento casco-dentro-de-persona falla 38.2% de las veces).

Logica temporal (agente reactivo basado en modelos):
- un incidente se CONFIRMA cuando la misma clase `no_*` aparece en >=
  K frames consecutivos en la misma zona (config.K_FRAMES_CONFIRMACION);
- la confirmacion consulta a la Memoria antes de disparar el actuador
  (cooldown anti-spam por par (zona, clase)).
"""
from dataclasses import dataclass
from datetime import datetime

from . import config


@dataclass
class Incidente:
    """Un incumplimiento confirmado por el agente."""
    zona: str
    clase_id: int
    clase: str
    conf_media: float
    frames_consecutivos: int
    t_confirmacion: float          # t_stamp del frame que confirmo
    t_inicio_deteccion: float     # primer frame de la racha
    origen_ultimo_frame: str = ""

    def como_dict(self):
        return {
            "zona": self.zona,
            "clase": self.clase,
            "clase_id": self.clase_id,
            "conf_media": round(self.conf_media, 3),
            "frames_consecutivos": self.frames_consecutivos,
            "t_confirmacion": round(self.t_confirmacion, 2),
            "t_inicio_deteccion": round(self.t_inicio_deteccion, 2),
            "hora_local": datetime.fromtimestamp(self.t_confirmacion).isoformat(
                timespec="seconds"),
            "origen_ultimo_frame": self.origen_ultimo_frame,
        }


class Razonamiento:
    """Evalua observaciones y decide cuando hay un incidente confirmado."""

    def __init__(self, umbrales_incumplimiento=None, coherencia=None):
        # estado de corto plazo: (zona, clase_id) -> info de la racha actual
        self._rachas = {}
        # E33: umbral POR CLASE `no_*` (perfil VIVO calibrado en el piloto).
        # None = umbral global de evaluacion (config.UMBRAL_INCUMPLIMIENTO).
        self.umbrales_incumplimiento = umbrales_incumplimiento
        # E35: regla de coherencia por persona (solo perfil VIVO):
        # {cls_positivo: cls_no_*} — si el positivo esta detectado en la
        # MISMA persona, el `no_*` contradictorio se suprime.
        self.coherencia = coherencia or None
        self.suprimidas_coherencia = 0

    @staticmethod
    def _persona_contenedora(det, personas):
        """Persona cuya caja mejor contiene la deteccion (>=30% de su area)."""
        x1, y1, x2, y2 = det.caja
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

    def evaluar(self, zona, t_stamp, detecciones_filtradas, origen=""):
        """Devuelve la lista de incidentes confirmados en este frame.

        `detecciones_filtradas` ya viene con umbral por clase aplicado.
        """
        t = t_stamp
        presentes = set()
        for d in detecciones_filtradas:
            if d.cls_id in config.CLASES_INCUMPLIMIENTO:
                presentes.add(d.cls_id)

        confirmados = []
        # 1) actualizar rachas de las clases presentes
        for cls_id in presentes:
            clave = (zona, cls_id)
            confs = [d.conf for d in detecciones_filtradas if d.cls_id == cls_id]
            conf = max(confs)
            racha = self._rachas.get(clave)
            if racha is None or t - racha["t_ultimo"] > 1.0:  # racha rota
                self._rachas[clave] = {"n": 1, "t_inicio": t,
                                       "t_ultimo": t, "conf_suma": conf,
                                       "conf_max": conf}
            else:
                racha["n"] += 1
                racha["t_ultimo"] = t
                racha["conf_suma"] += conf
                racha["conf_max"] = max(racha["conf_max"], conf)

            racha = self._rachas[clave]
            if racha["n"] == config.K_FRAMES_CONFIRMACION:
                # punto exacto de confirmacion: emitir una sola vez
                confirmados.append(Incidente(
                    zona=zona,
                    clase_id=cls_id,
                    clase=config.NOMBRES_CLASES[cls_id],
                    conf_media=racha["conf_suma"] / racha["n"],
                    frames_consecutivos=racha["n"],
                    t_confirmacion=t,
                    t_inicio_deteccion=racha["t_inicio"],
                    origen_ultimo_frame=origen,
                ))
                racha["ya_confirmado"] = True

        # 2) decaer rachas de clases ausentes en este frame
        for clave in list(self._rachas.keys()):
            if clave[0] == zona and clave[1] not in presentes:
                del self._rachas[clave]

        # 3) rachas ya confirmadas no re-confirman hasta reinicio (cooldown
        #    lo maneja la Memoria; aqui evitamos doble emision en la misma racha)
        return confirmados

    def filtrar_por_clase(self, detecciones):
        """Aplica el umbral de confianza POR CLASE (positivas vs no_*).

        Con perfil VIVO (E33) cada clase `no_*` usa su umbral calibrado de
        `self.umbrales_incumplimiento` (dict {cls_id: umbral}); sin perfil,
        el umbral global de evaluacion. Las clases positivas siempre usan
        config.UMBRAL_DEFECTO.

        E35 (solo perfil VIVO, con `self.coherencia`): coherencia por
        persona — si el positivo de un EPP (ej. `gloves` en una mano) esta
        detectado en la MISMA persona, el `no_*` contradictorio (ej.
        `no_gloves` generado por la otra mano no detectada) se suprime.
        """
        salida = []
        for d in detecciones:
            if d.cls_id in config.CLASES_INCUMPLIMIENTO:
                if self.umbrales_incumplimiento is not None:
                    umbral = self.umbrales_incumplimiento.get(
                        d.cls_id, config.UMBRAL_INCUMPLIMIENTO)
                else:
                    umbral = config.UMBRAL_INCUMPLIMIENTO
            else:
                umbral = config.UMBRAL_DEFECTO
            if d.conf >= umbral:
                salida.append(d)

        # --- E35: coherencia por persona (solo si el perfil lo activa) ---
        if self.coherencia:
            personas = [d for d in salida if d.cls_id == 6]
            if personas:
                # clases positivas presentes por persona (id del objeto Persona)
                positivos_por_persona = {}
                for d in salida:
                    if d.cls_id in self.coherencia:
                        per = self._persona_contenedora(d, personas)
                        if per is not None:
                            positivos_por_persona.setdefault(
                                id(per), set()).add(d.cls_id)
                conservar = []
                for d in salida:
                    suprimir = False
                    if d.cls_id in self.coherencia.values():
                        per = self._persona_contenedora(d, personas)
                        if per is not None:
                            presentes = positivos_por_persona.get(id(per), set())
                            if any(self.coherencia[p] == d.cls_id
                                   for p in presentes):
                                suprimir = True
                                self.suprimidas_coherencia += 1
                                print(f"🧠 coherencia: {d.nombre} "
                                      f"(conf {d.conf:.2f}) suprimido — su "
                                      f"positivo esta en la misma persona",
                                      flush=True)
                    if not suprimir:
                        conservar.append(d)
                salida = conservar
        return salida
