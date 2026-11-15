-- ============================================================================
-- Esquema de base de datos — SAFESITE-AGENT (inicializacion Docker Postgres)
-- Ejecutado automaticamente al iniciar el contenedor db.
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ----------------------------------------------------------------------------
-- 1. empresa (catálogo, multi-tenant)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS empresa (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nombre VARCHAR(100) NOT NULL,
    nit VARCHAR(20) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- 2. puesto (catálogo)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS puesto (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    nombre VARCHAR(80) NOT NULL,
    epp_requerido JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- 3. turno (catálogo)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS turno (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    nombre VARCHAR(60) NOT NULL,
    hora_inicio TIME NOT NULL,
    hora_fin TIME NOT NULL,
    descanso_min INTEGER NOT NULL DEFAULT 60 CHECK (descanso_min >= 0),
    tolerancia_puntualidad_min INTEGER NOT NULL DEFAULT 10 CHECK (tolerancia_puntualidad_min >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- 4. empleado (catálogo)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS empleado (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    codigo_badge VARCHAR(20) NOT NULL UNIQUE,
    pseudonimo VARCHAR(80) NOT NULL,
    puesto_id UUID NOT NULL REFERENCES puesto(id) ON DELETE RESTRICT,
    turno_id UUID NOT NULL REFERENCES turno(id) ON DELETE RESTRICT,
    salario_base_por_hora NUMERIC(10,2) NOT NULL CHECK (salario_base_por_hora >= 0),
    activo BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- 5. asistencia (transaccional)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS asistencia (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    empleado_id UUID NOT NULL REFERENCES empleado(id) ON DELETE CASCADE,
    fecha DATE NOT NULL,
    entrada_ts TIMESTAMPTZ,
    salida_ts TIMESTAMPTZ,
    frames_evidencia JSONB,
    confianza_epp NUMERIC(3,2) CHECK (confianza_epp BETWEEN 0 AND 1),
    estado VARCHAR(20) NOT NULL CHECK (estado IN ('presente','tardanza','ausente','bloqueado')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (empleado_id, fecha)
);

-- ----------------------------------------------------------------------------
-- 6. incidente (transaccional) — incluye alertas de jornada
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS incidente (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    asistencia_id UUID REFERENCES asistencia(id) ON DELETE SET NULL,
    empleado_id UUID REFERENCES empleado(id) ON DELETE SET NULL,
    tipo VARCHAR(40) NOT NULL CHECK (tipo IN (
        'falta_epp','no_registrado','salida_temprana','entrada_sin_salida',
        'salida_mal_trazada','sensor_sin_dato','exceso_jornada'
    )),
    severidad VARCHAR(20) NOT NULL CHECK (severidad IN ('baja','media','alta','critica')),
    ts TIMESTAMPTZ NOT NULL DEFAULT now(),
    canal VARCHAR(20) NOT NULL CHECK (canal IN ('whatsapp','consola','panel','ninguno')),
    resuelto BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ----------------------------------------------------------------------------
-- 7. periodo_nomina (administrativo)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS periodo_nomina (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    desde DATE NOT NULL,
    hasta DATE NOT NULL,
    estado VARCHAR(20) NOT NULL CHECK (estado IN ('abierto','cerrado','liquidado')) DEFAULT 'abierto',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (hasta >= desde)
);

-- ----------------------------------------------------------------------------
-- 8. liquidacion (administrativo)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS liquidacion (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    periodo_id UUID NOT NULL REFERENCES periodo_nomina(id) ON DELETE CASCADE,
    empleado_id UUID NOT NULL REFERENCES empleado(id) ON DELETE CASCADE,
    horas_norm NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (horas_norm >= 0),
    horas_extra NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (horas_extra >= 0),
    descuentos NUMERIC(10,2) NOT NULL DEFAULT 0 CHECK (descuentos >= 0),
    total NUMERIC(12,2) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (periodo_id, empleado_id)
);

-- ----------------------------------------------------------------------------
-- 9. regla (configuracion por empresa)
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS regla (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id UUID NOT NULL REFERENCES empresa(id) ON DELETE CASCADE,
    key VARCHAR(60) NOT NULL,
    valor TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
    activa BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (empresa_id, key, version)
);

-- ----------------------------------------------------------------------------
-- Indices
-- ----------------------------------------------------------------------------
CREATE INDEX IF NOT EXISTS idx_empleado_empresa_badge ON empleado(empresa_id, codigo_badge);
CREATE INDEX IF NOT EXISTS idx_asistencia_empresa_fecha ON asistencia(empresa_id, fecha);
CREATE INDEX IF NOT EXISTS idx_asistencia_empleado_fecha ON asistencia(empleado_id, fecha);
CREATE INDEX IF NOT EXISTS idx_incidente_empresa_ts ON incidente(empresa_id, ts);
CREATE INDEX IF NOT EXISTS idx_incidente_asistencia ON incidente(asistencia_id);
CREATE INDEX IF NOT EXISTS idx_liquidacion_periodo_empleado ON liquidacion(periodo_id, empleado_id);
CREATE INDEX IF NOT EXISTS idx_regla_empresa_key_activa ON regla(empresa_id, key, activa);

-- ----------------------------------------------------------------------------
-- Row Level Security (RLS) — multi-tenant
-- ----------------------------------------------------------------------------
ALTER TABLE empresa ENABLE ROW LEVEL SECURITY;
ALTER TABLE puesto ENABLE ROW LEVEL SECURITY;
ALTER TABLE turno ENABLE ROW LEVEL SECURITY;
ALTER TABLE empleado ENABLE ROW LEVEL SECURITY;
ALTER TABLE asistencia ENABLE ROW LEVEL SECURITY;
ALTER TABLE incidente ENABLE ROW LEVEL SECURITY;
ALTER TABLE periodo_nomina ENABLE ROW LEVEL SECURITY;
ALTER TABLE liquidacion ENABLE ROW LEVEL SECURITY;
ALTER TABLE regla ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- Fin del esquema
-- ============================================================================
