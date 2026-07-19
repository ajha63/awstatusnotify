# awstatusnotify

Notificador de incidentes del [AWS Service Health Dashboard](https://health.aws.amazon.com/health/status), construido con arquitectura hexagonal en Python 3.12+.

Monitorea los feeds RSS públicos de `status.aws.amazon.com`, clasifica los incidentes por severidad y región, evita notificaciones duplicadas y emite alertas antes de que los usuarios finales reporten síntomas — sin necesidad de plan de soporte Business/Enterprise.

> **Estado actual:** fase local. Corre como script Python invocado manualmente o vía `cron`. La arquitectura está preparada para migrar a Lambda + DynamoDB + SNS cambiando únicamente los adapters.

---

## Contenido

- [Cómo funciona](#cómo-funciona)
- [Requisitos](#requisitos)
- [Instalación](#instalación)
- [Configuración](#configuración)
- [Uso](#uso)
- [Arquitectura](#arquitectura)
- [Lógica de notificación](#lógica-de-notificación)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Desarrollo](#desarrollo)
- [Roadmap hacia AWS](#roadmap-hacia-aws)

---

## Cómo funciona

```
cron / ejecución manual
        │
        ▼
  src/handler.py          ← cablea los adapters y lanza el ciclo
        │
        ▼
  application/process_feed.py
        │
        ├─ FeedFetcher ──► health_feed.py
        │                   └─ descarga feeds RSS de status.aws.amazon.com
        │                      (uno por servicio/región configurado)
        │                      └─ clasifica severidad por prefijo del título
        │                         y extrae región, AZs, RCA del body
        │
        ├─ DedupStore ──► json_dedup_store.py
        │                   └─ data/seen_incidents.json
        │                      (evita notificar el mismo incidente dos veces)
        │
        └─ Notifier ────► log_notifier.py
                            └─ logs/notifier.log
                               (registro de todas las notificaciones emitidas)
```

Cada ciclo:
1. Descarga los feeds RSS de los slugs configurados en `config.json`.
2. Agrupa los items por incidente lógico (un incidente puede tener N updates).
3. Para cada incidente nuevo (no visto antes), evalúa las reglas de dominio.
4. Si corresponde notificar, escribe en el log y marca el incidente como visto.

---

## Requisitos

- Python 3.12 o superior
- `curl` disponible en el sistema (preinstalado en macOS y Amazon Linux)
- Acceso a Internet para consultar `status.aws.amazon.com`

---

## Instalación

```bash
# Clonar el repositorio
git clone https://github.com/ajha63/awstatusnotify.git
cd awstatusnotify

# Crear entorno virtual e instalar dependencias
python3 -m venv .venv
source .venv/bin/activate        # bash/zsh
# o: source .venv/bin/activate.fish  # fish

pip install -e ".[dev]"
```

---

## Configuración

Copiar la plantilla y ajustar los valores:

```bash
cp config.json.example config.json
```

```json
{
  "watched_regions": [
    "us-east-1",
    "us-east-2",
    "us-west-2",
    "eu-west-1"
  ],
  "critical_services": [
    "ec2", "rds", "lambda", "s3", "iam", "route53"
  ],
  "feed_slugs": [
    "ec2-us-east-1",
    "ec2-us-east-2",
    "rds-us-east-1",
    "lambda-us-east-1",
    "s3",
    "iam",
    "route53"
  ]
}
```

| Campo | Descripción |
|---|---|
| `watched_regions` | Regiones AWS a vigilar. Un incidente en estas regiones activa notificación (ver `references/regions.md`). |
| `critical_services` | Servicios cuyo incidente siempre notifica, independientemente de región (ver `references/critical-services.md`). |
| `feed_slugs` | Lista de feeds RSS a monitorear. Cada slug corresponde a `https://status.aws.amazon.com/rss/<slug>.rss`. Ver `references/feed-slugs.md` para el catálogo completo. |

> `config.json` está en `.gitignore` — nunca se versiona.

### Slugs de feeds

Los slugs siguen el patrón:

| Patrón | Ejemplo | Descripción |
|---|---|---|
| `<servicio>-<región>` | `ec2-us-east-1` | Un servicio en una región |
| `multipleservices-<región>` | `multipleservices-us-east-1` | Todos los servicios de una región (severidad CRITICAL automática) |
| `<servicio>` | `s3`, `iam`, `route53` | Servicios globales |

Descubrir todos los slugs disponibles en: `https://status.aws.amazon.com/`

---

## Uso

### Ejecución manual

```bash
python -m src.handler
```

Salida de ejemplo:

```
2026-07-18T12:00:00 INFO     src.handler — Iniciando chequeo | feeds=11 | regiones vigiladas=['us-east-1', ...] | servicios críticos=['ec2', ...]
2026-07-18T12:00:02 INFO     src.adapters.health_feed — Feed ec2-us-east-1: 3 incidentes únicos identificados
2026-07-18T12:00:05 WARNING  src.adapters.log_notifier — NOTIFICACIÓN | id=a3f8c1d2e4b56789 | type=disruption | severity=critical | status=open | service=Ec2 | region=us-east-1 | rca=False | title=Instance connectivity issues | detected_at=2026-07-18T11:45:00+00:00
2026-07-18T12:00:05 INFO     src.handler — Fin del ciclo | notificaciones enviadas=1
```

Las notificaciones también se escriben en `logs/notifier.log`.

### Ejecución periódica con cron

```bash
# Revisar cada 5 minutos (alineado al TTL del feed de AWS)
*/5 * * * * cd /ruta/al/proyecto && .venv/bin/python -m src.handler >> logs/cron.log 2>&1
```

### Ejecución periódica con fish (launchd en macOS)

```fish
# Verificar que el script funciona
python -m src.handler
```

---

## Arquitectura

El proyecto sigue **arquitectura hexagonal** (ports & adapters):

```
┌─────────────────────────────────────────────────────┐
│                      DOMINIO                        │
│   incident.py  ·  rules.py                         │
│   (Python puro, sin dependencias externas)          │
└───────────────────────┬─────────────────────────────┘
                        │ protocolos (typing.Protocol)
┌───────────────────────▼─────────────────────────────┐
│                   APLICACIÓN                        │
│   process_feed.py                                   │
│   FeedFetcher · DedupStore · Notifier               │
└──────┬──────────────┬──────────────────┬────────────┘
       │              │                  │
       ▼              ▼                  ▼
health_feed.py  json_dedup_store.py  log_notifier.py
(RSS feed)      (JSON local)         (logging)
       │              │                  │
 [fase AWS]     [DynamoDB]            [SNS]
```

**Regla de dependencia:** el dominio no importa nada externo. Los adapters conocen el dominio pero no entre sí. El caso de uso solo habla con protocolos. `handler.py` es el único punto de cableado concreto.

Esta separación permite:
- Testear las reglas de negocio sin mocks de AWS ni red.
- Migrar de JSON a DynamoDB o de log a SNS reemplazando un archivo.
- Cambiar la fuente de datos de RSS a la AWS Health API sin tocar el dominio.

### Entidad `Incident`

```python
@dataclass(frozen=True)
class Incident:
    incident_id: str          # sha256(slug:incident_name)[:16] — estable por incidente lógico
    service: str              # nombre legible: "EC2", "Multiple services"
    service_slug: str         # slug del feed: "ec2-us-east-1"
    region: str               # región AWS o "global"
    status: IncidentStatus    # OPEN | RESOLVED
    severity: IncidentSeverity  # CRITICAL | HIGH | MEDIUM | LOW | INFO | RESOLVED
    incident_type: IncidentType # DISRUPTION | DEGRADATION | ERROR_RATE | IMPACT | ...
    title: str                # nombre del incidente sin prefijo de tipo
    raw_title: str            # título completo del feed
    detected_at: datetime
    affected_regions: list[str]
    affected_azs: list[str]
    has_rca: bool             # True si el update menciona causa raíz
```

---

## Lógica de notificación

Un incidente genera notificación si **todas** estas condiciones se cumplen:

1. Su `status` es `OPEN` (no se notifican cierres).
2. Al menos una de:
   - Su `severity` es `CRITICAL` o `HIGH` (disruption, degradation, increased error rate).
   - Su slug es `multipleservices-*` (afecta múltiples servicios en una región).
   - Afecta más de una región (`affected_regions > 1`).
   - Su `service` está en `critical_services` de `config.json`.
   - Su `region` está en `watched_regions` de `config.json`.
   - Su `region` es `global` (IAM, Route 53, Billing — siempre se notifican).

### Severidades y su origen

| Prefijo en el título RSS | Tipo | Severidad |
|---|---|---|
| `Service disruption:` | `disruption` | **CRITICAL** |
| `Service degradation:` | `degradation` | **HIGH** |
| `Increased error rate:` | `error_rate` | **HIGH** |
| `Service impact:` | `impact` | MEDIUM |
| `Performance issue:` | `performance` | LOW |
| `Informational message:` | `informational` | INFO |
| `Service is operating normally:` | `operational` | RESOLVED |

### Deduplicación

El `incident_id` es `sha256("<slug>:<nombre_incidente>")[:16]`. Es **estable**: el mismo incidente lógico produce el mismo ID aunque AWS publique 20 updates con distintos guids. Esto garantiza exactamente una notificación por incidente.

---

## Estructura del proyecto

```
awstatusnotify/
├── src/
│   ├── domain/
│   │   ├── incident.py          # Entidad Incident + enums de status, severidad y tipo
│   │   └── rules.py             # is_massive_impact, is_watched_region, should_notify
│   ├── application/
│   │   └── process_feed.py      # Caso de uso: orquesta fetch → dedup → evaluar → notificar
│   ├── adapters/
│   │   ├── health_feed.py       # Descarga y parsea feeds RSS de status.aws.amazon.com
│   │   ├── json_dedup_store.py  # Deduplicación en data/seen_incidents.json
│   │   └── log_notifier.py      # Notificaciones en logs/notifier.log
│   └── handler.py               # Entry point: cablea adapters y ejecuta el ciclo
│
├── tests/
│   ├── unit/
│   │   ├── test_rules.py              # 14 tests: reglas de dominio (sin red)
│   │   └── test_health_feed_parser.py # 28 tests: parseo RSS (sin red, sin curl)
│   └── integration/
│       └── test_json_dedup_store.py   # 4 tests: ciclo completo del dedup store
│
├── references/
│   ├── regions.md           # Regiones AWS vigiladas
│   ├── critical-services.md # Servicios críticos
│   └── feed-slugs.md        # Catálogo de slugs RSS por región y servicio
│
├── .kiro/steering/
│   ├── decisions.md         # 9 decisiones de diseño (ADRs)
│   └── feed-analysis.md     # Análisis técnico del formato RSS de AWS
│
├── config.json.example      # Plantilla de configuración
├── config.json              # Configuración local (gitignored)
├── pyproject.toml           # Dependencias y configuración de ruff/mypy/pytest
│
├── product.md               # Spec de producto working-backwards (EBA)
├── tech.md                  # Stack tecnológico y decisiones de infraestructura
├── structure.md             # Arquitectura y modelo de dominio
├── git-workflow.md          # Convenciones de branching, commits y PRs
└── linting.md               # Configuración de ruff, mypy y shellcheck
```

---

## Desarrollo

### Verificación completa (checklist pre-push)

```bash
# Lint y formato
.venv/bin/ruff check .
.venv/bin/ruff format .

# Tipado estático (strict en domain/ y application/)
.venv/bin/mypy src/

# Tests
.venv/bin/pytest
```

O todo junto:

```bash
.venv/bin/ruff check . && .venv/bin/ruff format --check . && .venv/bin/mypy src/ && .venv/bin/pytest
```

### Agregar un nuevo feed a monitorear

1. Encontrar el slug en `https://status.aws.amazon.com/` (buscar links `rss/<slug>.rss`).
2. Añadir el slug a `feed_slugs` en `config.json`.
3. Actualizar `references/feed-slugs.md` para mantener el catálogo sincronizado.
4. Si la región no estaba vigilada, añadirla también a `watched_regions` y a `references/regions.md`.

### Añadir un nuevo servicio crítico

1. Añadir el nombre del servicio a `critical_services` en `config.json`.
2. Actualizar `references/critical-services.md`.

### Convenciones de commits

```
<tipo>(<alcance>): <descripción en imperativo>

feat(domain): agregar campo affected_azs a Incident
fix(adapters): corregir extracción de región en slugs ap-southeast
docs(references): agregar slugs de ap-northeast-1
infra(notifier-stack): agregar alarma CloudWatch para fallos del Lambda
```

Tipos: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `infra`.

---

## Roadmap hacia AWS

Cuando el proyecto migre a AWS, solo cambian los adapters:

| Componente local | Reemplazar por | Archivo |
|---|---|---|
| `cron` del SO | EventBridge Scheduler | `infra/stacks/notifier_stack.py` |
| `src/handler.py` script | Lambda handler | mismo archivo, distinto entry point |
| `json_dedup_store.py` | `dynamo_dedup_store.py` | DynamoDB con TTL de 30-90 días |
| `log_notifier.py` | `sns_notifier.py` | SNS con suscripciones email + SMS |
| `logs/notifier.log` | CloudWatch Logs + Alarm | automático en Lambda |

El dominio (`incident.py`, `rules.py`) y el caso de uso (`process_feed.py`) **no se modifican**.

Si se contrata soporte Business/Enterprise, la fuente de datos puede migrar de RSS a la [AWS Health API](https://docs.aws.amazon.com/health/latest/APIReference/) (`describe_events`) para mayor granularidad. Solo se toca `health_feed.py`.

---

## Fuente de datos

Los feeds RSS están en `https://status.aws.amazon.com/rss/<slug>.rss`. El TTL declarado es de **5 minutos** — el polling cada 5-10 min es adecuado y no genera carga innecesaria.

> La URL `health.aws.amazon.com/public/currentevents` **no funciona** sin plan Business/Enterprise. No usarla.

---

## Licencia

Repositorio privado — © 2026 ajha63.
