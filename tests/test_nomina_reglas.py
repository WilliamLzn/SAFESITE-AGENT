"""Pruebas de las reglas de nómina con casos escritos a mano.

Se ejecuta con:   python -m tests.test_nomina_reglas
(también es compatible con pytest si se instala).
"""
from src.nomina.reglas import (
    AUSENTE, BLOQUEADO, PRESENTE, TARDANZA,
    entradas_validas, estado_asistencia, minutos_trabajados,
)

REGLAS = {"tolerancia_tardanza_min": 10, "ventana_duplicado_min": 2}
TURNO_TARDE = {"id_turno": "TARDE", "inicio": "14:00", "fin": "22:00"}
ACTIVO = {"badge": "BDG-001", "estado_badge": "activo"}
BLOQ = {"badge": "BDG-002", "estado_badge": "bloqueado"}


def marc(hora, tipo, fecha="2026-11-02", badge="BDG-001"):
    return {"fecha": fecha, "hora": hora, "badge": badge, "tipo": tipo}


def test_a_tiempo_es_presente():
    assert estado_asistencia(ACTIVO, TURNO_TARDE, [marc("13:55:00", "entrada")], REGLAS) == PRESENTE


def test_justo_en_la_tolerancia_es_presente():
    # 14:10 = 10 min tarde: NO supera la tolerancia (se exige > 10)
    assert estado_asistencia(ACTIVO, TURNO_TARDE, [marc("14:10:00", "entrada")], REGLAS) == PRESENTE


def test_pasada_la_tolerancia_es_tardanza():
    # 14:12 = 12 min tarde > 10
    assert estado_asistencia(ACTIVO, TURNO_TARDE, [marc("14:12:00", "entrada")], REGLAS) == TARDANZA


def test_sin_marcaciones_es_ausente():
    assert estado_asistencia(ACTIVO, TURNO_TARDE, [], REGLAS) == AUSENTE


def test_badge_bloqueado_tiene_prioridad_sobre_la_hora():
    # Aunque llegue a tiempo, el badge bloqueado manda
    assert estado_asistencia(BLOQ, TURNO_TARDE, [marc("13:58:00", "entrada")], REGLAS) == BLOQUEADO


def test_entrada_duplicada_se_ignora():
    marcs = [marc("14:00:00", "entrada"), marc("14:00:40", "entrada")]
    assert len(entradas_validas(marcs, 2)) == 1


def test_minutos_trabajados_normales():
    marcs = [marc("14:00:00", "entrada"), marc("22:05:00", "salida")]
    assert minutos_trabajados(marcs, 2) == 8 * 60 + 5


def test_sin_salida_devuelve_none():
    assert minutos_trabajados([marc("14:00:00", "entrada")], 2) is None

def test_bloqueado_sin_marcaciones_es_ausente():
    assert estado_asistencia(BLOQ, TURNO_TARDE, [], REGLAS) == AUSENTE


if __name__ == "__main__":
    pruebas = [f for n, f in sorted(globals().items()) if n.startswith("test_")]
    for p in pruebas:
        p()
        print("OK ", p.__name__)
    print(f"\n{len(pruebas)} pruebas pasaron")
