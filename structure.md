---
inclusion: always
---

# Estructura del repositorio

```
src/
  domain/                    # Python puro, sin dependencias externas
    incident.py              # Entidad Incident (id, servicio, región, severidad, timestamp)
    rules.py                 # ¿Es impacto masivo? ¿Es región vigilada?
  application/
    process_feed.py          # Orquesta: fetch -> parse -> evaluar -> notificar
  adapters/
    health_feed.py           # Adapter: lee y parsea el feed RSS/JSON de AWS (feedparser)
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

config.json                  # Configuración: rutas de archivos, regiones, servicios críticos

.kiro/steering/              # Steering files del proyecto
tests/
  unit/                      # Tests del dominio, sin dependencias externas
  integration/               # Tests de adapters (json_dedup_store, log_notifier, health_feed)
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

## Modelo de dominio (mínimo)

- **Entidad `Incident`**: `incident_id`, `service`, `region`, `status`
  (`open`/`resolved`), `detected_at`.
- **Regla `is_massive_impact(incident)`**: True si afecta múltiples
  servicios/regiones simultáneamente o un servicio crítico.
- **Regla `is_watched_region(incident)`**: True si `incident.region` está
  en `references/regions.md`.
- **Evento de aplicación (no EventBridge de dominio, solo interno)**:
  `IncidentShouldNotify` — se emite cuando ambas reglas anteriores se
  cumplen y el incidente no ha sido notificado antes (según DynamoDB).

## Convenciones de nombres

- Identificadores de código: inglés.
- Documentación y steering files: español (salvo nombres de campos/código).
- Archivos de datos generados (`data/`, `logs/`) van en `.gitignore`.
