# DESIGN.md — awstatusnotify

Documento de diseño técnico del sistema. Define la arquitectura, los contratos de cada componente, las decisiones de diseño y los criterios de aceptación que guían la implementación.

> Este documento es la fuente de verdad técnica. Cualquier cambio de diseño se refleja aquí antes de implementarse. Las decisiones de alto nivel viven en `.kiro/steering/decisions.md`.

---

## Tabla de contenidos

1. [Visión general del sistema](#1-visión-general-del-sistema)
2. [Arquitectura hexagonal](#2-arquitectura-hexagonal)
3. [Modelo de dominio](#3-modelo-de-dominio)
4. [Reglas de negocio](#4-reglas-de-negocio)
5. [Caso de uso principal](#5-caso-de-uso-principal)
6. [Adapters — contratos e implementaciones](#6-adapters--contratos-e-implementaciones)
7. [Configuración del sistema](#7-configuración-del-sistema)
8. [Flujo de datos end-to-end](#8-flujo-de-datos-end-to-end)
9. [Manejo de errores y resiliencia](#9-manejo-de-errores-y-resiliencia)
10. [Estrategia de testing](#10-estrategia-de-testing)
11. [Roadmap de migración a AWS](#11-roadmap-de-migración-a-aws)
12. [Limitaciones conocidas de la fase local](#12-limitaciones-conocidas-de-la-fase-local)

---

## 1. Visión general del sistema

### Problema que resuelve

Los equipos sin plan de soporte Business/Enterprise de AWS no tienen acceso a la AWS Health API personalizada. La única fuente pública es el AWS Service Health Dashboard. Sin automatización, el equipo se entera de los incidentes cuando los usuarios finales reportan síntomas.

### Solución

Un script Python que corre periódicamente (cada 5-10 minutos), consume los feeds RSS públicos de `status.aws.amazon.com`, evalúa cada incidente contra reglas de relevancia configurables y emite una notificación exactamente una vez por incidente nuevo.

### Principios de diseño

| Principio | Aplicación concreta |
|---|---|
| **Dominio aislado** | `domain/` no importa ninguna librería externa. Testeable sin infraestructura. |
| **Inversión de dependencias** | El caso de uso depende de protocolos (`typing.Protocol`), no de implementaciones. |
| **Sustitución de adapters** | Migrar de JSON local a DynamoDB o de log a SNS es cambiar un archivo, no refactorizar. |
| **Fallo visible** | Errores de red o parseo se loguean explícitamente; nunca fallo silencioso. |
| **Exactamente una notificación** | El `incident_id` estable + dedup store garantizan 0 duplicados. |

---

## 2. Arquitectura hexagonal

```
┌──────────────────────────────────────────────────────────────┐
│                        DOMINIO                               │
│                                                              │
│  ┌─────────────────┐        ┌──────────────────────────┐    │
│  │  incident.py    │        │       rules.py            │    │
│  │  ─────────────  │        │  ──────────────────────   │    │
│  │  Incident       │◄───────│  is_massive_impact()      │    │
│  │  IncidentStatus │        │  is_watched_region()      │    │
│  │  IncidentSev.   │        │  should_notify()          │    │
│  │  IncidentType   │        └──────────────────────────┘    │
│  └─────────────────┘                                         │
└──────────────────────────┬───────────────────────────────────┘
                           │  (solo conoce el dominio)
┌──────────────────────────▼───────────────────────────────────┐
│                      APLICACIÓN                              │
│                                                              │
│  ┌────────────────────────────────────────────────────────┐  │
│  │                  process_feed.py                       │  │
│  │  ──────────────────────────────────────────────────    │  │
│  │  Protocol FeedFetcher   → fetch_incidents()            │  │
│  │  Protocol DedupStore    → is_seen() / mark_seen()      │  │
│  │  Protocol Notifier      → notify()                     │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────┬───────────────────┬─────────────────┬─────────────┘
           │                   │                 │
           ▼                   ▼                 ▼
┌──────────────────┐ ┌──────────────────┐ ┌──────────────────┐
│  ADAPTER INPUT   │ │  ADAPTER DEDUP   │ │  ADAPTER OUTPUT  │
│                  │ │                  │ │                  │
│  health_feed.py  │ │ json_dedup_      │ │  log_notifier.py │
│  ─────────────── │ │ store.py         │ │  ──────────────  │
│  fetch_incidents │ │ ──────────────── │ │  notify()        │
│  (curl + XML)    │ │ is_seen()        │ │                  │
│                  │ │ mark_seen()      │ │  [fase AWS]      │
│  [fase AWS]      │ │                  │ │  sns_notifier.py │
│  health_feed.py  │ │  [fase AWS]      │ │                  │
│  (Health API)    │ │  dynamo_dedup_   │ └──────────────────┘
└──────────────────┘ │  store.py        │
                     └──────────────────┘
                              │
                    ┌─────────▼──────────┐
                    │  ENTRY POINT       │
                    │  handler.py        │
                    │  (wiring only)     │
                    └────────────────────┘
```

### Regla de dependencia (estricta)

```
domain ← application ← adapters ← handler
```

- `domain/` no importa nada externo.
- `application/` importa `domain/` y define protocolos.
- `adapters/` importa `domain/` e implementa los protocolos de `application/`.
- `handler.py` importa todo y es el único punto de cableado.
- Ninguna capa importa a la capa que está a su derecha en la cadena.

---

## 3. Modelo de dominio

### `Incident` — entidad raíz

```python
@dataclass(frozen=True)
class Incident:
    # Identificación
    incident_id: str        # sha256(f"{slug}:{incident_name}")[:16]
                            # Estable por incidente lógico (DEC-001)
    service: str            # Nombre legible: "EC2", "Multiple services"
    service_slug: str       # Slug del feed: "ec2-us-east-1"

    # Clasificación
    region: str             # Región AWS (ej. "us-east-1") o "global"
    status: IncidentStatus  # OPEN | RESOLVED
    severity: IncidentSeverity
    incident_type: IncidentType

    # Contenido
    title: str              # Nombre del incidente sin prefijo de tipo
    raw_title: str          # Título completo del feed RSS
    detected_at: datetime   # Timestamp UTC del update más reciente

    # Alcance (extraído del body del update)
    affected_services: list[str]  # Servicios mencionados en el description
    affected_regions: list[str]   # Regiones mencionadas en el description
    affected_azs: list[str]       # AZs mencionadas (ej. "mec1-az2")
    has_rca: bool                 # True si el update menciona causa raíz
```

**Invariantes:**
- `incident_id` no puede ser vacío.
- `service` no puede ser vacío.
- La entidad es inmutable (`frozen=True`). No hay setters.

### `IncidentSeverity`

| Valor | Origen en el feed |
|---|---|
| `CRITICAL` | Prefijo `"Service disruption:"` |
| `HIGH` | Prefijo `"Service degradation:"` o `"Increased error rate:"` |
| `MEDIUM` | Prefijo `"Service impact:"` |
| `LOW` | Prefijo `"Performance issue:"` |
| `INFO` | Prefijo `"Informational message:"` |
| `RESOLVED` | Prefijo `"Service is operating normally:"` o tag `[RESOLVED]` |

### `IncidentType`

| Valor | Prefijo del título RSS |
|---|---|
| `DISRUPTION` | `"Service disruption:"` |
| `DEGRADATION` | `"Service degradation:"` |
| `ERROR_RATE` | `"Increased error rate:"` |
| `IMPACT` | `"Service impact:"` |
| `PERFORMANCE` | `"Performance issue:"` |
| `INFORMATIONAL` | `"Informational message:"` |
| `OPERATIONAL` | `"Service is operating normally:"` |
| `UNKNOWN` | Prefijo no reconocido |

### Propiedades calculadas

```python
@property
def is_multi_region(self) -> bool:
    return len(self.affected_regions) > 1

@property
def is_multi_service(self) -> bool:
    return self.service_slug.startswith("multipleservices")
```

---

## 4. Reglas de negocio

### `should_notify(incident, critical_services, watched_regions) → bool`

Composición de reglas. Retorna `True` si el incidente debe generar notificación.

```
should_notify = NOT is_resolved(incident)
                AND (is_massive_impact(incident, critical_services)
                     OR is_watched_region(incident, watched_regions))
```

**Condición de salida temprana:** Si el incidente está `RESOLVED`, retorna `False` inmediatamente. No se notifica el cierre (DEC-009).

### `is_massive_impact(incident, critical_services) → bool`

```
is_massive_impact = incident.severity in {CRITICAL, HIGH}
                    OR incident.is_multi_region
                    OR incident.is_multi_service
                    OR incident.service in critical_services
```

| Condición | Fundamento |
|---|---|
| Severidad CRITICAL/HIGH | AWS lo clasifica explícitamente como disrupción severa (DEC-003) |
| Multi-región | Impacta a más de un territorio geográfico simultáneamente |
| `multipleservices-*` | Slug de AWS para eventos que afectan toda una región |
| Servicio en lista crítica | Definido por el operador en `config.json` |

### `is_watched_region(incident, watched_regions) → bool`

```
is_watched_region = incident.region == "global"
                    OR incident.region in watched_regions
```

**Regla especial para `global`:** IAM, Route 53, Billing Console y servicios globales similares no tienen región explícita. Un incidente en IAM afecta todas las regiones; ignorarlo sería un falso negativo inaceptable (DEC-008).

---

## 5. Caso de uso principal

### `process_feed` — flujo de ejecución

```
process_feed(fetcher, dedup, notifier, critical_services, watched_regions) → int

1. incidents = fetcher.fetch_incidents()
   └─ Descarga y parsea todos los feeds configurados.
      Agrupa por incidente lógico, retorna el update más reciente por incidente.

2. Para cada incident en incidents:
   a. Si dedup.is_seen(incident.incident_id):
      └─ Omitir (log DEBUG). El incidente ya fue notificado en un ciclo anterior.

   b. Si should_notify(incident, critical_services, watched_regions):
      i.  notifier.notify(incident)     ← emitir notificación
      ii. dedup.mark_seen(incident_id)  ← registrar para deduplicación futura
      iii. notified += 1

   c. Si NOT should_notify:
      └─ Omitir (log DEBUG). Incidente no relevante.

3. Retornar notified (count de notificaciones emitidas en este ciclo).
```

### Protocolos (interfaces)

```python
class FeedFetcher(Protocol):
    def fetch_incidents(self) -> list[Incident]: ...

class DedupStore(Protocol):
    def is_seen(self, incident_id: str) -> bool: ...
    def mark_seen(self, incident_id: str) -> None: ...

class Notifier(Protocol):
    def notify(self, incident: Incident) -> None: ...
```

Los protocolos son **estructurales** (`typing.Protocol`): cualquier objeto que implemente los métodos requeridos satisface la interfaz, sin necesidad de herencia (DEC-007).

---

## 6. Adapters — contratos e implementaciones

### 6.1 `health_feed.py` — FeedFetcher

**Responsabilidad:** Descargar feeds RSS y convertirlos en entidades `Incident`.

**Contrato público:**
```python
def fetch_incidents(slugs: list[str]) -> list[Incident]
def fetch_incidents_from_slug(slug: str) -> list[Incident]
def feed_url_for_slug(slug: str) -> str
```

**Algoritmo de parseo por slug:**
```
1. Construir URL: https://status.aws.amazon.com/rss/<slug>.rss
2. Descargar XML via curl subprocess (DEC-004):
   subprocess.run(["curl", "-sL", "--max-time", "15", url])
3. Parsear XML con xml.etree.ElementTree (stdlib)
4. Para cada <item>:
   a. Clasificar título → (IncidentType, IncidentSeverity, is_resolved)
   b. Extraer incident_name del título (quitar prefijo + [RESOLVED])
   c. Calcular incident_id = sha256(f"{slug}:{incident_name}")[:16]
   d. Extraer región del slug (regex) o del description
   e. Extraer AZs del description (regex)
   f. Detectar RCA en el description (keywords)
   g. Parsear pubDate → datetime UTC
   h. Construir Incident
5. Agrupar por incident_id, retener solo el item más reciente por grupo
   (el más reciente refleja el estado actual del incidente)
6. Retornar lista de incidentes únicos
```

**Manejo de errores:** Si un slug individual falla (timeout, XML inválido), se loguea el error y se continúa con los demás slugs. El error no detiene el ciclo completo.

**Extracción de región:**
- Del slug: regex `[a-z]{2}-(?:east|west|central|...)-\d` aplicado al slug.
- Del description: mismo regex aplicado al cuerpo del update.
- Si el slug no contiene región (servicios globales como `billingconsole`, `iam`): `region = "global"`.
- Si hay regiones en el description además de la del slug, se combinan en `affected_regions`.

**Clasificación de título:**
```python
_TITLE_PREFIX_MAP = [
    ("Service disruption",          DISRUPTION,    CRITICAL),
    ("Service degradation",         DEGRADATION,   HIGH),
    ("Increased error rate",        ERROR_RATE,    HIGH),
    ("Service impact",              IMPACT,        MEDIUM),
    ("Performance issue",           PERFORMANCE,   LOW),
    ("Informational message",       INFORMATIONAL, INFO),
    ("Service is operating normally", OPERATIONAL, RESOLVED),
]
```

### 6.2 `json_dedup_store.py` — DedupStore

**Responsabilidad:** Persistir los `incident_id` ya notificados entre ejecuciones del script.

**Contrato público:**
```python
class JsonDedupStore:
    def __init__(self, store_path: Path = Path("data/seen_incidents.json"))
    def is_seen(self, incident_id: str) -> bool
    def mark_seen(self, incident_id: str) -> None
```

**Formato del archivo JSON:**
```json
{
  "seen_ids": [
    "a3f8c1d2e4b56789",
    "b7e2f4a1c3d58920"
  ]
}
```

Los IDs están ordenados lexicográficamente en el JSON para facilitar inspección manual y diffs en git si fuera necesario versionar el archivo.

**Comportamiento ante fallos:**
- Archivo ausente → inicia con set vacío (no es error).
- JSON corrupto → inicia con set vacío + log WARNING.
- Error de escritura → propaga excepción (fallar visible).

**Operación:** `mark_seen` escribe inmediatamente al disco. No hay buffer ni escritura diferida, porque ante un crash entre la notificación y la escritura, el incidente se notificaría de nuevo en el siguiente ciclo (aceptable: mejor duplicado que silencio).

### 6.3 `log_notifier.py` — Notifier

**Responsabilidad:** Emitir la notificación al canal de salida (fase local: archivo de log).

**Contrato público:**
```python
class LogNotifier:
    def notify(self, incident: Incident) -> None
```

**Formato de log (nivel WARNING):**
```
NOTIFICACIÓN | id=<id> | type=<type> | severity=<sev> | status=<status>
             | service=<service> | region=<region> | rca=<bool>
             | title=<title> | detected_at=<iso8601>
```

El nivel `WARNING` garantiza que las notificaciones sean visibles en configuraciones de log con nivel `INFO` o superior.

---

## 7. Configuración del sistema

### `config.json`

```json
{
  "watched_regions": ["us-east-1", "us-east-2", "us-west-2", "eu-west-1"],
  "critical_services": ["ec2", "rds", "lambda", "s3", "iam", "route53"],
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

| Campo | Tipo | Descripción |
|---|---|---|
| `watched_regions` | `list[str]` | Regiones AWS. Incidentes en estas regiones activan notificación. |
| `critical_services` | `list[str]` | Servicios cuyo incidente siempre notifica, sin importar la región. |
| `feed_slugs` | `list[str]` | Lista de feeds RSS a monitorear. Cada slug = un feed en `status.aws.amazon.com/rss/<slug>.rss`. |

### Logging

Configurado en `handler.py` con dos handlers:
- `StreamHandler` (consola): nivel INFO.
- `FileHandler` (`logs/notifier.log`): nivel INFO, encoding UTF-8.

Formato: `%(asctime)s %(levelname)-8s %(name)s — %(message)s`

---

## 8. Flujo de datos end-to-end

```
config.json
    │
    ▼
handler.main()
    │
    ├─ _load_config()         → {watched_regions, critical_services, feed_slugs}
    ├─ _FeedFetcherAdapter(slugs)
    ├─ JsonDedupStore()        → carga data/seen_incidents.json
    └─ LogNotifier()
    │
    ▼
process_feed(fetcher, dedup, notifier, critical_services, watched_regions)
    │
    ├─ fetcher.fetch_incidents()
    │       │
    │       ├─ Para cada slug en feed_slugs:
    │       │       │
    │       │       ├─ curl https://status.aws.amazon.com/rss/<slug>.rss
    │       │       ├─ Parsear XML → list[dict]
    │       │       ├─ Convertir cada item → Incident
    │       │       └─ Deduplicar por incident_id → retener más reciente
    │       │
    │       └─ Retornar list[Incident] (todos los slugs combinados)
    │
    ├─ Para cada Incident:
    │       │
    │       ├─ dedup.is_seen(incident_id)?
    │       │       └─ Sí → skip (log DEBUG)
    │       │
    │       └─ should_notify(incident, critical_services, watched_regions)?
    │               ├─ No  → skip (log DEBUG)
    │               └─ Sí  → notifier.notify(incident)
    │                         dedup.mark_seen(incident_id)
    │                         → escribe logs/notifier.log
    │                         → actualiza data/seen_incidents.json
    │
    └─ Retornar count de notificaciones emitidas
```

---

## 9. Manejo de errores y resiliencia

| Escenario | Comportamiento | Nivel de log |
|---|---|---|
| Feed individual no responde (timeout curl) | Loguea error, continúa con los demás slugs | ERROR |
| XML del feed malformado | Loguea error, continúa con los demás slugs | ERROR |
| Item RSS sin título o con título no reconocido | Retorna `None`, item ignorado | WARNING |
| `pubDate` no parseable | Usa `datetime.now(UTC)` como fallback | — (silencioso) |
| `config.json` no encontrado | Lanza `FileNotFoundError` con mensaje claro | — (excepción) |
| `seen_incidents.json` corrupto | Inicia con set vacío + log WARNING | WARNING |
| Error de escritura en `seen_incidents.json` | Propaga excepción (fallo visible) | — (excepción) |
| Todos los feeds fallan | El ciclo termina con `notified = 0`, log ERROR por cada slug | ERROR |

**Principio:** fallar de forma visible. Nunca suprimir errores silenciosamente. El operador debe saber si el monitoreo está roto.

---

## 10. Estrategia de testing

### Pirámide de tests

```
        ┌──────────┐
        │   E2E    │  (no implementado — ejecución manual)
        ├──────────┤
        │  Integr. │  tests/integration/  → adapters con filesystem real
        ├──────────┤
        │  Unidad  │  tests/unit/         → dominio + funciones puras del parser
        └──────────┘
```

### Tests unitarios (`tests/unit/`)

**Principio:** sin red, sin filesystem, sin subprocess.

| Archivo | Qué cubre | Tests |
|---|---|---|
| `test_rules.py` | `is_massive_impact`, `is_watched_region`, `should_notify` | 14 |
| `test_health_feed_parser.py` | Funciones puras de `health_feed.py`: `_classify_title`, `_incident_name_from_title`, `_region_from_slug`, `_extract_regions`, `_extract_azs`, `_has_rca`, `_incident_id`, `feed_url_for_slug` | 28 |

**Helper `make_incident(**kwargs)`:** construye un `Incident` con defaults razonables, permitiendo sobreescribir solo el campo relevante para cada test. Evita repetición y hace los tests legibles.

### Tests de integración (`tests/integration/`)

**Principio:** usan el filesystem real via `tmp_path` de pytest. Sin red.

| Archivo | Qué cubre | Tests |
|---|---|---|
| `test_json_dedup_store.py` | Ciclo completo del dedup store: nuevo ID, persistencia entre instancias, múltiples IDs, archivo corrupto | 4 |

### Qué no se testea en automatizado

- Descarga real del feed RSS (requiere red — verificación manual o test de smoke).
- Formato final del log (verificación manual).
- Comportamiento del cron (verificación manual).

### Cobertura objetivo

- `domain/` y funciones puras de `adapters/`: 100%.
- `application/process_feed.py`: cubierto indirectamente por los tests de dominio y dedup.
- `handler.py`: verificación manual (wiring, no lógica de negocio).

---

## 11. Roadmap de migración a AWS

La migración no requiere tocar el dominio ni el caso de uso. Solo se reemplazan adapters y se añade `infra/`.

### Fase 1 — Notificaciones reales (SMTP / SNS)

Reemplazar `log_notifier.py` por `smtp_notifier.py` (fase intermedia) o `sns_notifier.py` (fase AWS).

```python
# sns_notifier.py — mismo contrato, distinta implementación
class SnsNotifier:
    def __init__(self, topic_arn: str, boto_client: Any) -> None: ...
    def notify(self, incident: Incident) -> None:
        # Publicar en SNS con subject + body estructurado
        ...
```

### Fase 2 — Deduplicación en DynamoDB

Reemplazar `json_dedup_store.py` por `dynamo_dedup_store.py`.

```python
# dynamo_dedup_store.py — mismo contrato, distinta implementación
class DynamoDedupStore:
    def __init__(self, table_name: str, boto_client: Any, ttl_days: int = 30) -> None: ...
    def is_seen(self, incident_id: str) -> bool: ...
    def mark_seen(self, incident_id: str) -> None:
        # PutItem con TTL = now + ttl_days
        ...
```

### Fase 3 — Lambda + EventBridge

`handler.py` se convierte en Lambda handler:

```python
def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    # Mismo cuerpo que main(), con clientes boto3 inyectados
    ...
```

EventBridge Scheduler dispara el Lambda cada 5-10 minutos.

### Fase 4 — Infraestructura como código (CDK)

```
infra/
  app.py
  stacks/
    notifier_stack.py   # Lambda + DynamoDB + SNS + EventBridge + Alarms
```

### Fase 5 — AWS Health API (opcional)

Si se contrata soporte Business/Enterprise, reemplazar `health_feed.py` por un adapter que use `describe_events` de la AWS Health API. El dominio y el caso de uso no cambian.

---

## 12. Limitaciones conocidas de la fase local

| Limitación | Impacto | Mitigación futura |
|---|---|---|
| El feed RSS no tiene región explícita en algunos servicios | Se infiere del slug o del description; puede ser impreciso para servicios globales complejos | Migrar a AWS Health API con soporte Business+ |
| La severidad se infiere del prefijo del título | Si AWS cambia el formato del título, el mapeo puede romperse silenciosamente | Monitorear el clasificador con logs DEBUG y añadir alerta si `UNKNOWN` aparece frecuentemente |
| `seen_incidents.json` crece indefinidamente | A largo plazo el archivo puede hacerse grande | Añadir limpieza de IDs con TTL (ej. eliminar entradas con `detected_at > 90 días`) |
| Sin notificación de resolución de incidentes | El operador no recibe aviso cuando el incidente se cierra | Añadir opción `notify_on_resolve: bool` en `config.json` como comportamiento opt-in |
| curl como dependencia de sistema | En entornos sin curl (raro) el adapter falla | Añadir fallback a `urllib` con manejo explícito de certificados (`ssl.create_default_context`) |
| No hay retry en descarga de feeds | Un timeout transitorio marca el feed como fallido para ese ciclo | Añadir retry con backoff exponencial (máximo 2-3 intentos) |
