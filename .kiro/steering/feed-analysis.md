---
inclusion: always
---

# Análisis del feed RSS de AWS Service Health Dashboard

## Fuente real de los feeds

La URL correcta **no** es `health.aws.amazon.com/public/currentevents` (retorna vacío).
Los feeds RSS reales están en:

```
https://status.aws.amazon.com/rss/<service-slug>.rss
```

### Feeds observados en producción (ejemplos)

| Slug | URL |
|---|---|
| `billingconsole` | `https://status.aws.amazon.com/rss/billingconsole.rss` |
| `multipleservices-me-central-1` | `https://status.aws.amazon.com/rss/multipleservices-me-central-1.rss` |
| `multipleservices-me-south-1` | `https://status.aws.amazon.com/rss/multipleservices-me-south-1.rss` |
| `ec2-us-east-1` | `https://status.aws.amazon.com/rss/ec2-us-east-1.rss` |

El patrón general es: `<service>-<region>.rss` o `<service>.rss` para servicios globales.

**Feed de índice con todos los feeds disponibles:**
`https://status.aws.amazon.com/` (HTML con links a todos los `.rss`)

## Estructura de un item RSS

```xml
<item>
  <title><![CDATA[Service disruption: Increased Error Rates]]></title>
  <link>https://status.aws.amazon.com/</link>
  <pubDate>Thu, 30 Apr 2026 00:25:54 PDT</pubDate>
  <guid isPermaLink="false">https://status.aws.amazon.com/#multipleservices-me-central-1_1777533954</guid>
  <description><![CDATA[Texto del update...]]></description>
</item>
```

### Campos disponibles y cómo usarlos

| Campo RSS | Contenido | Uso en el dominio |
|---|---|---|
| `title` | `"<Prefijo de estado>: <Nombre del incidente>"` | Tipo + severidad + nombre |
| `pubDate` | RFC 2822 con timezone (PDT/PST) | `detected_at`, cálculo de intervalos |
| `guid` | `#<service-slug>_<unix-epoch>` | Clave de deduplicación **por update** |
| `description` | Texto completo del update (CDATA) | Señales: RCA, mitigación, regiones, AZs, próximo update |
| `link` | Siempre `https://status.aws.amazon.com/` | No útil para identificación |

## Identificación del GUID y deduplicación

```
guid = "https://status.aws.amazon.com/#billingconsole_1784383061"
                                        └─ slug ──────┘ └── ts ──┘
```

- **Cada update de un mismo incidente genera un `guid` distinto** (el epoch cambia).
- El **incidente lógico** se identifica combinando: `slug` + `nombre del incidente`
  (título sin el prefijo de estado).
- Para deduplicar **el incidente** (no el update), usar `slug + incident_name`.
- Para deduplicar **el update individual**, usar el `guid` completo.

**Decisión de diseño:** notificamos una vez por incidente lógico, no por update.
La clave en `seen_incidents.json` es: `sha256(<slug>:<incident_name>)[:16]`.

## Tipo de incidente (prefijo del título)

| Prefijo en `title` | Tipo interno | Severidad sugerida |
|---|---|---|
| `Service disruption:` | `disruption` | `CRITICAL` |
| `Service degradation:` | `degradation` | `HIGH` |
| `Increased error rate:` / `Increased Error Rates` | `error_rate` | `HIGH` |
| `Service impact:` | `impact` | `MEDIUM` |
| `Performance issue:` | `performance` | `LOW` |
| `Informational message:` | `informational` | `INFO` |
| `Service is operating normally:` | `operational` | `RESOLVED` |

Si el título contiene `[RESOLVED]` o empieza con `Service is operating normally`, el incidente está cerrado.

## Extracción de región y AZ

- **Región**: buscar con regex `[a-z]{2}-(?:east|west|central|north|south|northeast|southeast)-\d`
  o variantes (`ap-`, `sa-`, `me-`, `af-`, `il-`, `ca-`) en el `description`.
- **AZ**: buscar `[a-z]{2,4}\d-az\d` (ej. `mec1-az2`).
- Para feeds con slug `multipleservices-<region>`, la región está directamente en el slug.
- Los feeds de un solo servicio global (ej. `billingconsole`) **no incluyen región** en el título;
  la región es implícita (`global`).

## Señales en el `description`

| Señal | Regex de detección | Significado |
|---|---|---|
| RCA identificado | `identified the root cause\|root cause\|retrospective` | Publicación del análisis de causa raíz |
| Mitigado | `mitigat\|resolved\|corrected\|restored\|recovery complete` | Problema contenido o resuelto |
| Fin del incidente | Título con `[RESOLVED]` o `operating normally` | Incidente cerrado |
| Próximo update prometido | `provide.*update.*by\s+(.{10,60}?)` | Hora comprometida del siguiente update |
| Servicios afectados | `Amazon [\w ]+\|AWS [\w ]+` en description | Alcance del impacto |

## Métricas observadas en producción (muestra real, jul 2026)

| Incidente | Tipo | Duración | Updates | Intervalo promedio |
|---|---|---|---|---|
| Billing Console – Inaccurate Data | `impact` / MEDIUM | 29.4 h | 12 | ~160 min |
| UAE – Increased Error Rates | `error_rate` / HIGH | >1.400 h (ongoing) | 23 | variable |

- **TTL del feed**: 5 minutos → el feed puede cambiar cada 5 min. Polling cada 5-10 min es apropiado.
- **Intervalo de updates de AWS**: altamente variable. En crisis activa: cada 30-60 min.
  En recuperación lenta: cada 2-6 horas. En incidentes de infraestructura física: días.
- **RCA típico**: aparece entre 0.5 h y 12 h después del primer update (si se publica).
  En incidentes de infraestructura física severa puede no publicarse en el feed público.

## Alcance (scope) de un incidente

| Indicador en el feed | Alcance inferido |
|---|---|
| Slug `multipleservices-<region>` | Regional, múltiples servicios → `is_massive_impact = True` |
| Descripción menciona >1 región | Multi-regional → `is_massive_impact = True` |
| Descripción menciona >1 AZ | Multi-AZ dentro de una región |
| Slug `<service>-<region>` | Un servicio, una región específica |
| Slug `<service>` sin región | Servicio global (billing, iam, route53, etc.) |

## Implicaciones para health_feed.py

1. **URL base correcta**: `https://status.aws.amazon.com/rss/<slug>.rss`
2. **Índice de feeds**: parsear `https://status.aws.amazon.com/` para descubrir todos los slugs activos.
3. **incident_id**: usar `sha256(<slug>:<incident_name>)[:16]` para identificar el incidente lógico.
4. **Región**: extraer del slug (`multipleservices-<region>`) o del description con regex.
5. **Severidad**: inferir del prefijo del título.
6. **SSL en Python 3.14+/macOS**: `urllib` requiere certificados del sistema. Usar `certifi` o `curl` como workaround, o `feedparser` con `ssl=False` en entornos sin CA bundle.
