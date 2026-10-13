"""SafeSite-Agent — núcleo del agente de monitoreo de EPP.

Modulos:
- config: umbrales por clase, K de confirmacion, cooldown, rutas
- percepcion: fuentes de frames + inferencia YOLO + anotacion
- razonamiento: reglas temporales (K frames consecutivos) sobre clases no_*
- memoria: cooldown anti-spam + historial persistente de incidentes
- actuarios: consola/panel + announcer de WhatsApp Business
- agente: orquestador del ciclo percibir -> razonar -> actuar
"""

__version__ = "0.1.0"
