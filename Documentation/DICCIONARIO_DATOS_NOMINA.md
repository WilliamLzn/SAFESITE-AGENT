# Diccionario de datos — Gestor y Verificador de Nómina LIVE (SAFESITE-AGENT)

**Proyecto:** SAFESITE-AGENT  
**Metodología:** CRISP-ML(Q) — Fase 2: Data Understanding  
**Versión:** 1.0  
**Fecha:** 02-nov-2026  
**Idioma:** español

---

## 1. Propósito y alcance

Este diccionario documenta las entidades, atributos, tipos, restricciones y significados de la base de datos que soporta el **gestor y verificador de nómina LIVE** de SAFESITE. Se aplica a la nueva funcionalidad (nómina, identificación, asistencia, liquidación, reportes) y se integra con la percepción de EPP existente.

**Regla de datos personales (curso):** no se almacenan nombres reales, cédulas ni salarios reales de empleados. Se usan **pseudónimos** (`pseudonimo`) y **códigos de badge** (`codigo_badge`). Los datos de prueba son sintéticos, generados con **semilla fija 42**.

---

## 2. Modelo de relaciones

El modelo es **multi-tenant por empresa**. Cada tabla lleva `empresa_id` para aislar datos entre empresas con Row Level Security (RLS).

```
empresa 1──N puesto
empresa 1──N empleado
empresa 1──N turno
empresa 1──N asistencia
empresa 1──N incidente
empresa 1──N periodo_nomina
empresa 1──N liquidacion
empresa 1──N regla

puesto 1──N empleado
turno 1──N empleado
empleado 1──N asistencia
empleado 1──N incidente
empleado 1──N liquidacion
periodo_nomina 1──N liquidacion
asistencia 1──N incidente
```

---

## 3. Tablas

### 3.1 `empresa` (catálogo)

| Atributo | Tipo | Nulo | Descripción | Restricción | Ejemplo |
|---|---|---|---|---|---|
| `id` | `UUID` | NO | Identificador único de la empresa | PK, `gen_random_uuid()` | `550e8400-e29b-41d4-a716-446655440000` |
| `nombre` | `VARCHAR(100)` | NO | Nombre comercial o razón social | NOT NULL | `Construcciones del Caribe S.A.S` |
| `nit` | `VARCHAR(20)` | NO | Número de identificación tributaria | UNIQUE | `900.123.456-7` |
| `created_at` | `TIMESTAMPTZ` | NO | Fecha de creación del registro | DEFAULT `now()` | `2026-11-02 08:00:00+00` |

### 3.2 `puesto` (catálogo)

| Atributo | Tipo | Nulo | Descripción | Restricción | Ejemplo |
|---|---|---|---|---|---|
| `id` | `UUID` | NO | Identificador único del puesto | PK | `...` |
| `empresa_id` | `UUID` | NO | Empresa a la que pertenece el puesto | FK → `empresa.id` | `...` |
| `nombre` | `VARCHAR(80)` | NO | Nombre del puesto | NOT NULL | `Operario de obra` |
| `epp_requerido` | `JSONB` | NO | Lista de EPP obligatorios para el puesto | NOT NULL, array de strings | `["casco","guantes","botas"]` |
| `created_at` | `TIMESTAMPTZ` | NO | Fecha de creación | DEFAULT `now()` | `...` |

### 3.3 `turno` (catálogo)

| Atributo | Tipo | Nulo | Descripción | Restricción | Ejemplo |
|---|---|---|---|---|---|
| `id` | `UUID` | NO | Identificador único del turno | PK | `...` |
| `empresa_id` | `UUID` | NO | Empresa | FK → `empresa.id` | `...` |
| `nombre` | `VARCHAR(60)` | NO | Nombre del turno | NOT NULL | `Mañana` |
| `hora_inicio` | `TIME` | NO | Hora de inicio programada | NOT NULL | `06:00:00` |
| `hora_fin` | `TIME` | NO | Hora de fin programada | NOT NULL | `14:00:00` |
| `descanso_min` | `INTEGER` | NO | Minutos de descanso no pagados | DEFAULT 30, ≥ 0 | `30` |
| `tolerancia_puntualidad_min` | `INTEGER` | NO | Minutos de tolerancia para entrada tardía | DEFAULT 10, ≥ 0 | `10` |
| `created_at` | `TIMESTAMPTZ` | NO | Fecha de creación | DEFAULT `now()` | `...` |

### 3.4 `empleado` (catálogo)

| Atributo | Tipo | Nulo | Descripción | Restricción | Ejemplo |
|---|---|---|---|---|---|
| `id` | `UUID` | NO | Identificador único del empleado | PK | `...` |
| `empresa_id` | `UUID` | NO | Empresa | FK → `empresa.id` | `...` |
| `codigo_badge` | `VARCHAR(20)` | NO | Código de badge/QR impreso | UNIQUE, NOT NULL | `BADGE-00123` |
| `pseudonimo` | `VARCHAR(80)` | NO | Pseudónimo del empleado (no nombre real) | NOT NULL | `Trabajador A` |
| `puesto_id` | `UUID` | NO | Puesto asignado | FK → `puesto.id` | `...` |
| `turno_id` | `UUID` | NO | Turno asignado por defecto | FK → `turno.id` | `...` |
| `salario_base_por_hora` | `NUMERIC(10,2)` | NO | Valor base por hora (datos de prueba, no real) | NOT NULL, ≥ 0 | `12500.00` |
| `activo` | `BOOLEAN` | NO | Indica si el empleado está activo | DEFAULT `true` | `true` |
| `created_at` | `TIMESTAMPTZ` | NO | Fecha de creación | DEFAULT `now()` | `...` |

### 3.5 `asistencia` (transaccional)

| Atributo | Tipo | Nulo | Descripción | Restricción | Ejemplo |
|---|---|---|---|---|---|
| `id` | `UUID` | NO | Identificador único del registro | PK | `...` |
| `empresa_id` | `UUID` | NO | Empresa | FK → `empresa.id` | `...` |
| `empleado_id` | `UUID` | NO | Empleado que marca | FK → `empleado.id` | `...` |
| `fecha` | `DATE` | NO | Fecha del registro | NOT NULL | `2026-11-02` |
| `entrada_ts` | `TIMESTAMPTZ` | SÍ | Timestamp de entrada | SÍ (puede estar vacío si aún no entra) | `2026-11-02 06:05:00+00` |
| `salida_ts` | `TIMESTAMPTZ` | SÍ | Timestamp de salida | SÍ (puede estar vacío si aún no sale) | `2026-11-02 14:10:00+00` |
| `frames_evidencia` | `JSONB` | SÍ | Rutas o hashes de frames de evidencia | Array de strings o null | `["frame_001.jpg", "frame_002.jpg"]` |
| `confianza_epp` | `NUMERIC(3,2)` | SÍ | Confianza media de detección EPP | Entre 0 y 1, null si no aplica | `0.87` |
| `estado` | `VARCHAR(20)` | NO | Estado del asistencia | CHECK: `presente`, `tardanza`, `ausente`, `bloqueado` | `presente` |
| `created_at` | `TIMESTAMPTZ` | NO | Fecha de creación | DEFAULT `now()` | `...` |
| `updated_at` | `TIMESTAMPTZ` | NO | Última actualización | DEFAULT `now()` | `...` |

### 3.6 `incidente` (transaccional)

| Atributo | Tipo | Nulo | Descripción | Restricción | Ejemplo |
|---|---|---|---|---|---|
| `id` | `UUID` | NO | Identificador único del incidente | PK | `...` |
| `empresa_id` | `UUID` | NO | Empresa | FK → `empresa.id` | `...` |
| `asistencia_id` | `UUID` | SÍ | Asistencia asociada (si aplica) | FK → `asistencia.id` | `...` |
| `empleado_id` | `UUID` | SÍ | Empleado involucrado | FK → `empleado.id` | `...` |
| `tipo` | `VARCHAR(40)` | NO | Tipo de incidente | CHECK: `falta_epp`, `no_registrado`, `salida_temprana`, `entrada_sin_salida`, `sensor_sin_dato` | `falta_epp` |
| `severidad` | `VARCHAR(20)` | NO | Severidad | CHECK: `baja`, `media`, `alta`, `critica` | `media` |
| `ts` | `TIMESTAMPTZ` | NO | Timestamp del incidente | DEFAULT `now()` | `2026-11-02 06:08:00+00` |
| `canal` | `VARCHAR(20)` | NO | Canal de notificación | CHECK: `whatsapp`, `consola`, `panel`, `ninguno` | `whatsapp` |
| `resuelto` | `BOOLEAN` | NO | Indica si fue revisado por humano | DEFAULT `false` | `false` |
| `created_at` | `TIMESTAMPTZ` | NO | Fecha de creación | DEFAULT `now()` | `...` |

### 3.7 `periodo_nomina` (administrativo)

| Atributo | Tipo | Nulo | Descripción | Restricción | Ejemplo |
|---|---|---|---|---|---|
| `id` | `UUID` | NO | Identificador único del período | PK | `...` |
| `empresa_id` | `UUID` | NO | Empresa | FK → `empresa.id` | `...` |
| `desde` | `DATE` | NO | Fecha inicio del período | NOT NULL | `2026-11-01` |
| `hasta` | `DATE` | NO | Fecha fin del período | NOT NULL | `2026-11-15` |
| `estado` | `VARCHAR(20)` | NO | Estado del período | CHECK: `abierto`, `cerrado`, `liquidado` | `abierto` |
| `created_at` | `TIMESTAMPTZ` | NO | Fecha de creación | DEFAULT `now()` | `...` |

### 3.8 `liquidacion` (administrativo)

| Atributo | Tipo | Nulo | Descripción | Restricción | Ejemplo |
|---|---|---|---|---|---|
| `id` | `UUID` | NO | Identificador único de la liquidación | PK | `...` |
| `periodo_id` | `UUID` | NO | Período de nómina | FK → `periodo_nomina.id` | `...` |
| `empleado_id` | `UUID` | NO | Empleado | FK → `empleado.id` | `...` |
| `horas_norm` | `NUMERIC(5,2)` | NO | Horas normales trabajadas | ≥ 0 | `40.00` |
| `horas_extra` | `NUMERIC(5,2)` | NO | Horas extra trabajadas | ≥ 0 | `5.00` |
| `descuentos` | `NUMERIC(10,2)` | NO | Descuentos aplicados | ≥ 0 | `25000.00` |
| `total` | `NUMERIC(12,2)` | NO | Total a pagar | `horas_norm * salario + horas_extra * 1.25 * salario - descuentos` | `525000.00` |
| `created_at` | `TIMESTAMPTZ` | NO | Fecha de creación | DEFAULT `now()` | `...` |

### 3.9 `regla` (configuración)

| Atributo | Tipo | Nulo | Descripción | Restricción | Ejemplo |
|---|---|---|---|---|---|
| `id` | `UUID` | NO | Identificador único de la regla | PK | `...` |
| `empresa_id` | `UUID` | NO | Empresa | FK → `empresa.id` | `...` |
| `key` | `VARCHAR(60)` | NO | Clave de configuración | NOT NULL | `cooldown_global_s` |
| `valor` | `TEXT` | NO | Valor de la regla | NOT NULL | `60` |
| `version` | `INTEGER` | NO | Versión de la regla | ≥ 1 | `1` |
| `activa` | `BOOLEAN` | NO | Indica si la regla está vigente | DEFAULT `true` | `true` |
| `created_at` | `TIMESTAMPTZ` | NO | Fecha de creación | DEFAULT `now()` | `...` |

---

## 4. Reglas de negocio representadas en datos

| Regla | Donde se aplica | Descripción |
|---|---|---|
| Un empleado tiene un solo turno por defecto | `empleado.turno_id` | FK obligatorio a `turno` |
| Un puesto requiere una lista de EPP | `puesto.epp_requerido` | JSONB con strings, usado por Agente 2 |
| Una asistencia tiene un solo empleado | `asistencia.empleado_id` | FK obligatorio |
| Un incidente puede vincularse a una asistencia | `incidente.asistencia_id` | FK opcional (persona no registrada no tiene asistencia) |
| Una liquidación pertenece a un período y un empleado | `liquidacion.periodo_id`, `liquidacion.empleado_id` | FK obligatorios |
| Las reglas son configurables por empresa y versión | `regla.empresa_id`, `regla.version` | Permite cambiar umbrales sin tocar código |

---

## 5. Códigos y dominios

| Dominio | Valores permitidos | Significado |
|---|---|---|
| `asistencia.estado` | `presente`, `tardanza`, `ausente`, `bloqueado` | Estado del registro de asistencia |
| `incidente.tipo` | `falta_epp`, `no_registrado`, `salida_temprana`, `entrada_sin_salida`, `sensor_sin_dato` | Tipo de incidente detectado |
| `incidente.severidad` | `baja`, `media`, `alta`, `critica` | Nivel de severidad |
| `incidente.canal` | `whatsapp`, `consola`, `panel`, `ninguno` | Canal usado para notificar |
| `periodo_nomina.estado` | `abierto`, `cerrado`, `liquidado` | Estado del período de nómina |
| `regla.key` | `cooldown_global_s`, `max_mensajes_hora`, `umbral_confianza_epp`, `tolerancia_puntualidad_min` | Claves de configuración |

---

## 6. Índices sugeridos

| Tabla | Columnas | Razón |
|---|---|---|
| `empleado` | `empresa_id`, `codigo_badge` | Búsqueda rápida por badge al entrar |
| `asistencia` | `empresa_id`, `empleado_id`, `fecha` | Consultas de asistencia por empleado y fecha |
| `asistencia` | `empresa_id`, `fecha` | Reportes diarios por empresa |
| `incidente` | `empresa_id`, `ts` | Histórico de incidentes por tiempo |
| `incidente` | `asistencia_id` | Vincular incidentes a asistencia |
| `liquidacion` | `periodo_id`, `empleado_id` | Liquidaciones por período y empleado |
| `regla` | `empresa_id`, `key`, `activa` | Obtener reglas vigentes por empresa |

---

## 7. Ejemplo de datos sintéticos (semilla 42)

| Tabla | Ejemplo (pseudónimo, sin datos reales) |
|---|---|
| `empresa` | `id=...`, `nombre=Construcciones del Caribe S.A.S`, `nit=900.123.456-7` |
| `puesto` | `id=...`, `nombre=Operario de obra`, `epp_requerido=["casco","guantes","botas"]` |
| `turno` | `id=...`, `nombre=Mañana`, `hora_inicio=06:00:00`, `hora_fin=14:00:00`, `tolerancia_puntualidad_min=10` |
| `empleado` | `id=...`, `codigo_badge=BADGE-00123`, `pseudonimo=Trabajador A`, `salario_base_por_hora=12500.00` |
| `asistencia` | `id=...`, `fecha=2026-11-02`, `entrada_ts=06:05:00+00`, `estado=tardanza` |
| `incidente` | `id=...`, `tipo=falta_epp`, `severidad=media`, `canal=whatsapp`, `resuelto=false` |

---

> **Nota:** Este diccionario es parte de la Fase 2 (Data Understanding) de CRISP-ML(Q). Se debe actualizar si el esquema cambia durante Data Preparation o Modeling.
