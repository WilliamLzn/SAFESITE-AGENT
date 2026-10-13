# 📱 WhatsApp Business Cloud API — Límites, cuotas y costos

> Consulta realizada el 13-oct-2026 para el canal de alertas de SafeSite-Agent.
> **TL;DR: en el modo actual (número de prueba) todo es $0 y sin cuotas mensuales
> relevantes. El único candado real es el máximo de 5 destinatarios.**

---

## 1. Modo actual: número de PRUEBA (el que usa el proyecto)

| Concepto | Regla |
|---|---|
| Costo por mensaje | **$0** — mensajes libres (texto + imagen) a destinatarios permitidos |
| Cuota mensual | Sin cuota dura utilizable en un piloto (modo desarrollo; aplica "uso razonable") |
| **Límite principal** | **Máximo 5 destinatarios permitidos** (verificados en el panel con código) |
| Uso permitido | **Solo desarrollo** — Meta prohíbe usarlo como producción real |
| Plantillas | No requiere plantillas aprobadas (mensajes libres habilitados) |

## 2. Límites técnicos del endpoint (aplican en cualquier modo)

| Límite | Valor | Impacto en SafeSite |
|---|---|---|
| Tasa de envío | **80 mensajes/segundo** por número | Ninguno (enviamos ~1 por incidente) |
| Peso de imagen | **5 MB** máximo | Ninguno (frames anotados ≈ 100–200 KB) |
| Caption de imagen | **1.024 caracteres** | Mensaje natural cabe de sobra |
| Texto simple | 4.096 caracteres | Detalle técnico INFO cabe de sobra |
| Carga de medios | vía `POST /{phone_id}/media` → `media_id` (2 pasos) | Ya implementado en `actuarios.py` |

## 3. Modo producción (número de negocio real) — si algún día se migra

**Modelo (desde 2025): cobro por mensaje de plantilla**, ya no por conversación.

**Se cobra** (mensajes iniciados por el negocio — p.ej. las alertas):
- Requieren plantilla aprobada (`alerta_epp`, categoría *Utilidad*)
- Tarifa por unidad, según categoría y país — las *utility* son las más baratas
  (fracciones de centavo; consultar la tarjeta oficial vigente:
  [developers.facebook.com/docs/whatsapp/pricing](https://developers.facebook.com/docs/whatsapp/pricing))

**Es gratis**:
- Mensajes libres **dentro de la ventana de 24 h** que abre el supervisor al
  responder (el INFO del supervisor la abre)
- Plantillas *utility* entregadas dentro de esa misma ventana abierta

**Requisitos administrativos de la migración**:
1. Número dedicado (no puede ser el WhatsApp personal simultáneamente)
2. Verificación del negocio en Meta Business
3. Plantilla `alerta_epp` aprobada + nombre visible aprobado
4. Límites diarios escalonados según calidad del número (250 → 1.000 → 10.000
   clientes únicos/día) — irrelevantes a escala de piloto

## 4. Traducción al proyecto

| Escenario | Costo estimado | Nota |
|---|---|---|
| **Entrega académica / piloto (modo actual)** | **$0** | 5 números permitidos; cooldown 30 s ya limita el volumen |
| Piloto real en obra (número de negocio) | centavos–2 USD/mes | El trabajo es administrativo (verificación + plantilla), no de código: `ActuadorWhatsApp.construir_payload()` ya genera el payload de plantilla que esa modalidad exige |

**Recomendación vigente:** permanecer en el número de prueba durante toda la
fase académica. La migración a producción es trámite, no desarrollo.

---

*Fuente: documentación oficial de Meta (WhatsApp Business Platform) consultada
el 13-oct-2026. Tarifas exactas por país/paquete: verificar siempre la tarjeta
oficial en el enlace de la sección 3, pues Meta las actualiza periódicamente.*
