"""Genera el banco de tareas de prueba (experiments/tareas_v1.json).

Cada tarea es una pregunta de nómina + la respuesta esperada. La respuesta
SIEMPRE se calcula llamando a las funciones de reglas.py, nunca a mano.
Así la evaluación del LLM y del agente es objetiva y reproducible.

Uso (desde la raíz del repo):
    python -m src.nomina.generar_tareas
"""
import json
import random
from pathlib import Path

from src.nomina import reglas as R

SEMILLA = 42
RAIZ = Path(__file__).resolve().parents[2]
SALIDA = RAIZ / "experiments" / "tareas_v1.json"


def main():
    rng = random.Random(SEMILLA)
    datos = R.cargar_datos()
    cfg = datos["reglas"]
    ventana = cfg["ventana_duplicado_min"]
    empleados = datos["empleados"]
    fechas = sorted({m["fecha"] for m in datos["marcaciones"]})

    # --- Tabla (badge, fecha) -> info, para buscar candidatos por tipo -----
    casos = []
    for badge, emp in empleados.items():
        for fecha in fechas:
            marcs = R.marcaciones_del_dia(datos["marcaciones"], badge, fecha)
            res = R.resumen_empleado_dia(datos, badge, fecha)
            entradas_crudas = [m for m in marcs if m["tipo"] == "entrada"]
            casos.append({
                "badge": badge, "fecha": fecha, "emp": emp, "marcs": marcs,
                "estado": res["estado"], "minutos": res["minutos"],
                "duplicado": len(entradas_crudas) > len(R.entradas_validas(marcs, ventana)),
                "sin_salida": bool(entradas_crudas) and not any(m["tipo"] == "salida" for m in marcs),
            })

    tareas = []

    def agregar(tipo, pregunta, esperada, tipo_respuesta, **extra):
        tareas.append({"id": f"T{len(tareas) + 1:02d}", "tipo": tipo,
                       "pregunta": pregunta, "respuesta_esperada": esperada,
                       "tipo_respuesta": tipo_respuesta, **extra})

    # 1. Estado de asistencia: uno por cada estado posible (4 tareas)
    for estado in ["presente", "tardanza", "ausente", "bloqueado"]:
        c = rng.choice([c for c in casos if c["estado"] == estado])
        agregar("estado_asistencia",
                f"¿Cuál fue el estado de asistencia del badge {c['badge']} el {c['fecha']}? "
                "Responde solo con una palabra: presente, tardanza, bloqueado o ausente.",
                c["estado"], "categoria", badge=c["badge"], fecha=c["fecha"])

    # 2. Horas trabajadas (jornadas completas)
    for c in rng.sample([c for c in casos if c["minutos"] is not None and not c["duplicado"]], 3):
        agregar("horas_trabajadas",
                f"¿Cuántos minutos trabajó el badge {c['badge']} el {c['fecha']}? "
                "Responde solo con el número entero.",
                c["minutos"], "entero", tolerancia=1, badge=c["badge"], fecha=c["fecha"])

    # 3. Badge inexistente
    for m in R.badges_inexistentes(datos):
        agregar("badge_inexistente",
                f"El badge {m['badge']} marcó {m['tipo']} el {m['fecha']} a las {m['hora']}. "
                "¿Cuál es su estado en la nómina? Responde solo: badge_inexistente o empleado_valido.",
                "badge_inexistente", "categoria", badge=m["badge"], fecha=m["fecha"])

    # 4. Entrada duplicada: cuántas entradas válidas quedan
    for c in rng.sample([c for c in casos if c["duplicado"]], 3):
        n = len(R.entradas_validas(c["marcs"], ventana))
        agregar("entrada_duplicada",
                f"El badge {c['badge']} pasó el lector más de una vez como entrada el {c['fecha']}. "
                "¿Cuántas entradas válidas tiene ese día, descartando duplicados? Responde solo el número.",
                n, "entero", badge=c["badge"], fecha=c["fecha"])

    # 5. Entrada sin salida: las horas deben quedar sin dato
    for c in rng.sample([c for c in casos if c["sin_salida"]], 3):
        agregar("entrada_sin_salida",
                f"¿Cuántos minutos trabajó el badge {c['badge']} el {c['fecha']}? "
                "Si no se puede calcular con certeza, responde exactamente: incompleto. "
                "Si se puede, responde el número entero.",
                "incompleto", "categoria", badge=c["badge"], fecha=c["fecha"])

    # 6. Cambio de turno: empleado de TARDE reasignado a MANANA ese día
    for c in rng.sample([c for c in casos if c["emp"]["id_turno"] == "TARDE"
                         and c["emp"]["estado_badge"] == "activo" and c["marcs"]], 3):
        emp_nuevo = {**c["emp"], "id_turno": "MANANA"}
        esperado = R.estado_asistencia(emp_nuevo, datos["turnos"]["MANANA"], c["marcs"], cfg)
        agregar("cambio_de_turno",
                f"El badge {c['badge']} estaba en el turno TARDE, pero el {c['fecha']} fue "
                "reasignado al turno MANANA. Con sus marcaciones reales de ese día, "
                "¿cuál es su estado? Responde solo: presente, tardanza, bloqueado o ausente.",
                esperado, "categoria", badge=c["badge"], fecha=c["fecha"])

    # 7. Cierre de jornada: total de minutos trabajados por todos en un día
    for fecha in rng.sample(fechas, 3):
        total = sum(c["minutos"] for c in casos if c["fecha"] == fecha and c["minutos"] is not None)
        agregar("cierre_jornada",
                f"Al cerrar el {fecha}, ¿cuántos minutos trabajaron en total todos los empleados "
                "con jornada completa (entrada y salida)? Responde solo el número entero.",
                total, "entero", tolerancia=1, fecha=fecha)

    # 8. Reporte agregado
    f1, f2, f3 = rng.sample(fechas, 3)
    n_tard = sum(1 for c in casos if c["fecha"] == f1 and c["estado"] == "tardanza")
    agregar("reporte_agregado",
            f"¿Cuántos empleados llegaron con tardanza el {f1}? Responde solo el número.",
            n_tard, "entero", fecha=f1)
    n_aus = sum(1 for c in casos if c["estado"] == "ausente")
    agregar("reporte_agregado",
            f"En toda la semana ({fechas[0]} a {fechas[-1]}), ¿cuántas ausencias (empleado-día) hubo? "
            "Responde solo el número.",
            n_aus, "entero")
    n_pres = sum(1 for c in casos if c["fecha"] == f3 and c["estado"] == "presente")
    agregar("reporte_agregado",
            f"¿Cuántos empleados quedaron en estado presente el {f3}? Responde solo el número.",
            n_pres, "entero", fecha=f3)

    SALIDA.parent.mkdir(parents=True, exist_ok=True)
    SALIDA.write_text(json.dumps({"semilla": SEMILLA, "n_tareas": len(tareas), "tareas": tareas},
                                 indent=2, ensure_ascii=False), encoding="utf-8")

    por_tipo = {}
    for t in tareas:
        por_tipo[t["tipo"]] = por_tipo.get(t["tipo"], 0) + 1
    print(f"{len(tareas)} tareas -> {SALIDA}")
    for tipo, n in por_tipo.items():
        print(f"  {tipo}: {n}")


if __name__ == "__main__":
    main()
