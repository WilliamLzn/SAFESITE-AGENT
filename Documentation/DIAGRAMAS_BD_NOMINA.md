# Diagramas de base de datos y arquitectura — Gestor de Nómina LIVE (SAFESITE-AGENT)

**Proyecto:** SAFESITE-AGENT  
**Metodología:** CRISP-ML(Q) — Fases 3 y 4  
**Versión:** 1.0  
**Fecha:** 02-nov-2026  
**Idioma:** español

---

## 1. Diagrama Entidad-Relación (ER) de la base de datos

```mermaid
erDiagram
    empresa ||--o{ puesto : contiene
    empresa ||--o{ turno : contiene
    empresa ||--o{ empleado : tiene
    empresa ||--o{ asistencia : registra
    empresa ||--o{ incidente : reporta
    empresa ||--o{ periodo_nomina : gestiona
    empresa ||--o{ liquidacion : paga
    empresa ||--o{ regla : configura

    puesto ||--o{ empleado : asigna
    turno ||--o{ empleado : asigna

    empleado ||--o{ asistencia : marca
    empleado ||--o{ incidente : genera
    empleado ||--o{ liquidacion : recibe

    periodo_nomina ||--o{ liquidacion : incluye

    asistencia ||--o{ incidente : vincula

    empresa {
        UUID id PK
        VARCHAR nombre UK
        VARCHAR nit UK
        TIMESTAMPTZ created_at
    }

    puesto {
        UUID id PK
        UUID empresa_id FK
        VARCHAR nombre
        JSONB epp_requerido
        TIMESTAMPTZ created_at
    }

    turno {
        UUID id PK
        UUID empresa_id FK
        VARCHAR nombre
        TIME hora_inicio
        TIME hora_fin
        INTEGER descanso_min
        INTEGER tolerancia_puntualidad_min
        TIMESTAMPTZ created_at
    }

    empleado {
        UUID id PK
        UUID empresa_id FK
        VARCHAR codigo_badge UK
        VARCHAR pseudonimo
        UUID puesto_id FK
        UUID turno_id FK
        NUMERIC salario_base_por_hora
        BOOLEAN activo
        TIMESTAMPTZ created_at
    }

    asistencia {
        UUID id PK
        UUID empresa_id FK
        UUID empleado_id FK
        DATE fecha
        TIMESTAMPTZ entrada_ts
        TIMESTAMPTZ salida_ts
        JSONB frames_evidencia
        NUMERIC confianza_epp
        VARCHAR estado
        TIMESTAMPTZ created_at
        TIMESTAMPTZ updated_at
    }

    incidente {
        UUID id PK
        UUID empresa_id FK
        UUID asistencia_id FK
        UUID empleado_id FK
        VARCHAR tipo
        VARCHAR severidad
        TIMESTAMPTZ ts
        VARCHAR canal
        BOOLEAN resuelto
        TIMESTAMPTZ created_at
    }

    periodo_nomina {
        UUID id PK
        UUID empresa_id FK
        DATE desde
        DATE hasta
        VARCHAR estado
        TIMESTAMPTZ created_at
    }

    liquidacion {
        UUID id PK
        UUID periodo_id FK
        UUID empleado_id FK
        NUMERIC horas_norm
        NUMERIC horas_extra
        NUMERIC descuentos
        NUMERIC total
        TIMESTAMPTZ created_at
    }

    regla {
        UUID id PK
        UUID empresa_id FK
        VARCHAR key
        TEXT valor
        INTEGER version
        BOOLEAN activa
        TIMESTAMPTZ created_at
    }
```

---

## 2. Flujo de los dos agentes (secuencial)

```mermaid
flowchart TD
    A[📷 Trabajador llega a la entrada] --> B{Agente 1: Nómina / Identificación}
    B --> C[Validar código badge / QR o selección manual]
    C --> D{¿Está registrado en nómina?}
    D -->|No| E[❌ Rechazar acceso + alerta WhatsApp "alguien raro"]
    D -->|Sí| F[Registrar entrada_ts + verificar puntualidad]
    F --> G[Agente 2: Verificación de EPP]
    G --> H[📷 Analizar frame con YOLOv8s K=3 frames]
    H --> I{¿Lleva EPP completo?}
    I -->|Sí| J[✅ Registrar asistencia como presente/tardanza]
    I -->|No| K[⚠️ Registrar incidente falta_epp, entrada con observación]
    J --> L[Jornada laboral]
    K --> L
    L --> M[🏁 Salida del trabajador]
    M --> N[Registrar salida_ts + calcular horas trabajadas]
    N --> O{Cierre de intervalo o fin de jornada}
    O --> P[📄 Generar reporte PDF agregado]
    O --> Q[📱 Enviar WhatsApp con resumen y alertas]
    P --> R[Fin]
    Q --> R
    E --> R

    style B fill:#e1f5e1,stroke:#333
    style G fill:#e1f5e1,stroke:#333
    style E fill:#ffebee,stroke:#333
    style K fill:#fff3e0,stroke:#333
```

---

## 3. Diagrama de secuencia — Entrada típica (Agente 1 → Agente 2)

```mermaid
sequenceDiagram
    autonumber
    actor Trabajador
    participant Panel as Panel Web (Flask)
    participant A1 as Agente 1: Nómina
    participant BD as Base de Datos
    participant Cam as Cámara Webcam
    participant A2 as Agente 2: EPP (YOLOv8s)
    participant WA as WhatsApp Cloud API

    Trabajador->>Panel: Presenta badge/QR o selecciona pseudónimo
    Panel->>A1: Validar empleado(codigo_badge)
    A1->>BD: Consultar empleado, puesto, turno
    BD-->>A1: Datos del empleado + turno + EPP requerido
    alt Empleado no existe
        A1->>WA: Alerta "alguien raro" + foto
        A1-->>Panel: Acceso rechazado
        Panel-->>Trabajador: Acceso denegado
    else Empleado existe
        A1->>BD: Registrar entrada_ts + estado (presente/tardanza)
        BD-->>A1: Confirmación registro
        A1->>Cam: Capturar frame de entrada
        Cam-->>A1: Frame
        A1->>A2: Enviar frame + epp_requerido del puesto
        A2->>A2: Detectar EPP con YOLOv8s (K=3 frames)
        alt EPP completo
            A2-->>A1: estado_epp = cumple
        else Falta EPP
            A2-->>A1: estado_epp = incumple + incidente falta_epp
        end
        A1->>BD: Registrar incidente si falta EPP
        BD-->>A1: Confirmación
        A1-->>Panel: Entrada autorizada (con o sin observación EPP)
        Panel-->>Trabajador: Acceso permitido
    end
```

---

## 4. Diagrama de secuencia — Cierre de jornada / reporte agregado

```mermaid
sequenceDiagram
    autonumber
    actor Supervisor
    participant Panel as Panel Web
    participant A1 as Agente 1: Nómina
    participant BD as Base de Datos
    participant PDF as Generador de PDF
    participant WA as WhatsApp Cloud API

    Supervisor->>Panel: Solicitar reporte de intervalo (turno/día)
    Panel->>A1: Generar reporte agregado(intervalo)
    A1->>BD: Consultar asistencia, incidentes, ausentes del intervalo
    BD-->>A1: Datos agregados
    A1->>PDF: Generar reporte PDF
    PDF-->>A1: Archivo PDF generado
    A1->>WA: Enviar resumen por WhatsApp (entradas, ausentes, incidentes críticos)
    WA-->>A1: Confirmación envío (wamid)
    A1-->>Panel: Reporte listo + PDF disponible
    Panel-->>Supervisor: Descarga de PDF y notificación WhatsApp
```

---

## 5. Consideraciones de implementación

| Aspecto | Decisión | Justificación |
|---|---|---|
| Base de datos | PostgreSQL con RLS | Multi-tenant, integridad referencial, JSONB para `epp_requerido` y `frames_evidencia` |
| Identificación | Badge/QR o selección manual | Sin reconocimiento facial, cumple restricción de datos personales del curso |
| EPP | No bloquea entrada | Genera incidente/observación; la entrada ya fue validada por Agente 1 |
| Reportes | PDF + WhatsApp | PDF para archivo/evidencia, WhatsApp para notificación inmediata |
| Semilla | 42 | Reproducibilidad de datos sintéticos para pruebas |

---

## 6. Archivos relacionados

| Archivo | Contenido |
|---|---|
| `Documentation/DICCIONARIO_DATOS_NOMINA.md` | Diccionario de datos detallado (atributos, tipos, restricciones) |
| `src/safesite/modelo_datos.sql` | Esquema SQL ejecutable (PostgreSQL) |
| `Documentation/CRISPML_INTEGRACION_NOMINA.md` | Plan de integración completo bajo CRISP-ML(Q) |
| `src/safesite/agente.py` | Lógica del agente existente (percepción → decisión → acción) |
| `src/safesite/razonamiento.py` | Reglas deterministas existentes (umbrales, cooldown, K=3) |

---

> **Nota:** Los diagramas usan Mermaid y pueden renderizarse en GitHub, VS Code u otros visores compatibles. El esquema SQL en `src/safesite/modelo_datos.sql` es la fuente de verdad para la creación de tablas.
