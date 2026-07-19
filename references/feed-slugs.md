# Catálogo de slugs RSS de AWS Service Health Dashboard

Cada feed RSS tiene la forma:
```
https://status.aws.amazon.com/rss/<slug>.rss
```

Los slugs activos en `config.json` son los que el script monitorea.
Este archivo sirve como referencia para agregar o quitar servicios/regiones.

## Formato de slugs

| Patrón | Ejemplo | Descripción |
|---|---|---|
| `<service>-<region>` | `ec2-us-east-1` | Un servicio en una región específica |
| `multipleservices-<region>` | `multipleservices-me-central-1` | Todos los servicios de una región (siempre CRITICAL) |
| `<service>` | `billingconsole`, `iam`, `route53` | Servicios globales (región = `global`) |

## Slugs de servicios críticos por región vigilada

### us-east-1 (N. Virginia)
```
ec2-us-east-1
rds-us-east-1
lambda-us-east-1
s3-us-east-1
iam             (global)
route53         (global)
multipleservices-us-east-1
```

### us-east-2 (Ohio)
```
ec2-us-east-2
rds-us-east-2
lambda-us-east-2
s3-us-east-2
multipleservices-us-east-2
```

### us-west-2 (Oregon)
```
ec2-us-west-2
rds-us-west-2
lambda-us-west-2
s3-us-west-2
multipleservices-us-west-2
```

### eu-west-1 (Irlanda)
```
ec2-eu-west-1
rds-eu-west-1
lambda-eu-west-1
s3-eu-west-1
multipleservices-eu-west-1
```

## Slugs globales (siempre monitorear, región = `global`)
```
billingconsole
iam
route53
s3
```

## Notas

- Los slugs de `multipleservices-<region>` tienen severidad CRITICAL automáticamente
  en las reglas de dominio — representan un evento que afecta múltiples servicios.
- Verificar slugs válidos navegando `https://status.aws.amazon.com/` y buscando
  los links RSS (formato `href="rss/<slug>.rss"`).
- Si un slug no tiene feed activo, `health_feed.py` loguea el error y continúa
  con los demás slugs — no detiene el ciclo completo.
- Actualizar `config.json` (y este archivo) cuando se agregan o quitan regiones
  o servicios vigilados.
