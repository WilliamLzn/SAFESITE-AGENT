"""SafeSite-Agent v2 — Módulo de asistencia y control de acceso por badge.

Integra el lector de QR con src/nomina/reglas.py para:
  - Validar que el badge existe en la nómina y está activo.
  - Registrar entrada/salida con timestamp.
  - Calcular horas trabajadas y valor a pagar (tarifa fija por hora).
  - Mantener el estado actual (dentro/fuera) de cada empleado.

Los datos se persisten en un archivo JSONL simple (sin servidor de BD),
suficiente para el alcance de la v2.
"""

import csv
import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.nomina.reglas import cargar_datos, entradas_validas, minutos_trabajados

RAIZ = Path(__file__).resolve().parents[2]
DATOS_NOMINA = RAIZ / "data" / "nomina"
DIR_ASISTENCIA = RAIZ / "runs" / "asistencia"
ARCHIVO_MARCACIONES = DIR_ASISTENCIA / "marcaciones_v2.jsonl"

# Tarifa fija por hora (convención del usuario: misma para todos)
TARIFA_POR_HORA = 15000  # pesos COP por hora (ajustable)

# Jornada laboral máxima antes de considerar "olvido de salida" (horas)
JORNADA_MAXIMA_HORAS = 12

# Umbral para considerar que un empleado se fue sin marcar salida
# (si lleva más de esto dentro sin salida, se marca como alerta)
UMBRAL_ALERTA_SIN_SALIDA_HORAS = 10


class RegistroAsistencia:
    """Gestiona entradas/salidas de badges y consulta la nómina."""

    def __init__(self, tarifa_por_hora=TARIFA_POR_HORA):
        self.tarifa_por_hora = tarifa_por_hora
        self.lock = threading.Lock()
        self._datos_nomina = None
        self._estado_actual = {}  # badge_id -> {"dentro": bool, "ultima_entrada": datetime|None}
        DIR_ASISTENCIA.mkdir(parents=True, exist_ok=True)
        self._cargar_nomina()
        self._recuperar_estado_desde_marcaciones()

    # ---------------------------------------------------------------- nomina

    def _cargar_nomina(self):
        """Carga empleados, turnos y reglas desde data/nomina."""
        try:
            self._datos_nomina = cargar_datos(DATOS_NOMINA)
        except Exception as e:
            print(f"⚠️  asistencia: no se pudo cargar la nómina: {e}", flush=True)
            self._datos_nomina = {"empleados": {}, "turnos": {}, "marcaciones": [], "reglas": {}}

    def empleado_por_badge(self, badge_id: str) -> Optional[dict]:
        """Devuelve la info del empleado para un badge, o None."""
        return self._datos_nomina["empleados"].get(badge_id)

    def badge_activo(self, badge_id: str) -> bool:
        """True si el badge existe y su estado es 'activo'."""
        emp = self.empleado_por_badge(badge_id)
        return emp is not None and emp.get("estado_badge") == "activo"

    # ---------------------------------------------------------------- estado

    def _recuperar_estado_desde_marcaciones(self):
        """Reconstruye quién está dentro leyendo el historial de marcaciones."""
        try:
            with open(ARCHIVO_MARCACIONES, encoding="utf-8") as f:
                for linea in f:
                    linea = linea.strip()
                    if not linea:
                        continue
                    m = json.loads(linea)
                    badge = m["badge"]
                    tipo = m["tipo"]
                    if tipo == "entrada":
                        self._estado_actual[badge] = {"dentro": True,
                                                      "ultima_entrada": m["timestamp"]}
                    elif tipo == "salida":
                        self._estado_actual[badge] = {"dentro": False,
                                                      "ultima_entrada": None}
        except FileNotFoundError:
            pass
        except Exception as e:
            print(f"⚠️  asistencia: error recuperando estado: {e}", flush=True)

    def esta_dentro(self, badge_id: str) -> bool:
        """True si el badge tiene una entrada sin salida correspondiente."""
        with self.lock:
            est = self._estado_actual.get(badge_id)
            return bool(est and est.get("dentro", False))

    # ---------------------------------------------------------------- marcar

    def marcar_entrada(self, badge_id: str) -> dict:
        """Registra una entrada. Devuelve dict con resultado."""
        ahora = datetime.now()
        timestamp = ahora.isoformat()
        with self.lock:
            if self.esta_dentro(badge_id):
                return {"ok": False, "tipo": "entrada",
                        "motivo": "ya_registrado_dentro",
                        "timestamp": timestamp, "badge": badge_id}
            self._estado_actual[badge_id] = {"dentro": True, "ultima_entrada": timestamp}
            self._persistir_marcacion(badge_id, "entrada", timestamp)
        return {"ok": True, "tipo": "entrada",
                "timestamp": timestamp, "badge": badge_id}

    def marcar_salida(self, badge_id: str) -> dict:
        """Registra una salida. Devuelve dict con resultado."""
        ahora = datetime.now()
        timestamp = ahora.isoformat()
        with self.lock:
            if not self.esta_dentro(badge_id):
                return {"ok": False, "tipo": "salida",
                        "motivo": "no_esta_dentro",
                        "timestamp": timestamp, "badge": badge_id}
            self._estado_actual[badge_id] = {"dentro": False, "ultima_entrada": None}
            self._persistir_marcacion(badge_id, "salida", timestamp)
        return {"ok": True, "tipo": "salida",
                "timestamp": timestamp, "badge": badge_id}

    def _persistir_marcacion(self, badge_id, tipo, timestamp):
        """Guarda una marcación en el JSONL."""
        registro = {
            "badge": badge_id,
            "tipo": tipo,
            "timestamp": timestamp,
            "fecha": datetime.now().strftime("%Y-%m-%d"),
            "hora": datetime.now().strftime("%H:%M:%S"),
        }
        with open(ARCHIVO_MARCACIONES, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")

    # ---------------------------------------------------------------- consultas

    def resumen_empleado(self, badge_id: str) -> dict:
        """Estado actual, horas trabajadas hoy y valor a pagar."""
        emp = self.empleado_por_badge(badge_id)
        if emp is None:
            return {
                "badge": badge_id,
                "existe": False,
                "estado": "badge_inexistente",
            }

        dentro = self.esta_dentro(badge_id)
        hoy = datetime.now().strftime("%Y-%m-%d")

        # cargar marcaciones del día desde el JSONL
        marcs_hoy = self._marcaciones_del_dia(badge_id, hoy)

        minutos = minutos_trabajados(marcs_hoy,
                                     self._datos_nomina["reglas"].get("ventana_duplicado_min", 5))
        horas = round(minutos / 60, 2) if minutos is not None else 0.0
        valor_pagar = round(horas * self.tarifa_por_hora, 0) if minutos is not None else 0

        return {
            "badge": badge_id,
            "existe": True,
            "id_empleado": emp.get("id_empleado", ""),
            "nombre": emp.get("nombre", emp.get("id_empleado", "")),
            "puesto": emp.get("puesto", ""),
            "turno": emp.get("id_turno", ""),
            "estado_badge": emp.get("estado_badge", ""),
            "dentro": dentro,
            "minutos_hoy": minutos,
            "horas_hoy": horas,
            "valor_pagar": valor_pagar,
            "tarifa_por_hora": self.tarifa_por_hora,
            "fecha": hoy,
        }

    def _marcaciones_del_dia(self, badge_id, fecha):
        """Lee marcaciones de un badge en una fecha desde el JSONL."""
        resultado = []
        try:
            with open(ARCHIVO_MARCACIONES, encoding="utf-8") as f:
                for linea in f:
                    linea = linea.strip()
                    if not linea:
                        continue
                    m = json.loads(linea)
                    if m["badge"] == badge_id and m["fecha"] == fecha:
                        resultado.append(m)
        except FileNotFoundError:
            pass
        return resultado

    def listar_todos(self) -> list:
        """Resumen de todos los empleados con su estado actual."""
        salida = []
        for badge_id, emp in self._datos_nomina["empleados"].items():
            res = self.resumen_empleado(badge_id)
            salida.append(res)
        salida.sort(key=lambda x: x.get("badge", ""))
        return salida

    # ---------------------------------------------------------------- jornada

    def obtener_jornadas_sin_salida(self) -> list:
        """Detecta empleados que entraron pero no salieron y excedieron
        la jornada máxima. Devuelve lista de alertas para el administrador."""
        alertas = []
        ahora = datetime.now()
        for badge_id, estado in self._estado_actual.items():
            if not estado.get("dentro", False):
                continue  # ya salió
            emp = self.empleado_por_badge(badge_id)
            if emp is None:
                continue
            ultima_entrada = estado.get("ultima_entrada")
            if not ultima_entrada:
                continue
            try:
                t_entrada = datetime.fromisoformat(ultima_entrada)
            except Exception:
                continue
            horas_dentro = round((ahora - t_entrada).total_seconds() / 3600, 2)
            if horas_dentro > UMBRAL_ALERTA_SIN_SALIDA_HORAS:
                alertas.append({
                    "badge": badge_id,
                    "id_empleado": emp.get("id_empleado", ""),
                    "nombre": emp.get("nombre", emp.get("id_empleado", "")),
                    "puesto": emp.get("puesto", ""),
                    "turno": emp.get("id_turno", ""),
                    "hora_entrada": ultima_entrada,
                    "horas_dentro": horas_dentro,
                    "excede_jornada_maxima": horas_dentro > JORNADA_MAXIMA_HORAS,
                    "tipo_alerta": "sin_salida",
                })
        return alertas

    def cancelar_nomina_por_olvido_salida(self, badge_id: str) -> dict:
        """Marca al empleado como fuera y cancela la nómina del día
        por no haber marcado salida dentro de la jornada máxima."""
        emp = self.empleado_por_badge(badge_id)
        if emp is None:
            return {"ok": False, "motivo": "badge_inexistente"}
        ahora = datetime.now()
        timestamp = ahora.isoformat()
        with self.lock:
            if not self.esta_dentro(badge_id):
                return {"ok": False, "motivo": "ya_esta_fuera"}
            self._estado_actual[badge_id] = {"dentro": False, "ultima_entrada": None}
            self._persistir_marcacion(badge_id, "salida_forzada", timestamp)
        return {
            "ok": True,
            "tipo": "salida_forzada",
            "badge": badge_id,
            "nombre": emp.get("nombre", ""),
            "timestamp": timestamp,
            "motivo": "excede_jornada_maxima_sin_salida",
        }

    def resumen_empleado(self, badge_id: str) -> dict:
        """Estado actual, horas trabajadas hoy y valor a pagar."""
        emp = self.empleado_por_badge(badge_id)
        if emp is None:
            return {
                "badge": badge_id,
                "existe": False,
                "estado": "badge_inexistente",
            }

        dentro = self.esta_dentro(badge_id)
        hoy = datetime.now().strftime("%Y-%m-%d")

        # cargar marcaciones del día desde el JSONL
        marcs_hoy = self._marcaciones_del_dia(badge_id, hoy)

        minutos = minutos_trabajados(marcs_hoy,
                                     self._datos_nomina["reglas"].get("ventana_duplicado_min", 5))
        horas = round(minutos / 60, 2) if minutos is not None else 0.0
        valor_pagar = round(horas * self.tarifa_por_hora, 0) if minutos is not None else 0

        # Calcular horas dentro ahora mismo si está adentro
        horas_dentro_ahora = None
        if dentro:
            estado = self._estado_actual.get(badge_id, {})
            ultima_entrada = estado.get("ultima_entrada")
            if ultima_entrada:
                try:
                    t_entrada = datetime.fromisoformat(ultima_entrada)
                    horas_dentro_ahora = round(
                        (datetime.now() - t_entrada).total_seconds() / 3600, 2)
                except Exception:
                    pass

        return {
            "badge": badge_id,
            "existe": True,
            "id_empleado": emp.get("id_empleado", ""),
            "nombre": emp.get("nombre", emp.get("id_empleado", "")),
            "puesto": emp.get("puesto", ""),
            "turno": emp.get("id_turno", ""),
            "estado_badge": emp.get("estado_badge", ""),
            "dentro": dentro,
            "minutos_hoy": minutos,
            "horas_hoy": horas,
            "valor_pagar": valor_pagar,
            "tarifa_por_hora": self.tarifa_por_hora,
            "fecha": hoy,
            "horas_dentro_ahora": horas_dentro_ahora,
            "excede_jornada_maxima": (
                horas_dentro_ahora is not None
                and horas_dentro_ahora > JORNADA_MAXIMA_HORAS
            ),
        }


# Instancia compartida (singleton) para usar desde el panel y otros módulos.
registro_asistencia = RegistroAsistencia()
