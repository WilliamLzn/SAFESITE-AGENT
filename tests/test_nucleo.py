"""Pruebas del núcleo del agente: rachas de confirmación, cooldown,
umbrales por clase y los arreglos de la visualización.

No necesitan el modelo ni el dataset (la percepción va falsificada), así
que corren en segundos en cualquier máquina y en el workflow de CI.

Desde la raíz del repo:
    python -m pytest tests -q
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from src.safesite import config  # noqa: E402
from src.safesite.agente import SafeSiteAgent  # noqa: E402
from src.safesite.memoria import Memoria  # noqa: E402
from src.safesite.percepcion import Deteccion, Percepcion  # noqa: E402
from src.safesite.razonamiento import Incidente, Razonamiento  # noqa: E402


def det(cls_id, conf, caja):
    """Una detección hecha a mano, para no depender del modelo."""
    return Deteccion(cls_id=cls_id, nombre=config.NOMBRES_CLASES[cls_id],
                     conf=conf, caja=list(caja))


# --- razonamiento: rachas y confirmación en K frames ---

def test_racha_confirma_exactamente_en_k():
    r = Razonamiento()
    caja = [10, 10, 30, 30]
    inc = []
    for t in (0.0, 0.5, 1.0):
        inc = r.evaluar("zona", t, [det(7, 0.4, caja)])
    assert len(inc) == 1
    assert inc[0].clase_id == 7
    assert inc[0].frames_consecutivos == config.K_FRAMES_CONFIRMACION


def test_racha_no_confirma_antes_de_k():
    r = Razonamiento()
    caja = [10, 10, 30, 30]
    assert r.evaluar("zona", 0.0, [det(7, 0.4, caja)]) == []
    assert r.evaluar("zona", 0.5, [det(7, 0.4, caja)]) == []


def test_racha_se_rompe_si_la_clase_desaparece():
    r = Razonamiento()
    caja = [10, 10, 30, 30]
    r.evaluar("zona", 0.0, [det(7, 0.4, caja)])
    r.evaluar("zona", 0.5, [])          # la clase no está: la racha se borra
    assert r.evaluar("zona", 1.0, [det(7, 0.4, caja)]) == []


def test_umbrales_por_clase():
    r = Razonamiento()
    out = r.filtrar_por_clase([
        det(7, 0.14, [0, 0, 10, 10]),      # no_helmet bajo el umbral de no_*
        det(7, 0.15, [0, 0, 10, 10]),      # justo en el umbral: pasa
        det(0, 0.34, [0, 0, 10, 10]),      # helmet bajo el umbral de positivas
        det(0, 0.35, [0, 0, 10, 10]),      # justo en el umbral: pasa
    ])
    pares = sorted((d.cls_id, d.conf) for d in out)
    assert pares == [(0, 0.35), (7, 0.15)]


def test_regla_de_coherencia_suprime_el_no_contradictorio():
    # una persona con un guante detectado no debe generar "sin guantes"
    r = Razonamiento(coherencia=config.REGLA_COHERENCIA_VIVO)
    persona = det(6, 0.9, [0, 0, 100, 200])
    guante = det(1, 0.9, [40, 150, 60, 170])       # dentro de la persona
    no_gloves = det(9, 0.9, [50, 160, 65, 175])     # también dentro
    out = r.filtrar_por_clase([persona, guante, no_gloves])
    ids = [d.cls_id for d in out]
    assert 1 in ids            # el guante se conserva
    assert 9 not in ids        # el no_gloves contradictorio, no


# --- memoria: cooldown anti-spam ---

def test_cooldown_bloquea_y_luego_deja_pasar():
    m = Memoria(cooldown_s=30)
    inc = Incidente(zona="zona", clase_id=7, clase="no_helmet",
                    conf_media=0.5, frames_consecutivos=3,
                    t_confirmacion=100.0, t_inicio_deteccion=99.0)
    assert m.debe_alertar(inc, 100.0)
    m.registrar_alerta(inc, 100.0)
    assert not m.debe_alertar(inc, 120.0)     # dentro de la ventana
    assert m.debe_alertar(inc, 131.0)         # la ventana ya pasó


# --- percepción: geometría de las cajas ---

def test_persona_contenedora():
    persona = det(6, 0.9, [0, 0, 100, 200])
    dentro = det(4, 0.5, [40, 20, 60, 40])
    fuera = det(4, 0.5, [500, 500, 520, 520])
    assert Percepcion._persona_contenedora(dentro, [persona]) is persona
    assert Percepcion._persona_contenedora(fuera, [persona]) is None


def test_reanclaje_de_gafas_no_sube_de_la_frente():
    # caja de cabeza que solo cubre la parte alta: la gafa no debe quedar
    # por encima del 6% de la altura de la persona
    persona = det(6, 0.9, [0, 0, 100, 1000])
    cabeza = det(7, 0.6, [40, 0, 60, 40])
    gafa = det(4, 0.5, [40, 800, 60, 820])
    nueva = Percepcion._reanclar_a_ojos(gafa.caja, persona, cabeza)
    frac = ((nueva[1] + nueva[3]) / 2) / 1000
    assert frac >= 0.0595


def test_deduplicar_visual_al_dibujar():
    a = det(3, 0.6, [0, 0, 100, 50])
    b = det(3, 0.4, [10, 5, 105, 45])    # casi la misma caja que la otra
    mejor = det(3, 0.9, [0, 0, 100, 50])
    persona = det(6, 0.5, [0, 0, 100, 100])
    out = Percepcion._deduplicar_visual([a, b, mejor, persona])
    botas = [d for d in out if d.cls_id == 3]
    assert len(botas) == 1 and botas[0].conf == 0.9
    assert any(d.cls_id == 6 for d in out)   # persona nunca se deduplica


# --- agente: el ciclo completo con una percepción falsa ---

class PercepcionFalsa:
    """Devuelve siempre las mismas detecciones, para probar el ciclo del
    agente sin cargar YOLO."""

    def __init__(self, detecciones=None, ruta_modelo=None, device=None):
        self.detecciones = detecciones or []

    def detectar(self, frame, conf=None):
        return list(self.detecciones)

    def anotar(self, frame, detecciones, grueso=2):
        return frame


class ActuadorSilencioso:
    nombre = "silencioso"

    def alertar(self, *args, **kwargs):
        pass

    def alertar_lote(self, *args, **kwargs):
        pass


def agente_de_prueba(monkeypatch, detecciones=None):
    import src.safesite.agente as modulo
    monkeypatch.setattr(
        modulo, "Percepcion",
        lambda ruta_modelo=None, device=None: PercepcionFalsa(detecciones))
    return SafeSiteAgent(actuadores=[ActuadorSilencioso()],
                         guardar_frames=False)


def test_frames_invalidos_se_registran_y_no_tumban_el_agente(monkeypatch):
    ag = agente_de_prueba(monkeypatch)
    r = ag.procesar_frame(None, "zona")                    # sensor sin dato
    assert r == ([], []) and ag.frames_fallidos == 1
    r = ag.procesar_frame(np.zeros((480, 640), np.uint8), "zona")  # 1 canal
    assert r == ([], []) and ag.frames_fallidos == 2


def test_ciclo_confirma_y_no_repite_la_alerta(monkeypatch):
    no_casco = det(7, 0.4, [10, 10, 30, 30])
    ag = agente_de_prueba(monkeypatch, detecciones=[no_casco])
    frame = np.zeros((480, 640, 3), np.uint8)
    for t in (0.0, 0.5, 1.0):
        incidentes, _ = ag.procesar_frame(frame, "zona", t_stamp=100.0 + t)
    assert ag.alertas_emitidas == 1
    assert incidentes[0].clase_id == 7
    # la misma racha no vuelve a alertar
    for t in (1.5, 2.0, 2.5):
        ag.procesar_frame(frame, "zona", t_stamp=100.0 + t)
    assert ag.alertas_emitidas == 1


def test_frame_valido_sin_faltas_no_alerta(monkeypatch):
    ag = agente_de_prueba(monkeypatch, detecciones=[det(0, 0.9, [10, 10, 30, 30])])
    frame = np.zeros((480, 640, 3), np.uint8)
    for t in (0.0, 0.5, 1.0):
        ag.procesar_frame(frame, "zona", t_stamp=100.0 + t)
    assert ag.alertas_emitidas == 0


# --- y que los umbrales pre-registrados sigan donde deben ---

def test_umbrales_preregistrados_de_la_suite():
    from src.safesite import pruebas_medidas as suite
    assert suite.UMBRAL_M1 == 0.70
    assert suite.UMBRAL_M2 == 0.10
    assert suite.UMBRAL_M3_S == 10.0
    assert suite.UMBRAL_M4 == 0
