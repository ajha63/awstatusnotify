---
inclusion: always
---

# Producto: AWS Health Incident Notifier

## Working backwards (EBA)

**Outcome de negocio:** el equipo se entera de un incidente de AWS con
impacto masivo o específico de una región **antes** de que los usuarios
finales reporten síntomas, sin necesidad de tener plan de soporte
Business/Enterprise.

**Press release (resumen de una línea):** "La app revisa el AWS Service
Health Dashboard cada pocos minutos y notifica por correo y SMS solo
cuando detecta un incidente relevante para las regiones que nos importan,
evitando ruido de eventos ya conocidos."

**Preguntas frecuentes que el diseño debe responder:**

- ¿Qué se considera "impacto masivo"? → Un incidente que afecta múltiples
  servicios o regiones al mismo tiempo, o que afecta un servicio crítico
  para nosotros (definir lista de servicios críticos en `references/`).
- ¿Qué se considera "impacto regional"? → Un incidente reportado en una
  región de nuestra lista de regiones vigiladas (`references/regions.md`).
- ¿Cómo evitamos notificar el mismo incidente varias veces? → Ver
  `structure.md` (deduplicación por `incident_id`).
- ¿Qué pasa si la fuente de datos (RSS/Health API) no responde? → Debe
  fallar de forma visible (alarma en CloudWatch), nunca en silencio.

## Fuente de datos

Sin soporte Business/Enterprise, la fuente es el feed público del AWS
Service Health Dashboard (RSS/JSON), no la AWS Health API
(`describe_events`), que requiere ese nivel de soporte. Si en el futuro se
contrata soporte Business/Enterprise, este documento debe actualizarse y
la fuente puede migrar a la Health API para mayor granularidad.

## Fuera de alcance (por ahora)

- Dashboard web o UI de consulta histórica.
- Integración con sistemas de tickets (ese es otro proyecto, ver skill
  `ticketing-eba-ddd`, no debe mezclarse con este).
- Confirmación/reconocimiento de incidentes por parte de un humano
  (podría añadirse después vía Step Functions si se necesita un flujo de
  aprobación).

## Definición de éxito

- Tiempo entre publicación del incidente en AWS y la notificación: menor a
  N minutos (definir N según el intervalo del scheduler).
- Cero notificaciones duplicadas del mismo incidente.
- Cero falsos negativos en incidentes marcados como "masivos" por AWS.
