# Tabla de resultados — Fase 3 (suite `src/safesite/pruebas_medidas.py`)

Modelo: `runs\safesite\tuned_v2_s\weights\best.pt` · device: `0` · K=3 · cooldown=30.0s · reps=5 · fecha: 20261014_170459

| Medida de desempeño | Fórmula | Umbral | Casos ejecutados | Resultado obtenido | ¿Cumple? | Evidencia |
|---|---|---|---|---|---|---|
| M1 Recall de incidente (val) | escenas con alerta / escenas incidente | ≥ 0.7 | 28 escenas × 5 reps | 0.964 ± 0.0 | ✅ | `log_ejecucion.jsonl`, `resultados_20261014_170459.csv` |
| M2 Falsas alarmas (val) | escenas control con alerta / escenas control | ≤ 0.1 | 115 escenas × 5 reps | 0.035 ± 0.0 | ✅ | `log_ejecucion.jsonl` |
| M1 Recall de incidente (test) | escenas con alerta / escenas incidente | ≥ 0.7 | 26 escenas × 5 reps | 0.962 ± 0.0 | ✅ | `log_ejecucion.jsonl`, `resultados_20261014_170459.csv` |
| M2 Falsas alarmas (test) | escenas control con alerta / escenas control | ≤ 0.1 | 114 escenas × 5 reps | 0.026 ± 0.0 | ✅ | `log_ejecucion.jsonl` |
| M3 Tiempo de notificación | t(confirmación) − t(inicio racha) + K×latencia + envío WhatsApp | < 10.0 s | 5 escenarios con alerta × 5 reps | 2.99 s (media 1.0 ± 0.0 s sim) | ✅ | `resultados_20261014_170459.csv`; en vivo E28: ~2.6 s |
| M4 Cooldown anti-spam | duplicadas dentro de la ventana / reincidentes | = 0 | S6 + S7 × 5 reps | S6=1 alerta(s), S7=2 alerta(s) | ✅ | `log_ejecucion.jsonl` (S6/S7) |

## Detalle por escenario

| ID | Tipo | Descripción | Alertas (media±σ) | t_alerta s | Excepciones |
|---|---|---|---|---|---|
| S1 | normal | Trabajador con EPP visible (casco+chaleco): sin alertas | 0 ± 0.0 | None | 0 |
| S2 | normal | Trabajador sin casco (solo no_helmet): alerta unica | 1 ± 0.0 | 1.0 | 0 |
| S3 | normal | Trabajador sin guantes (escena con varias faltas): alerta por cada clase no_* confirmada | 3 ± 0.0 | 1.0 | 0 |
| S4 | limite | Incumplimientos multiples en la misma escena: lote | 1 ± 0.0 | 1.0 | 0 |
| S5 | limite | Persona lejana/pequena en escena incidente | 0 ± 0.0 | None | 0 |
| S6 | limite | Reincidencia dentro del cooldown (30 s): 1 sola alerta | 1 ± 0.0 | 1.0 | 0 |
| S7 | limite | Reincidencia despues del cooldown: 2 alertas | 2 ± 0.0 | 1.0 | 0 |
| S8 | normal | Escena sin personas: sin alertas | 0 ± 0.0 | None | 0 |
| S9 | limite | Frame negro (sensor sin senal): sin alertas ni error | 0 ± 0.0 | None | 0 |
| S10 | falla | Sensor sin dato (frame None): registrado, sin crash | 0 ± 0.0 | None | 0 |
| S11 | falla | Entrada invalida (frame 1 canal): sin crash | 0 ± 0.0 | None | 0 |
| S12 | falla | WhatsApp Cloud API caida: degradacion, alerta persistida | 1 ± 0.0 | None | 0 |
| S13 | falla | Checkpoint inexistente: fallo de arranque controlado | None ± None | None | 0 |