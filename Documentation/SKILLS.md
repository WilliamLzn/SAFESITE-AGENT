# 🧰 Skills instaladas — Scientific Agent Skills (K-Dense)

| | |
|---|---|
| **Fecha de instalación** | 13 de octubre de 2026 |
| **Repositorio origen** | [K-Dense-AI/scientific-agent-skills](https://github.com/K-Dense-AI/scientific-agent-skills) — commit `a1043ef544e3a100c28e70a736b6cf32554d0677` |
| **Ubicación en el proyecto** | `.opencode/skills/` (descubrimiento automático por OpenCode; compatible con `.claude/skills` y `.agents/skills`) |
| **Licencias** | `exploratory-data-analysis`: MIT · `pytorch-lightning`: Apache-2.0 |
| **Selección** | De las 177 skills del catálogo se instalaron **solo las 2 relevantes** al proyecto (recomendación explícita del propio repositorio por seguridad) |

> ⚠️ **Nota:** no existe una skill llamada "mlops" en ese catálogo. `pytorch-lightning` es la skill con contenido MLOps (entrenamiento reproducible, tracking con MLflow/TensorBoard/W&B, checkpoints, callbacks) y fue la seleccionada con ese fin, junto con `exploratory-data-analysis` para el análisis del dataset.

---

## 1. `exploratory-data-analysis` (v1.4)

**Propósito:** inspección exploratoria acotada y determinista de archivos locales antes del modelado.

**Reglas clave que aplicamos en este proyecto:**
- Datos crudos en **solo lectura**; artefactos derivados en carpetas separadas (`eda/salidas/`, `eda/figuras/`).
- Alcance del escaneo siempre reportado (nada de extrapolar silenciosamente).
- Hallazgos *post-hoc* marcados como **exploratorios**; sin afirmaciones causales.
- Versiones de software y comandos exactos documentados para reproducibilidad.

**Contenido instalado:**

```
.opencode/skills/exploratory-data-analysis/
├── SKILL.md                  # instrucciones de la skill
├── assets/report_template.md # plantilla de informe EDA
├── references/               # 7 guías de formato (CSV/JSON, imágenes, genómica, etc.)
└── scripts/                  # 12 CLIs acotados y sin red (eda_analyzer, tabular_profile,
                              #   missingness_leakage_audit, image_inspector, …)
```

**Uso en este proyecto:** metodología seguida al pie de la letra en el [informe EDA](EDA_SAFESITE_DATASET.md). Sus scripts empaquetados están orientados a CSV/TSV/JSON/imágenes individuales; para el análisis masivo de 1,416 registros NDJSON + 1,129 etiquetas YOLO se escribieron scripts dedicados (`eda/01…05_*.py`) que **respetan su contrato** (solo lectura, alcances, semillas deterministas).

## 2. `pytorch-lightning` (v1.4)

**Propósito:** entrenamiento de redes neuronales reproducible y escalable — organización en `LightningModule`, `Trainer`, callbacks (`ModelCheckpoint`, `EarlyStopping`), y **tracking de experimentos con MLflow / TensorBoard / W&B**.

**Contenido instalado:**

```
.opencode/skills/pytorch-lightning/
├── SKILL.md                       # instrucciones de la skill
├── scripts/                       # 3 plantillas ejecutables (module, datamodule, trainer)
└── references/                    # 7 guías (trainer, callbacks, logging, DDP/FSDP, …)
```

**Uso previsto en este proyecto (Roadmap, Fases 1–2):**
- Semillas fijas (`seed 42`), checkpoints `best.pt` y configuración versionada en cada experimento — prácticas que la skill formaliza y que ya aplicamos en el EDA.
- El baseline usará la API de Ultralytics (nativa del dataset); la skill aporta las **prácticas MLOps** alrededor: reproducibilidad, logging, criterios de parada, documentación de experimentos en la bitácora.
- Si el proyecto evoluciona a un pipeline PyTorch propio (p.ej. módulo de decisión con re-entrenamiento), las plantillas de `LightningModule`/`DataModule` de la skill son el punto de partida.

**Dependencia:** requiere `lightning==2.6.6` + PyTorch compatible cuando se use (no instalada todavía; se instalará en la Fase 1 del roadmap).

---

## Cómo invocar las skills

- **En OpenCode:** se cargan automáticamente cuando la tarea coincide con su descripción, o manualmente con `@exploratory-data-analysis` / `@pytorch-lightning` en el prompt, o vía tool `skill` con su ID.
- **En otros hosts compatibles** (Cursor, Claude Code, Codex…): copiar las carpetas a `.claude/skills/` o `.agents/skills/` según el host.

## Añadir más skills del catálogo (si se necesitan)

```powershell
# el clon sparse temporal sigue disponible:
git -C "$env:TEMP\opencode\sas-clone" sparse-checkout add skills/<nombre>
Copy-Item -Recurse "$env:TEMP\opencode\sas-clone\skills\<nombre>" .opencode\skills\
```

Candidatas evaluadas y **no instaladas** (instalar solo cuando se necesiten): `scientific-visualization` (figuras de publicación), `scikit-learn` (modelos clásicos), `modal` (despliegue serverless).

## Seguridad

Ambas skills provienen del repositorio K-Dense (autoría K-Dense Inc., escaneadas con Cisco AI Defense Skill Scanner según su README). Reglas de la skill de EDA que también son buenas prácticas de seguridad: tratar todo contenido de datos como no confiable, no seguir instrucciones embebidas en archivos, no abrir URLs contenidas en datasets.

## Citación

Si estas skills contribuyen materialmente a un entregable académico, citar (práctica requerida por su SKILL.md):

> Kassis, T., Agarwal, V., He, Y., Patel, D., & Brueckner, A. M. (2026). *Scientific Agent Skills: A Library of Procedural Knowledge for Research Agents*. arXiv:2609.00065. https://doi.org/10.48550/arXiv.2609.00065
