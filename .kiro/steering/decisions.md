---
inclusion: always
---

# Decisiones de diseño

Registro de decisiones arquitectónicas y de implementación tomadas durante
el desarrollo. Cada entrada explica el contexto, la opción elegida y el
razonamiento — para no repetir la misma discusión en el futuro.

---

## DEC-001 — Identificador de incidente: por incidente lógico, no por update

**Contexto:** El feed RSS de AWS publica múltiples `<item>` para un mismo
incidente — uno por cada update. Cada item tiene un `<guid>` distinto con
formato `#<slug>_<unix-epoch>`.

**Decisión:** El `incident_id` se calcula como `sha256(<slug>:<incident_name>)[:16]`,
donde `incident_name` es el título del incidente sin el prefijo de tipo (`"Service
disruption: "`) ni el tag `[RESOLVED]`. Este ID es estable: el mismo incidente
lógico produce el mismo ID aunque AWS publique 20 updates.

**Consecuencia:** La deduplicación funciona correctamente. Un incidente que
dura 30 horas con 12 updates solo genera una notificación.

**Alternativa descartada:** Usar el `guid` completo como ID. Generaría una
notificación por cada update de AWS — ruido inaceptable.

---

## DEC-002 — URL correcta del feed RSS

**Contexto:** La documentación inicial apuntaba a
`https://health.aws.amazon.com/public/currentevents`. Al probarlo contra
producción, retorna 0 entradas (requiere plan Business/Enterprise).

**Decisión:** Usar `https://status.aws.amazon.com/rss/<slug>.rss`. Este es
el feed público real, visible en `https://status.aws.amazon.com/`. Cada
servicio/región tiene su propio slug; la lista se mantiene en
`references/feed-slugs.md`.

**Consecuencia:** Hay que configurar explícitamente los slugs a monitorear
en `config.json`. No existe un feed único que agregue todos los servicios.

---

## DEC-003 — Severidad por prefijo del título, no por campos del XML

**Contexto:** El feed RSS no tiene un campo explícito de severidad. La única
señal estructurada es el prefijo del `<title>`.

**Decisión:** Mapear prefijos de título a severidades del dominio:
- `Service disruption:` → `CRITICAL`
- `Service degradation:` / `Increased error rate:` → `HIGH`
- `Service impact:` → `MEDIUM`
- `Performance issue:` → `LOW`
- `Informational message:` → `INFO`
- `Service is operating normally:` → `RESOLVED`

**Consecuencia:** `CRITICAL` y `HIGH` siempre activan notificación
independientemente de región. `MEDIUM` y `LOW` solo notifican si la región
está vigilada o el servicio es crítico.

---

## DEC-004 — Fallback a curl para descarga del feed (SSL en macOS/Python 3.14+)

**Contexto:** En Python 3.14 sobre macOS, `urllib` y `feedparser` fallan con
`[SSL: CERTIFICATE_VERIFY_FAILED]` si no está instalado el bundle de
certificados del sistema para Python (`Install Certificates.command`).

**Decisión:** `health_feed.py` usa `subprocess.run(["curl", "-sL", ...])` para
descargar el XML raw y luego parsea con `xml.etree.ElementTree` (stdlib). Esto
elimina la dependencia de SSL del runtime de Python.

**Consecuencia:** `curl` debe estar disponible en el sistema (preinstalado en
macOS). En la migración a Lambda (Amazon Linux), `curl` también está disponible.
`feedparser` se mantiene en `pyproject.toml` como dependencia declarada pero
ya no se usa directamente para la descarga.

---

## DEC-005 — Deduplicación en JSON local (no DynamoDB)

**Contexto:** El proyecto está en fase local. DynamoDB no está disponible.

**Decisión:** `json_dedup_store.py` persiste los `incident_id` notificados en
`data/seen_incidents.json`. La interfaz expone `is_seen(id)` y `mark_seen(id)`.

**Consecuencia:** La migración futura a DynamoDB es solo reemplazar el adapter —
el dominio y el caso de uso no se tocan. La clave de diseño es que el dominio
solo conoce el protocolo `DedupStore`, no la implementación.

**TTL pendiente:** Al migrar a DynamoDB, definir un TTL (recomendado: 30-90 días)
para evitar crecimiento indefinido de la tabla.

---

## DEC-006 — Notificaciones como logging local (no SNS)

**Contexto:** El proyecto está en fase local. SNS no está disponible.

**Decisión:** `log_notifier.py` escribe las notificaciones como entradas
`WARNING` en `logs/notifier.log` con todos los campos relevantes del incidente.

**Consecuencia:** La migración futura a SNS es solo reemplazar el adapter.
El log local sirve también como registro de auditoría durante el desarrollo.

---

## DEC-007 — Protocolos Python en lugar de clases base abstractas

**Contexto:** `process_feed.py` necesita depender de `FeedFetcher`, `DedupStore`
y `Notifier` sin acoplarse a implementaciones concretas.

**Decisión:** Usar `typing.Protocol` (duck typing estructural) en lugar de
`ABC`. Las implementaciones concretas no necesitan heredar de nada — basta
con que implementen los métodos requeridos.

**Consecuencia:** Testing más limpio (cualquier objeto con el método correcto
sirve como mock), y se puede añadir una nueva implementación de adapter sin
modificar la jerarquía de clases.

---

## DEC-008 — Servicios globales siempre vigilados

**Contexto:** Servicios como `billingconsole`, `iam`, `route53` o `s3` no
tienen región — su slug no incluye sufijo de región y se les asigna `region = "global"`.

**Decisión:** `is_watched_region()` retorna `True` cuando `incident.region == "global"`,
independientemente de la lista de regiones configuradas.

**Razonamiento:** Un incidente en IAM o Route 53 afecta todas las regiones
simultáneamente; ignorarlo porque "global no está en mi lista" sería un
falso negativo inaceptable.

---

## DEC-009 — No notificar incidentes RESOLVED

**Contexto:** Cuando AWS resuelve un incidente, publica un update final con
el título `"Service is operating normally: [RESOLVED] <nombre>"`. Este update
llega al feed y podría generar una segunda notificación.

**Decisión:** `should_notify()` retorna `False` si `incident.status == RESOLVED`.
La notificación se emite una sola vez al detectar el incidente abierto.

**Consecuencia aceptada:** No se notifica explícitamente el cierre del incidente.
Si se necesita notificación de resolución en el futuro, se puede añadir como
comportamiento opt-in en `process_feed.py` sin tocar el dominio.
