"""SafeSite-Agent — configuración central del núcleo del agente.

Valores por defecto derivados de la evidencia:
- EDA F5: las clases de incumplimiento (`no_*`) son débiles -> umbral de
  confianza MENOR para ellas + confirmación temporal de K frames (la
  responsabilidad de la decisión se desplaza al razonamiento temporal).
- EDA F6: no usar anidamiento casco/persona -> las decisiones se basan
  SOLO en las clases `no_*` explicitas.
- Reencuadre de E21: la métrica del negocio es el recall A NIVEL DE
  INCIDENTE en video continuo, no el recall por fotograma.
"""

# --- Modelo (checkpoint actual; cambiar al mejor modelo futuro) ---
RUTA_MODELO = r"runs\safesite\baseline_v1\weights\best.pt"
DEVICE_DEFECTO = "cpu"  # el demo corre en CPU para no competir con entrenamientos en GPU

# --- Clases (orden = dataset.yaml) ---
NOMBRES_CLASES = {
    0: "helmet", 1: "gloves", 2: "vest", 3: "boots", 4: "goggles",
    5: "none", 6: "Person", 7: "no_helmet", 8: "no_goggle",
    9: "no_gloves", 10: "no_boots",
}
# Clases que constituyen incumplimiento (el objetivo del agente)
CLASES_INCUMPLIMIENTO = {7, 8, 9, 10}

# --- Umbrales de confianza POR CLASE (EDA F5: exigir menos a las debiles) ---
UMBRAL_DEFECTO = 0.35          # clases positivas (anotacion/estado)
UMBRAL_INCUMPLIMIENTO = 0.15   # clases no_*: umbral bajo, el razonamiento temporal confirma

# --- Razonamiento temporal ---
K_FRAMES_CONFIRMACION = 3   # frames consecutivos con deteccion para confirmar incidente
COOLDOWN_S = 30.0           # anti-spam: segundos minimo entre alertas del mismo (zona, clase)

# --- Salidas del agente (artefactos de ejecucion, no versionados) ---
DIR_SALIDAS_AGENTE = r"runs\agente"
DIR_ALERTAS = r"runs\agente\alertas"        # frames anotados de incidentes confirmados
ARCHIVO_HISTORIAL = r"runs\agente\historial_incidentes.jsonl"
