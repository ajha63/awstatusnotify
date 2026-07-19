# Historial de incidentes AWS — análisis de eventos recientes

Fuente: [AWS Health Dashboard](https://health.aws.amazon.com/health/status)  
Análisis realizado: 18 de julio de 2026  
Eventos analizados: 3 incidentes activos / recientes (todos los disponibles en el feed público a la fecha)

> **Nota:** El feed público de `status.aws.amazon.com` retiene solo los últimos ~20 items por servicio. Los incidentes históricos más antiguos no están disponibles sin plan de soporte Business/Enterprise.

---

## Resumen ejecutivo

| # | Incidente | Región | Severidad | Inicio | Fin | Duración | Estado |
|---|---|---|---|---|---|---|---|
| EVT-001 | Inaccurate Estimated Billing Data | Global | MEDIUM (impact) | 2026-07-16 19:38 PDT | 2026-07-18 06:00 PDT | **34.4 h** | ✅ Resuelto |
| EVT-002 | Increased Error Rates — Daño físico por conflicto bélico | ME-CENTRAL-1 (UAE) | CRITICAL (disruption) | 2026-03-01 04:51 PST | En curso (>4 meses) | **>3,500 h** | 🔴 En curso |
| EVT-003 | Increased Connectivity Issues — Daño físico por conflicto bélico | ME-SOUTH-1 (Bahrain) | CRITICAL (disruption) | 2026-03-01 21:56 PST | En curso (>4 meses) | **>3,490 h** | 🔴 En curso |

---

## EVT-001 — AWS Billing Console: Inaccurate Estimated Billing Data

### Ficha del incidente

| Campo | Valor |
|---|---|
| **Servicio** | AWS Billing Console (Global) |
| **Slug RSS** | `billingconsole` |
| **Región** | Global |
| **Severidad** | MEDIUM (`Service impact`) |
| **Tipo** | `impact` |
| **Estado** | ✅ RESOLVED |
| **Inicio** | 2026-07-16 19:38 PDT (primer dato incorrecto generado) |
| **Detección por AWS** | 2026-07-16 19:46 PDT (alarmas detectaron anomalías) |
| **Primer update público** | 2026-07-17 01:33 PDT |
| **RCA identificado** | 2026-07-17 12:00 PDT (+10.4 h desde primer update) |
| **Mitigación** | 2026-07-17 12:30 PDT |
| **Inicio de recuperación** | 2026-07-17 16:19 PDT |
| **Resolución** | 2026-07-18 06:00 PDT |
| **Duración total (dato incorrecto → resolución)** | **34.4 horas** |
| **Duración (primer update → resolución)** | **29.4 horas** |
| **N° de updates públicos** | 12 |
| **Intervalo promedio de updates** | ~160 minutos |

### Causa raíz

Cambio de configuración en el sistema de computación de facturas que causó fallos en las actualizaciones de datos de conversión de unidades. Esto produjo costos de línea inflados que se propagaron a la consola y dispararon alertas de presupuesto y detección de anomalías de costos erróneas.

### Servicios afectados

- AWS Billing Console
- AWS Cost Management Console
- Cost and Usage Reports (CUR)
- Cost Explorer
- Budget Alerts
- Cost Anomaly Detection

### Servicios resueltos

- Todos los servicios anteriores (recuperación completa al 2026-07-18 06:00 PDT)

### Timeline de updates

| Timestamp (PDT) | Evento |
|---|---|
| 2026-07-16 19:38 | Inicio de datos incorrectos en facturación |
| 2026-07-16 19:46 | Alarmas internas detectan anomalías (no alertaron al equipo) |
| 2026-07-17 01:33 | Primer update público — investigando datos incorrectos en Cost Explorer |
| 2026-07-17 02:07 | Confirmación del inicio del incidente (19:38 PDT del día anterior) |
| 2026-07-17 03:03 | RCA preliminar: problema de precios unitarios en subsistema de facturación |
| 2026-07-17 03:52 | Pausa de computaciones de facturación estimada |
| 2026-07-17 04:58 | Dos caminos de mitigación en paralelo |
| 2026-07-17 05:54 | Evaluando retomar computaciones (validación adicional) |
| 2026-07-17 07:53 | Rollback no resolvió el problema; continuando investigación |
| 2026-07-17 09:59 | **RCA confirmado** + inicio de backfill de datos |
| 2026-07-17 12:56 | Progreso más lento de lo anticipado en backfill |
| 2026-07-17 18:38 | Progreso sostenido; recuperación esperada 2026-07-19 |
| 2026-07-18 01:05 | Progreso sustancial; mayoría de cuentas en recuperación |
| 2026-07-18 06:57 | **RESOLVED** — todas las cuentas recuperadas |

---

## EVT-002 — Multiple Services (UAE / ME-CENTRAL-1): Increased Error Rates

### Ficha del incidente

| Campo | Valor |
|---|---|
| **Servicio** | Multiple services (UAE) |
| **Slug RSS** | `multipleservices-me-central-1` |
| **Región** | ME-CENTRAL-1 (Middle East — UAE) |
| **AZs afectadas** | mec1-az2 (desde inicio), mec1-az3 (desde ~22:46 PST del 01-Mar) |
| **Severidad** | CRITICAL (`Service disruption`) |
| **Tipo** | `disruption` |
| **Estado** | 🔴 EN CURSO (ongoing, >4 meses) |
| **Inicio** | 2026-03-01 04:51 PST |
| **Causa física** | Drone strikes sobre 2 de 3 data centers; daño estructural, corte de energía, daño por agua de supresión de incendios |
| **Último update** | 2026-04-30 00:25 PDT |
| **Duración a la fecha del análisis** | **>3,500 horas (~146 días)** |
| **N° de updates públicos** | 23 |
| **Evolución de severidad** | impact → degradation → disruption (escaló en las primeras horas) |

### Causa raíz

Conflicto bélico en Medio Oriente. Ataques con drones impactaron directamente 2 de los 3 data centers en UAE (mec1-az2 y mec1-az3), causando daño estructural, corte de suministro eléctrico, y daño por agua de los sistemas de supresión de incendios. La restauración requiere reparación física de instalaciones y coordinación con autoridades locales.

### Servicios disrupted (135 servicios)

Servicios foundational (bloquean recuperación de dependientes):
- **Amazon S3** — alta tasa de errores en PUT/GET/LIST
- **Amazon DynamoDB** — tasas de error elevadas, plano de control degradado
- **Amazon EC2** — lanzamiento de instancias bloqueado; APIs de networking afectadas
- **Amazon RDS** — degradado por dependencias de S3/DynamoDB

Servicios dependientes (se recuperan cuando foundational se restaure):
- AWS Lambda, Amazon Kinesis, Amazon CloudWatch, Amazon EKS, Amazon ECS
- AWS Management Console, AWS CLI
- Amazon ElastiCache, Amazon Redshift, Amazon OpenSearch
- 125+ servicios adicionales (ver lista completa en el dashboard)

### Servicios resueltos dentro del incidente

| Servicio | Fecha de resolución |
|---|---|
| AWS Cloud WAN | ~2026-03-02 (aproximado) |
| AWS Global Accelerator | ~2026-03-02 |
| AWS Management Console | Parcial ~2026-03-02; completo ~2026-03-03 |
| Amazon CloudFront | ~2026-03-02 |
| Amazon Route 53 | ~2026-03-02 |

### Timeline de updates (selección clave)

| Timestamp (PST) | Evento |
|---|---|
| 2026-03-01 04:51 | Primer update — investigando issues en ME-CENTRAL-1 |
| 2026-03-01 05:19 | Confirmación: power issue en AZ mec1-az2 |
| 2026-03-01 06:09 | AZ mec1-az2 confirmada caída; `service impact` → escalando |
| 2026-03-01 07:09 | La mayoría de servicios desviaron tráfico fuera de mec1-az2 |
| 2026-03-01 08:59 | `Service degradation` (elevado de impact) |
| 2026-03-01 09:41 | Información pública: drone strike, fuego, bomberos cortaron energía |
| 2026-03-01 21:59 | Segunda AZ afectada (mec1-az3) — escalada a `Service disruption` |
| 2026-03-02 04:19 | Confirmación oficial: ataques con drones en UAE y Bahrain |
| 2026-03-02 16:19 | Recuperación parcial S3 (PUT/LIST mejora); DynamoDB aún degradado |
| 2026-03-03 08:14 | Transición a modelo de comunicación focalizada vía PHD |
| 2026-04-30 00:25 | Último update: "proceso de restauración tomará varios meses" |

---

## EVT-003 — Multiple Services (Bahrain / ME-SOUTH-1): Increased Connectivity Issues

### Ficha del incidente

| Campo | Valor |
|---|---|
| **Servicio** | Multiple services (Bahrain) |
| **Slug RSS** | `multipleservices-me-south-1` |
| **Región** | ME-SOUTH-1 (Middle East — Bahrain) |
| **AZs afectadas** | mes1-az2 |
| **Severidad** | CRITICAL (`Service disruption`) — escaló desde `impact` |
| **Tipo** | `disruption` |
| **Estado** | 🔴 EN CURSO (ongoing, región declarada no operativa) |
| **Inicio** | 2026-03-01 21:56 PST |
| **Causa física** | Drone strike en proximidad a data center; daño a infraestructura |
| **Último update** | 2026-04-30 00:07 PDT |
| **Duración a la fecha del análisis** | **>3,490 horas (~145 días)** |
| **N° de updates públicos** | 13 |

### Causa raíz

Mismo conflicto bélico que EVT-002. En Bahrain, un drone strike en las cercanías de uno de los data centers causó impactos físicos a la infraestructura. A diferencia de UAE (3 AZs), ME-SOUTH-1 opera con menos redundancia y la región quedó completamente no operativa al 30 de abril 2026.

### Servicios disrupted (144 servicios)

Incluye todos los servicios afectados en EVT-002 más servicios adicionales:
- Amazon Polly, Amazon Transcribe, Amazon Macie, Amazon Detective
- Amazon GameLift Streams, Amazon FreeRTOS, AWS Cloud9
- AWS Ground Station, Amazon Keyspaces, Amazon Kinesis Video Streams

### Servicios resueltos dentro del incidente

| Servicio | Estado |
|---|---|
| AWS Cloud WAN | Resuelto |
| AWS Global Accelerator | Resuelto |
| AWS Management Console | Resuelto |
| Amazon CloudFront | Resuelto |
| Amazon Route 53 | Resuelto |

### Timeline de updates (selección clave)

| Timestamp (PST) | Evento |
|---|---|
| 2026-03-01 21:56 | Primer update — investigando errores en mes1-az2 |
| 2026-03-01 23:09 | Power issue confirmado en mes1-az2 |
| 2026-03-02 01:03 | Tráfico desviado; recovery tomará "muchas horas" |
| 2026-03-02 06:23 | APIs EC2 restauradas en otras AZs; RDS multi-AZ mejorado |
| 2026-03-02 16:22 | Sin cambio en tiempo de recuperación estimado |
| 2026-03-03 08:40 | Transición a comunicación vía PHD |
| 2026-04-30 00:07 | **Región declarada no operativa** — recuperación tomará "varios meses" |

---

## Análisis estadístico de servicios impactados

### Frecuencia de impacto por servicio (eventos EVT-002 + EVT-003 combinados)

Los siguientes servicios aparecen afectados en **ambos** eventos de infraestructura física (los más críticos por ser foundational):

| Servicio | Veces impactado | Clasificación |
|---|---|---|
| **Amazon EC2** | 2/2 eventos | Foundational — compute |
| **Amazon S3** | 2/2 eventos | Foundational — storage |
| **Amazon DynamoDB** | 2/2 eventos | Foundational — NoSQL |
| **Amazon RDS** | 2/2 eventos | Foundational — relational DB |
| **AWS Lambda** | 2/2 eventos | Core serverless |
| **Amazon CloudWatch** | 2/2 eventos | Observabilidad |
| **Amazon Kinesis** | 2/2 eventos | Streaming |
| **Amazon ELB** | 2/2 eventos | Networking |
| **Amazon EKS / ECS** | 2/2 eventos | Containers |
| **AWS Management Console** | 2/2 (resuelto en ambos) | Control plane |
| **Amazon Route 53** | 2/2 (resuelto en ambos) | DNS |
| **Amazon CloudFront** | 2/2 (resuelto en ambos) | CDN |
| **Amazon SNS / SQS** | 2/2 eventos | Messaging |
| **AWS Step Functions** | 2/2 eventos | Orchestration |
| **AWS Secrets Manager / KMS** | 2/2 eventos | Security |
| **Amazon ElastiCache** | 2/2 eventos | Cache |
| **Amazon Redshift** | 2/2 eventos | Data warehouse |
| **Amazon OpenSearch** | 2/2 eventos | Search |

### Patrón de cascada observado

```
Causa raíz (física o config)
    │
    ▼
S3 + DynamoDB degradados   ← foundational; bloquean todo lo demás
    │
    ▼
Lambda + Kinesis + CloudWatch degradados
    │
    ▼
EKS + ECS + Fargate degradados
    │
    ▼
RDS + ElastiCache + Redshift degradados
    │
    ▼
Management Console + CLI degradados
    │
    ▼
125+ servicios dependientes degradados
```

**Implicación para el notificador:** Un incidente en S3 o DynamoDB dentro de una región es señal de alerta temprana de cascada. Monitorear estos servicios específicamente es de alta prioridad.

---

## Estadísticas por región

| Región | Eventos | Severidad máxima | Duración total acumulada | Estado actual |
|---|---|---|---|---|
| **Global** | 1 | MEDIUM | 34.4 h | ✅ Resuelto |
| **ME-CENTRAL-1 (UAE)** | 1 | CRITICAL | >3,500 h | 🔴 En curso |
| **ME-SOUTH-1 (Bahrain)** | 1 | CRITICAL | >3,490 h | 🔴 En curso |

### Distribución de severidad en los feeds analizados

| Severidad | Eventos | % del total |
|---|---|---|
| CRITICAL (`disruption`) | 2 | 67% |
| MEDIUM (`impact`) | 1 | 33% |
| HIGH (`degradation`) | 0 | 0% |

### Distribución de items RSS por incidente

| Incidente | Items RSS | Días cubiertos | Intervalo promedio |
|---|---|---|---|
| EVT-001 Billing | 12 | 1.2 días | ~160 min |
| EVT-002 UAE | 23 | ~60 días | ~3,900 min (~2.7 días) |
| EVT-003 Bahrain | 13 | ~60 días | ~6,500 min (~4.5 días) |

---

## Implicaciones para la configuración del notificador

### Servicios que DEBEN estar en `critical_services`

Basado en el patrón de cascada observado, los servicios foundational que disparan eventos masivos:

```json
"critical_services": [
  "ec2",
  "s3",
  "dynamodb",
  "rds",
  "lambda",
  "cloudwatch",
  "iam",
  "route53"
]
```

> `dynamodb` y `cloudwatch` deberían añadirse a la lista actual (actualmente solo tiene `ec2`, `rds`, `lambda`, `s3`, `iam`, `route53`).

### Slugs de alta prioridad para monitoreo

Los slugs `multipleservices-<region>` son los más críticos — un solo evento en estos feeds puede afectar 130+ servicios simultáneamente:

```
multipleservices-us-east-1
multipleservices-us-east-2
multipleservices-us-west-2
multipleservices-eu-west-1
```

### Tiempo de respuesta observado (EVT-001)

- AWS tardó **7h44m** en publicar el primer update desde el inicio del incidente
- El RCA se identificó **10.4h** después del primer update público
- La mitigación llegó **11.0h** después del primer update
- La recuperación completa tomó **29.4h** desde el primer update

Para un notificador con polling de 5 min, la latencia máxima de detección es 5 min + el tiempo que tardó AWS en publicar el primer update (en este caso 7h44m para EVT-001 — esto no es controlable).

### Incidentes de infraestructura física (EVT-002, EVT-003)

- Duración: **meses** (sin precedente en incidentes de software)
- El feed deja de recibir updates frecuentes después de ~3 días (se pasa a PHD)
- Después del último update público (Apr 30), estos incidentes siguen activos en el feed como `Service disruption`
- El notificador los detectaría correctamente en el primer ciclo y no volvería a notificar gracias a la deduplicación
