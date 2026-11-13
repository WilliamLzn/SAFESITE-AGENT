"""Generador de datos sintéticos de nómina para SAFESITE V2 (Agente 1).

Con la misma semilla (42) produce SIEMPRE los mismos archivos, lo que hace
reproducible el experimento. No usa nombres reales, rostros ni cédulas.

Uso (desde la raíz del repo):
    python -m src.nomina.datos_sinteticos
"""
import csv
import json
import random
from datetime import date, datetime, timedelta
from pathlib import Path

SEMILLA = 42
N_EMPLEADOS = 30
N_DIAS = 5
PRIMER_DIA = date(2026, 11, 2)  # lunes

RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "data" / "nomina"

PUESTOS = ["albañil", "electricista", "operario_grua", "soldador", "ayudante", "supervisor_hse"]

# Turnos: hora de inicio y fin (formato HH:MM)
TURNOS = [
    {"id_turno": "MANANA", "inicio": "06:00", "fin": "14:00"},
    {"id_turno": "TARDE", "inicio": "14:00", "fin": "22:00"},
]

# Reglas configurables. reglas.py las leerá de aquí.
REGLAS = {
    "tolerancia_tardanza_min": 10,   # hasta 10 min tarde sigue siendo "presente"
    "ventana_duplicado_min": 2,      # misma marcación en <2 min = duplicada
}

# Probabilidades de comportamiento por empleado y día
P_AUSENTE = 0.08
P_TARDE = 0.15
P_SIN_SALIDA = 0.04
P_DUPLICADA = 0.04
N_BADGES_BLOQUEADOS = 2
N_INTENTOS_BADGE_INEXISTENTE = 3


def _hhmm(texto):
    h, m = texto.split(":")
    return int(h), int(m)


def _instante(dia, hhmm_texto, minutos=0):
    h, m = _hhmm(hhmm_texto)
    return datetime(dia.year, dia.month, dia.day, h, m) + timedelta(minutes=minutos)


def generar_empleados(rng):
    """30 empleados con ID pseudonimizado, puesto, turno y badge."""
    empleados = []
    for i in range(1, N_EMPLEADOS + 1):
        empleados.append({
            "id_empleado": f"EMP-{i:03d}",
            "puesto": rng.choice(PUESTOS),
            "id_turno": rng.choice(TURNOS)["id_turno"],
            "badge": f"BDG-{i:03d}",
            "estado_badge": "activo",
        })
    # Algunos badges quedan bloqueados (credencial desactivada)
    for emp in rng.sample(empleados, N_BADGES_BLOQUEADOS):
        emp["estado_badge"] = "bloqueado"
    return empleados


def generar_marcaciones(rng, empleados):
    """Marcaciones de badge durante N_DIAS, con casos normales y anómalos."""
    turnos = {t["id_turno"]: t for t in TURNOS}
    marcaciones = []

    for d in range(N_DIAS):
        dia = PRIMER_DIA + timedelta(days=d)
        for emp in empleados:
            if rng.random() < P_AUSENTE:
                continue  # no marcó nada: ausente

            turno = turnos[emp["id_turno"]]
            # Llegada: a tiempo (-10..+5 min) o tarde (+15..+60 min)
            if rng.random() < P_TARDE:
                desvio = rng.randint(15, 60)
            else:
                desvio = rng.randint(-10, 5)
            entrada = _instante(dia, turno["inicio"], desvio)
            marcaciones.append((entrada, emp["badge"], "entrada"))

            # Anomalía: marcación de entrada duplicada (segundos después)
            if rng.random() < P_DUPLICADA:
                marcaciones.append((entrada + timedelta(seconds=rng.randint(20, 60)),
                                    emp["badge"], "entrada"))

            # Salida (salvo que olvide marcarla)
            if rng.random() >= P_SIN_SALIDA:
                salida = _instante(dia, turno["fin"], rng.randint(-5, 20))
                marcaciones.append((salida, emp["badge"], "salida"))

    # Intentos con un badge que no existe en la nómina
    for _ in range(N_INTENTOS_BADGE_INEXISTENTE):
        dia = PRIMER_DIA + timedelta(days=rng.randrange(N_DIAS))
        hora = _instante(dia, "06:00", rng.randint(0, 600))
        marcaciones.append((hora, f"BDG-9{rng.randint(10, 99)}", "entrada"))

    marcaciones.sort(key=lambda x: x[0])
    return [
        {
            "id_marcacion": f"M-{i:04d}",
            "fecha": ts.strftime("%Y-%m-%d"),
            "hora": ts.strftime("%H:%M:%S"),
            "badge": badge,
            "tipo": tipo,
        }
        for i, (ts, badge, tipo) in enumerate(marcaciones, start=1)
    ]


def _escribir_csv(ruta, filas):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        w.writeheader()
        w.writerows(filas)


def main():
    rng = random.Random(SEMILLA)  # generador propio: no afecta al random global
    SALIDA.mkdir(parents=True, exist_ok=True)

    empleados = generar_empleados(rng)
    marcaciones = generar_marcaciones(rng, empleados)

    _escribir_csv(SALIDA / "empleados.csv", empleados)
    _escribir_csv(SALIDA / "turnos.csv", TURNOS)
    _escribir_csv(SALIDA / "marcaciones.csv", marcaciones)
    (SALIDA / "reglas.json").write_text(json.dumps(REGLAS, indent=2), encoding="utf-8")

    print(f"Empleados:   {len(empleados)}")
    print(f"Marcaciones: {len(marcaciones)}")
    print(f"Archivos en: {SALIDA}")


if __name__ == "__main__":
    main()
