"""SafeSite-Agent v2 — Módulo de asistencia y control de acceso por badge.

Integra el lector de QR con src/nomina/reglas.py para:
  - Validar que el badge existe en la nómina y está activo.
  - Registrar entrada/salida con timestamp.
  - Calcular horas trabajadas y valor a pagar (tarifa fija por hora).
  - Mantener el estado actual (dentro/fuera) de cada empleado.

ESCALA DE TIEMPO DE PRUEBA:
  - 10 segundos reales = 1 hora de trabajo (para pruebas rápidas).
  - Se usa FACTOR_TIEMPO = 360.0 (3600s / 10s = 360).

Los datos se persisten en un archivo JSONL simple (sin servidor de BD),
suficiente para el alcance de la v2.
"""

import csv
import json
import threading
from datetime import datetime, timedelta, date
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

# Tolerancia (minutos) sobre la hora de fin de turno para considerar
# que la salida fue "mal trazada" (se fue pero no marco salida).
# Dentro de esta ventana no se considera olvido intencional.
TOLERANCIA_SALIDA_MIN = 30

# ESCALA DE PRUEBA: 10 segundos reales = 1 hora de trabajo
# Factor = 3600 segundos (1 hora) / 10 segundos (escala) = 360
FACTOR_TIEMPO = 360.0  # cada segundo real = 360 segundos de trabajo (6 minutos)


def _ahora_real() -> datetime:
    """Devuelve la hora real actual."""
    return datetime.now()


def _hora_trabajada_desde(fecha_entrada: datetime) -> float:
    """Calcula horas trabajadas usando la escala acelerada.

    10 segundos reales = 1 hora de trabajo.
    Devuelve horas como float.
    """
    ahora = _ahora_real()
    segundos_reales = (ahora - fecha_entrada).total_seconds()
    if segundos_reales < 0:
        return 0.0
    horas = (segundos_reales * FACTOR_TIEMPO) / 3600.0
    return round(horas, 2)


class RegistroAsistencia:
    """Gestiona entradas/salidas de badges y consulta la nómina."""

    def __init__(self, tarifa_por_hora=TARIFA_POR_HORA):
        self.tarifa_por_hora = tarifa_por_hora
        self.lock = threading.Lock()
        self._datos_nomina = None
        # _estado_actual: badge_id -> {"dentro": bool, "ultima_entrada": datetime|None}
        self._estado_actual = {}
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
        ahora = _ahora_real()
        timestamp = ahora.isoformat()
        print(f"📝 [asistencia] marcar_entrada({badge_id}) iniciado", flush=True)
        with self.lock:
            est = self._estado_actual.get(badge_id)
            if est and est.get("dentro", False):
                print(f"⚠️ [asistencia] {badge_id} ya está dentro, ignorando entrada duplicada", flush=True)
                return {"ok": False, "tipo": "entrada",
                        "motivo": "ya_registrado_dentro",
                        "timestamp": timestamp, "badge": badge_id}
            self._estado_actual[badge_id] = {"dentro": True, "ultima_entrada": timestamp}
            print(f"💾 [asistencia] persistiendo entrada de {badge_id}", flush=True)
            self._persistir_marcacion(badge_id, "entrada", timestamp)
        print(f"✅ [asistencia] entrada de {badge_id} registrada OK", flush=True)
        return {"ok": True, "tipo": "entrada",
                "timestamp": timestamp, "badge": badge_id}

    def marcar_salida(self, badge_id: str) -> dict:
        """Registra una salida. Devuelve dict con resultado."""
        ahora = _ahora_real()
        timestamp = ahora.isoformat()
        print(f"📝 [asistencia] marcar_salida({badge_id}) iniciado", flush=True)
        with self.lock:
            est = self._estado_actual.get(badge_id)
            if not est or not est.get("dentro", False):
                print(f"⚠️ [asistencia] {badge_id} no está dentro, ignorando salida", flush=True)
                return {"ok": False, "tipo": "salida",
                        "motivo": "no_esta_dentro",
                        "timestamp": timestamp, "badge": badge_id}
            self._estado_actual[badge_id] = {"dentro": False, "ultima_entrada": None}
            print(f"💾 [asistencia] persistiendo salida de {badge_id}", flush=True)
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
        """Estado actual, horas trabajadas y valor a pagar.

        Usa la escala acelerada: 10s reales = 1h de trabajo.
        """
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

        # Calcular horas usando escala acelerada si está dentro ahora
        horas_dentro_ahora = None
        if dentro:
            estado = self._estado_actual.get(badge_id, {})
            ultima_entrada = estado.get("ultima_entrada")
            if ultima_entrada:
                try:
                    t_entrada = datetime.fromisoformat(ultima_entrada)
                    horas_dentro_ahora = _hora_trabajada_desde(t_entrada)
                except Exception:
                    pass

        # Horas acumuladas desde marcaciones persistidas (para horas totales del día)
        minutos = minutos_trabajados(marcs_hoy,
                                     self._datos_nomina["reglas"].get("ventana_duplicado_min", 5))
        # Convertir minutos a horas usando escala acelerada
        horas_acumuladas = round((minutos or 0) * FACTOR_TIEMPO / 60.0, 2) if minutos else 0.0

        # Usar horas_dentro_ahora si está dentro, sino las acumuladas
        horas_finales = horas_dentro_ahora if dentro else horas_acumuladas
        valor_pagar = round(horas_finales * self.tarifa_por_hora, 0) if horas_finales else 0

        # Horas y valor de la semana actual
        semana = self.obtener_horas_semana(badge_id)

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
            "horas_hoy": horas_finales,
            "valor_pagar": valor_pagar,
            "tarifa_por_hora": self.tarifa_por_hora,
            "fecha": hoy,
            "horas_dentro_ahora": horas_dentro_ahora,
            "excede_jornada_maxima": (
                horas_dentro_ahora is not None
                and horas_dentro_ahora > JORNADA_MAXIMA_HORAS
            ),
            # ---------- acumulado semanal ----------
            "horas_semana": semana.get("horas_semana", 0.0),
            "valor_semana": semana.get("valor_semana", 0),
            "sesiones_semana": semana.get("sesiones", 0),
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
        ahora = _ahora_real()
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
            horas_dentro = _hora_trabajada_desde(t_entrada)
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

    # ---------------------------------------------------------------- horas semana

    def obtener_horas_semana(self, badge_id: str) -> dict:
        """Horas trabajadas y valor a pagar de la semana actual
        (lunes a domingo), sumando sesiones completadas (entrada + salida).

        Usa la escala acelerada: 10s reales = 1h de trabajo.
        """
        emp = self.empleado_por_badge(badge_id)
        if emp is None:
            return {"badge": badge_id, "existe": False, "horas_semana": 0.0,
                    "valor_semana": 0, "sesiones": 0}

        hoy = date.today()
        inicio_semana = hoy - timedelta(days=hoy.weekday())  # lunes
        fin_semana = inicio_semana + timedelta(days=6)  # domingo

        total_horas = 0.0
        sesiones = 0

        # Leer todas las marcaciones del badge en el rango de la semana
        try:
            with open(ARCHIVO_MARCACIONES, encoding="utf-8") as f:
                entradas_por_dia = {}
                salidas_por_dia = {}
                for linea in f:
                    linea = linea.strip()
                    if not linea:
                        continue
                    m = json.loads(linea)
                    if m["badge"] != badge_id:
                        continue
                    fecha_m = datetime.strptime(m["fecha"], "%Y-%m-%d").date()
                    if fecha_m < inicio_semana or fecha_m > fin_semana:
                        continue
                    clave = m["fecha"]
                    if m["tipo"] == "entrada":
                        entradas_por_dia.setdefault(clave, []).append(m["hora"])
                    elif m["tipo"] == "salida":
                        salidas_por_dia.setdefault(clave, []).append(m["hora"])
        except FileNotFoundError:
            return {"badge": badge_id, "existe": True, "horas_semana": 0.0,
                    "valor_semana": 0, "sesiones": 0}

        # Emparejar primera entrada con última salida de cada día
        for fecha_str in sorted(set(list(entradas_por_dia.keys()) + list(salidas_por_dia.keys()))):
            ents = entradas_por_dia.get(fecha_str, [])
            sais = salidas_por_dia.get(fecha_str, [])
            if not ents or not sais:
                continue  # sesion incompleta, no se cuenta
            t_entrada = datetime.strptime(f"{fecha_str} {ents[0]}", "%Y-%m-%d %H:%M:%S")
            t_salida = datetime.strptime(f"{fecha_str} {max(sais)}", "%Y-%m-%d %H:%M:%S")
            if t_salida <= t_entrada:
                continue
            segundos_reales = (t_salida - t_entrada).total_seconds()
            horas_sesion = (segundos_reales * FACTOR_TIEMPO) / 3600.0
            total_horas += round(horas_sesion, 2)
            sesiones += 1

        total_horas = round(total_horas, 2)
        valor_semana = round(total_horas * self.tarifa_por_hora, 0)

        return {
            "badge": badge_id,
            "existe": True,
            "horas_semana": total_horas,
            "valor_semana": valor_semana,
            "sesiones": sesiones,
            "tarifa_por_hora": self.tarifa_por_hora,
            "inicio_semana": inicio_semana.isoformat(),
            "fin_semana": fin_semana.isoformat(),
        }

    # ---------------------------------------------------------------- salida mal trazada

    def _turno_de_empleado(self, badge_id: str) -> Optional[dict]:
        """Devuelve el turno configurado del empleado, o None."""
        emp = self.empleado_por_badge(badge_id)
        if emp is None:
            return None
        return self._datos_nomina["turnos"].get(emp.get("id_turno", ""))

    def obtener_jornadas_sin_salida(self) -> list:
        """Detecta empleados que entraron pero no salieron.

        Incluye dos tipos de alerta:
          - 'sin_salida': estuvo dentro mas de UMBRAL_ALERTA_SIN_SALIDA_HORAS
            (hora real, sin escala acelerada).
          - 'salida_mal_trazada': estuvo dentro mas allá del fin de su turno
            + TOLERANCIA_SALIDA_MIN (30 min), pero dentro del umbral absoluto.
            Se considera que se fue pero no marco salida -> amonestación.
        """
        alertas = []
        ahora_real = datetime.now()
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

            # Horas dentro usando escala acelerada (para UI y valor)
            horas_dentro = _hora_trabajada_desde(t_entrada)

            # Tiempo REAL transcurrido desde la entrada (para comparar con turno)
            segundos_reales = (ahora_real - t_entrada).total_seconds()
            horas_reales = segundos_reales / 3600.0

            turno = self._turno_de_empleado(badge_id)
            hora_fin_turno = None
            if turno and turno.get("hora_fin"):
                try:
                    h, m = map(int, turno["hora_fin"].split(":"))
                    # Construir datetime de fin de turno hoy
                    hoy = ahora_real.date()
                    hora_fin_turno = datetime.combine(hoy, datetime.min.time().replace(hour=h, minute=m))
                    # Si el turno es de tarde y ya pasó la medianoche, ajustar
                    if hora_fin_turno < t_entrada:
                        hora_fin_turno += timedelta(days=1)
                except Exception:
                    hora_fin_turno = None

            excede_maxima = horas_dentro > JORNADA_MAXIMA_HORAS
            salida_mal_trazada = False

            if hora_fin_turno is not None:
                # Tiempo lógico de salida: fin de turno + tolerancia
                limite_salida = hora_fin_turno + timedelta(minutes=TOLERANCIA_SALIDA_MIN)
                if ahora_real > limite_salida:
                    salida_mal_trazada = True

            if salida_mal_trazada:
                alertas.append({
                    "badge": badge_id,
                    "id_empleado": emp.get("id_empleado", ""),
                    "nombre": emp.get("nombre", emp.get("id_empleado", "")),
                    "puesto": emp.get("puesto", ""),
                    "turno": emp.get("id_turno", ""),
                    "hora_entrada": ultima_entrada,
                    "horas_dentro": horas_dentro,
                    "horas_reales": round(horas_reales, 2),
                    "excede_jornada_maxima": excede_maxima,
                    "tipo_alerta": "salida_mal_trazada",
                    "severidad": "alta" if excede_maxima else "media",
                    "motivo": (
                        f"Sobrepasó el fin de turno ({turno['hora_fin'] if turno else '—'}) "
                        f"más de {TOLERANCIA_SALIDA_MIN} min sin marcar salida."
                    ),
                })
            elif horas_dentro > UMBRAL_ALERTA_SIN_SALIDA_HORAS:
                alertas.append({
                    "badge": badge_id,
                    "id_empleado": emp.get("id_empleado", ""),
                    "nombre": emp.get("nombre", emp.get("id_empleado", "")),
                    "puesto": emp.get("puesto", ""),
                    "turno": emp.get("id_turno", ""),
                    "hora_entrada": ultima_entrada,
                    "horas_dentro": horas_dentro,
                    "excede_jornada_maxima": excede_maxima,
                    "tipo_alerta": "sin_salida",
                    "severidad": "critica" if excede_maxima else "alta",
                    "motivo": "No ha marcado salida y supera el umbral de alerta.",
                })
        return alertas

    def cancelar_nomina_por_olvido_salida(self, badge_id: str) -> dict:
        """Marca al empleado como fuera y cancela la nómina del día
        por no haber marcado salida dentro de la jornada máxima."""
        emp = self.empleado_por_badge(badge_id)
        if emp is None:
            return {"ok": False, "motivo": "badge_inexistente"}
        ahora = _ahora_real()
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


# Instancia compartida (singleton) para usar desde el panel y otros módulos.
registro_asistencia = RegistroAsistencia()
