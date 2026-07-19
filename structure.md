---
inclusion: always
---

# Estructura del repositorio

```
src/
  domain/                    # Python puro, sin dependencias externas
    incident.py              # Entidad Incident (id, slug, región, severidad, tipo, rca, etc.)
    rules.py                 # is_massive_impact, is_watched_region, should_notify
  application/
    process_feed.py          # Orquesta: fetch -> parse -> evaluar -> notificar
                             # Define protocolos FeedFetcher, DedupStore, Notifier
  adapters/
    health_feed.py           # Adapter: descarga y parsea feeds RSS de status.aws.amazon.com
    json_dedup_store.py      # Adapter: deduplicación con archivo JSON local
    log_notifier.py          # Adapter: notifica escribiendo a archivo de log
  handler.py                 # Entry point del script, cablea los adapters

data/
  seen_incidents.json        # Persistencia de incidentes ya notificados (gitignored)

logs/
  notifier.log               # Log de notificaciones emitidas (gitignored)

references/
  regions.md                 # Lista de regiones vigiladas
  critical-services.md       # Lista de servicios considerados críticos
  feed-slugs.md              # Catálogo de slugs RSS relevantes para monitorear

config.json                  # Configuración: feed_slugs, watched_regions, critical_services
config.json.example          # Plantilla de configuración versionada

.kiro/steering/              # Steering files del proyecto
  feed-analysis.md           # Análisis técnico del feed RSS (estructura, métricas, decisiones)
tests/
  unit/                      # Tests del dominio y del parser RSS (sin red)
  integration/               # Tests de adapters (json_dedup_store)
```

> **Fase AWS (futura):** `json_dedup_store.py` → `dynamo_dedup_store.py`,
> `log_notifier.py` → `sns_notifier.py`, `handler.py` se convierte en el
> entry point del Lambda. El directorio `infra/` con CDK se añade en ese momento.

## Separación de capas (obligatoria)

- `domain/` nunca importa librerías externas ni SDKs. Solo lógica pura:
  ¿qué es un incidente relevante?
- `adapters/` contiene todo el código I/O (feed, JSON local, logging).
  Si mañana cambiamos de RSS a la Health API, solo se toca `health_feed.py`.
  Si migramos a AWS, `json_dedup_store.py` → `dynamo_dedup_store.py` y
  `log_notifier.py` → `sns_notifier.py`.
- `handler.py` es el único lugar que conecta domain + adapters; debe ser
  delgado (wiring, no lógica de negocio).

Esta separación existe para poder testear las reglas de negocio
("¿esto es impacto masivo?") sin mockear AWS, y para no bloquear la
decisión de fuente de datos (RSS vs Health API) dentro de la lógica de
negocio.

## Modelo de dominio (actual)

- **Entidad `Incident`**: `incident_id` (sha256 estable), `service`,
  `service_slug`, `region`, `status` (`open`/`resolved`), `severity`
  (`critical`/`high`/`medium`/`low`/`info`/`resolved`), `incident_type`
  (`disruption`/`degradation`/`error_rate`/`impact`/`performance`/
  `informational`/`operational`/`unknown`), `title`, `raw_title`,
  `detected_at`, `affected_regions`, `affected_azs`, `has_rca`.
- **Regla `is_massive_impact(incident)`**: True si severidad es CRITICAL/HIGH,
  o slug es `multipleservices-*`, o hay >1 región afectada, o el servicio
  está en `references/critical-services.md`.
- **Regla `is_watched_region(incident)`**: True si `incident.region` está
  en `references/regions.md`, o si la región es `global`.
- **Regla `should_notify(incident)`**: True si no está RESOLVED Y
  (`is_massive_impact` OR `is_watched_region`).
- **`incident_id` estable**: `sha256(<slug>:<incident_name>)[:16]` — el
  mismo incidente lógico produce el mismo ID aunque AWS publique N updates.

## Convenciones de nombres

- Identificadores de código: inglés.
- Documentación y steering files: español (salvo nombres de campos/código).
- Archivos de datos generados (`data/`, `logs/`) van en `.gitignore`.
