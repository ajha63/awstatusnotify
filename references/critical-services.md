# Servicios críticos

Lista de servicios AWS cuyo incidente activa notificación independientemente de la región
(aplica la regla `is_massive_impact`). Editar aquí y reflejar en `config.json`.

## Servicios activos

```
ec2
rds
lambda
s3
dynamodb
cloudwatch
iam
route53
```

## Justificación por servicio

| Servicio | Razón | Evidencia |
|---|---|---|
| `ec2` | Compute foundational. Su degradación bloquea EKS, ECS, Fargate y workloads en general. | EVT-002, EVT-003 |
| `rds` | Base de datos relacional. Dependencia directa de S3 y DynamoDB para recuperación. | EVT-002, EVT-003 |
| `lambda` | Serverless compute. Depende de S3/DynamoDB; cae en cascada con los foundational. | EVT-002, EVT-003 |
| `s3` | Storage foundational. Su degradación es la primera señal de cascada masiva. Monitoreo crítico. | EVT-002, EVT-003 |
| `dynamodb` | NoSQL foundational. Junto con S3, bloquea la recuperación de 100+ servicios dependientes. | EVT-002, EVT-003 (análisis de cascada) |
| `cloudwatch` | Observabilidad. Su caída impide detectar el alcance real de otros incidentes. | EVT-002, EVT-003 |
| `iam` | Identity global. Un incidente en IAM afecta autenticación en todas las regiones. | DEC-008 |
| `route53` | DNS global. Un incidente en Route 53 afecta resolución de nombres en todas las regiones. | DEC-008 |

## Nota sobre `dynamodb` y `cloudwatch`

Agregados basándose en el análisis de incidentes reales (ver `references/incident-history.md`):

- **DynamoDB** aparece como servicio bloqueante en el patrón de cascada de EVT-002 y EVT-003.
  Su recuperación es prerequisito para que Lambda, Kinesis, CloudWatch y RDS se restauren.
- **CloudWatch** es la capa de observabilidad. Cuando cae, el equipo pierde visibilidad
  del alcance real del incidente, agravando el impacto operativo.

## Actualizar la configuración

```bash
# Después de editar este archivo, actualizar config.json:
# "critical_services": ["ec2", "rds", "lambda", "s3", "dynamodb", "cloudwatch", "iam", "route53"]
```
