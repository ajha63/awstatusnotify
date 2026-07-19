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

- ¿Qué se considera "impacto masivo"? → Un incidente cuya severidad es
  CRITICAL o HIGH (prefijo `Service disruption` o `Service degradation` /
  `Increased error rate` en el feed RSS), o que afecta múltiples regiones,
  o cuyo slug es `multipleservices-*`, o que afecta un servicio de la lista
  en `references/critical-services.md`.
- ¿Qué se considera "impacto regional"? → Un incidente cuya región (extraída
  del slug del feed o del body del update) está en `references/regions.md`.
  Los servicios globales (`billingconsole`, `iam`, `route53`) se tratan como
  región `global` y siempre se consideran vigilados.
- ¿Cómo evitamos notificar el mismo incidente varias veces? → El feed publica
  múltiples items por incidente (uno por update). El `incident_id` se calcula
  como `sha256(<slug>:<incident_name>)[:16]`, estable por incidente lógico.
  El adapter `json_dedup_store.py` persiste los IDs ya notificados.
- ¿Qué pasa si la fuente de datos (RSS) no responde? → En fase local, el
  error se loguea y el ciclo termina con excepción visible. En fase AWS,
  debe haber alarma de CloudWatch, nunca fallo silencioso.
- ¿Con qué frecuencia se actualiza el feed de AWS? → El TTL declarado es
  5 minutos. En crisis activa AWS publica updates cada 30-60 min; en
  recuperación lenta, cada 2-6 horas; en incidentes físicos graves, días.
  Polling cada 5-10 min es suficiente y adecuado al TTL.

## Fuente de datos

Sin soporte Business/Enterprise, la fuente es el feed público del AWS
Service Health Dashboard en `https://status.aws.amazon.com/rss/<slug>.rss`.
**No** usar `health.aws.amazon.com/public/currentevents` — ese endpoint
retorna vacío sin Health API. Ver `references/feed-slugs.md` para el
catálogo de slugs relevantes y `.kiro/steering/feed-analysis.md` para
el análisis técnico completo del formato RSS.

Si en el futuro se contrata soporte Business/Enterprise, este documento
debe actualizarse y la fuente puede migrar a la AWS Health API
(`describe_events`) para mayor granularidad y datos personalizados por cuenta.

## Fuera de alcance (por ahora)

- Dashboard web o UI de consulta histórica.
- Integración con sistemas de tickets (ese es otro proyecto, ver skill
  `ticketing-eba-ddd`, no debe mezclarse con este).
- Confirmación/reconocimiento de incidentes por parte de un humano
  (podría añadirse después vía Step Functions si se necesita un flujo de
  aprobación).

## Definición de éxito

- Tiempo entre publicación del incidente en AWS y la notificación: menor a
  N minutos (N = intervalo del scheduler; recomendado 5-10 min dado el TTL
  del feed de 5 min).
- Cero notificaciones duplicadas del mismo incidente (garantizado por
  `incident_id` estable + `json_dedup_store.py`).
- Cero falsos negativos en incidentes con severidad CRITICAL o HIGH.
- Fallo visible (log de error) cuando el feed no responde — nunca silencioso.
