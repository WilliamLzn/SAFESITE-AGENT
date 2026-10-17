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

# --- Modelo (checkpoint de DESPLIEGUE, elegido en P8/BITACORA E23) ---
# tuned_v2_s (yolov8s, data v3): recall incidente no_helmet 0.963 val / 0.833 test
# vs baseline_v1 (yolov8n, data v2): 0.778 / 0.792. Ver eda/salidas/resumen_fase3_demo*.json
RUTA_MODELO = r"runs\safesite\tuned_v2_s\weights\best.pt"
DEVICE_DEFECTO = "cpu"  # el demo corre en CPU para no competir con entrenamientos en GPU

# --- Clases (orden = dataset.yaml) ---
NOMBRES_CLASES = {
    0: "helmet", 1: "gloves", 2: "vest", 3: "boots", 4: "goggles",
    5: "none", 6: "Person", 7: "no_helmet", 8: "no_goggle",
    9: "no_gloves", 10: "no_boots",
}
# Clases que constituyen incumplimiento (el objetivo del agente)
CLASES_INCUMPLIMIENTO = {7, 8, 9, 10}

# --- Anotación visual (E30: corrección del sesgo de etiquetas del dataset) ---
# El dataset fuente (MOCS) etiqueta `goggles` con sesgo sistemático hacia
# abajo: mediana de las cajas al 14.5% de la altura de la persona vs ~8%
# donde están los ojos humanos (verificación sobre 509 cajas del split
# oficial). `no_goggle` es aún más bajo (17.7%). Al DIBUJAR se re-anclan
# esas cajas a nivel de ojos de la persona que las contiene.
NOMBRES_ES = {
    0: "Casco", 1: "Guantes", 2: "Chaleco", 3: "Botas", 4: "Gafas",
    5: "None", 6: "Persona", 7: "SIN CASCO", 8: "SIN GAFAS",
    9: "SIN GUANTES", 10: "SIN BOTAS",
}
CLASES_OJOS = {4, 8}        # se dibujan re-ancladas a nivel de ojos
FRACCION_OJOS = 0.08         # ojos ~8% de la altura de la caja Persona

# --- Umbrales de confianza POR CLASE (EDA F5: exigir menos a las debiles) ---
UMBRAL_DEFECTO = 0.35          # clases positivas (anotacion/estado)
UMBRAL_INCUMPLIMIENTO = 0.15   # clases no_*: umbral bajo, el razonamiento temporal confirma

# --- Perfil VIVO: umbrales por clase calibrados en el piloto real (E33/E35) ---
# Hallazgo del piloto (E28 + capturas del usuario): en sesion en vivo con
# webcam, los falsos positivos de gafas/guantes aparecen con confianza baja
# MIENTRAS se usa el EPP, y ese rango se solapa con las detecciones
# verdaderas del dataset (no_goggle mediana 0.16). Un umbral global alto
# romperia el recall validado, asi que el perfil VIVO calibra CADA clase
# y anade una REGLA DE COHERENCIA por persona (E35); el perfil EVALUACION
# (umbral global 0.15, sin regla) queda intacto para la suite y el demo
# (metricas E31 validadas con el).
#   no_helmet 0.18: conserva las verdaderas mas debiles del piloto (E28 ~18%)
#   no_goggle 0.18: TP del piloto sin gafas ~0.20; FP con gafas ~0.16
#   no_gloves 0.25: TP manos desnudas ~0.27; FP con guante ~0.29 lo suprime
#                   la regla de coherencia (positivo de guante en la persona)
#   no_boots  0.15: sin cambio (verdaderas debiles 0.14; irrelevante en webcam)
UMBRALES_INCUMPLIMIENTO_VIVO = {
    7: 0.18,    # no_helmet
    8: 0.18,    # no_goggle
    9: 0.25,    # no_gloves
    10: 0.15,   # no_boots
}
# E35 — coherencia por persona (SOLO perfil vivo): si el positivo de un EPP
# esta detectado (conf >= UMBRAL_DEFECTO) en la MISMA persona, el `no_*`
# contradictorio se suprime. Casos que resuelve:
#   * casco puesto + no_helmet residual -> no alertar "SIN CASCO" con casco
#   * un guante detectado + no_gloves de la mano no detectada -> sin FP
#   * gafas detectadas + no_goggle residual -> sin FP
# Tradeoff documentado: una persona genuinamente con UNA sola mano
# descubierta no alertaria (se prioriza no molestar en el piloto webcam).
REGLA_COHERENCIA_VIVO = {
    0: 7,    # helmet  -> suprime no_helmet en la misma persona
    4: 8,    # goggles -> suprime no_goggle
    1: 9,    # gloves  -> suprime no_gloves
}

# --- Razonamiento temporal ---
K_FRAMES_CONFIRMACION = 3   # frames consecutivos con deteccion para confirmar incidente
COOLDOWN_S = 30.0           # anti-spam: segundos minimo entre alertas del mismo (zona, clase)

# --- Limites anti-spam GLOBALES del canal WhatsApp (E32) ---
# El cooldown por (zona, clase) acota cada falta individual; estos limites
# acotan el CANAL COMPLETO: evitan el bombardeo cuando varias clases `no_*`
# confirman en momentos distintos o reinciden por flickering de deteccion.
# Aplican solo al actuador WhatsApp (consola/panel/historial no se limitan).
COOLDOWN_GLOBAL_S = 60.0    # tiempo minimo entre CUALQUIER par de mensajes
MAX_MENSAJES_HORA = 20      # techo de mensajes en una hora rodante
# Envios MANUALES (boton del panel, prueba_whatsapp) usan forzar=True y
# bypassan estos limites: son peticiones explicitas del supervisor.

# --- Salidas del agente (artefactos de ejecucion, no versionados) ---
DIR_SALIDAS_AGENTE = r"runs\agente"
DIR_ALERTAS = r"runs\agente\alertas"        # frames anotados de incidentes confirmados
ARCHIVO_HISTORIAL = r"runs\agente\historial_incidentes.jsonl"
