"""Reglas deterministas de nómina de SAFESITE V2 (Agente 1).

Este módulo es la ÚNICA fuente de verdad sobre el estado de asistencia y las
horas trabajadas. Todo lo demás (banco de tareas, evaluación del LLM, agente)
se califica contra lo que estas funciones devuelven.

Son funciones puras: mismos datos de entrada -> misma salida, sin azar.
"""
import csv
import json
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "data" / "nomina"

# Estados posibles de un empleado en un día
PRESENTE = "presente"
TARDANZA = "tardanza"
BLOQUEADO = "bloqueado"
AUSENTE = "ausente"


# ---------------------------------------------------------------- carga

def cargar_datos(carpeta=DATOS):
    """Lee los archivos generados y los deja listos para consultar."""
    carpeta = Path(carpeta)

    def leer(nombre):
        with open(carpeta / nombre, encoding="utf-8", newline="") as f:
            return list(csv.DictReader(f))

    empleados = {e["badge"]: e for e in leer("empleados.csv")}  # clave: badge
    turnos = {t["id_turno"]: t for t in leer("turnos.csv")}     # clave: id_turno
    marcaciones = leer("marcaciones.csv")
    reglas = json.loads((carpeta / "reglas.json").read_text(encoding="utf-8"))
    return {"empleados": empleados, "turnos": turnos,
            "marcaciones": marcaciones, "reglas": reglas}


# ------------------------------------------------------------ utilidades

def _a_datetime(fecha, hora):
    """'2026-11-02' + '06:15:00' -> objeto datetime."""
    return datetime.strptime(f"{fecha} {hora}", "%Y-%m-%d %H:%M:%S")


def _inicio_turno(fecha, turno):
    return datetime.strptime(f"{fecha} {turno['inicio']}", "%Y-%m-%d %H:%M")


def marcaciones_del_dia(marcaciones, badge, fecha):
    """Marcaciones de un badge en una fecha, ordenadas por hora."""
    del_dia = [m for m in marcaciones if m["badge"] == badge and m["fecha"] == fecha]
    return sorted(del_dia, key=lambda m: m["hora"])


def entradas_validas(marcs_dia, ventana_duplicado_min):
    """Hora de cada entrada real, descartando duplicados.

    Una entrada repetida a menos de `ventana_duplicado_min` minutos de la
    anterior se considera un doble pase del badge y se ignora.
    """
    validas = []
    for m in marcs_dia:
        if m["tipo"] != "entrada":
            continue
        t = _a_datetime(m["fecha"], m["hora"])
        if validas and (t - validas[-1]).total_seconds() < ventana_duplicado_min * 60:
            continue  # duplicada
        validas.append(t)
    return validas


# --------------------------------------------------------------- reglas

def estado_asistencia(empleado, turno, marcs_dia, reglas):
    """Estado de un empleado en un día: presente, tardanza, bloqueado o ausente.

    Orden de decisión:
      1. Sin entrada ese día                -> ausente
      2. Con entrada pero badge bloqueado   -> bloqueado (prioridad sobre la hora)
      3. Entrada pasada la tolerancia       -> tardanza
      4. En cualquier otro caso             -> presente
    """
    entradas = entradas_validas(marcs_dia, reglas["ventana_duplicado_min"])
    if not entradas:
        return AUSENTE
    if empleado["estado_badge"] == "bloqueado":
        return BLOQUEADO

    primera = entradas[0]
    inicio = _inicio_turno(marcs_dia[0]["fecha"], turno)
    minutos_tarde = (primera - inicio).total_seconds() / 60
    if minutos_tarde > reglas["tolerancia_tardanza_min"]:
        return TARDANZA
    return PRESENTE


def minutos_trabajados(marcs_dia, ventana_duplicado_min):
    """Minutos entre la primera entrada válida y la última salida.

    Devuelve None si falta la entrada o la salida: no se inventan datos,
    ese caso queda 'incompleto' para revisión humana.
    """
    entradas = entradas_validas(marcs_dia, ventana_duplicado_min)
    salidas = [_a_datetime(m["fecha"], m["hora"]) for m in marcs_dia if m["tipo"] == "salida"]
    if not entradas or not salidas:
        return None
    return round((max(salidas) - entradas[0]).total_seconds() / 60)


def badges_inexistentes(datos):
    """Marcaciones cuyo badge no está en la nómina (intentos sospechosos)."""
    return [m for m in datos["marcaciones"] if m["badge"] not in datos["empleados"]]


def resumen_empleado_dia(datos, badge, fecha):
    """Estado y minutos trabajados de un empleado en una fecha."""
    empleado = datos["empleados"].get(badge)
    if empleado is None:
        return {"badge": badge, "fecha": fecha, "estado": "badge_inexistente",
                "minutos": None}
    turno = datos["turnos"][empleado["id_turno"]]
    marcs = marcaciones_del_dia(datos["marcaciones"], badge, fecha)
    return {
        "badge": badge,
        "fecha": fecha,
        "estado": estado_asistencia(empleado, turno, marcs, datos["reglas"]) if marcs
                  else AUSENTE,
        "minutos": minutos_trabajados(marcs, datos["reglas"]["ventana_duplicado_min"]),
    }
