---
inclusion: always
---

# Stack Tecnológico

## Lenguaje de aplicación: Python 3.12+

Elegido sobre Node.js porque:

- La carga de trabajo es *polling periódico + parsing + notificación*, no
  I/O concurrente masivo — el modelo async de Node.js no aporta ventaja
  real aquí.
- `boto3` tiene mejor cobertura que el SDK de JS para Health API, SNS,
  DynamoDB y Secrets Manager.
- Permite compartir lenguaje con la infraestructura (CDK en Python),
  reduciendo el context-switch y permitiendo testing compartido.
- Librerías de parsing (`feedparser`, `beautifulsoup4`) son directas para
  leer el feed RSS/JSON del Service Health Dashboard.

No usar Node.js en este proyecto salvo justificación explícita y aprobada.

## Infraestructura: AWS CDK (Python), nunca CloudFormation crudo

- Un único stack de aplicación es suficiente dado el tamaño del proyecto
  (no se requiere separación por bounded context como en el proyecto de
  ticketing).
- Constructs de alto nivel (`aws-cdk-lib`) sobre L1 (`Cfn*`) siempre que
  existan.

## Modo de ejecución actual: local (sin AWS)

El proyecto corre localmente como un script Python invocado manualmente
o vía `cron` del sistema operativo. No se despliega en Lambda ni usa
servicios AWS por ahora. La arquitectura hexagonal se mantiene para que
la migración futura a AWS sea un cambio de adapters, no de dominio.

| Componente | Implementación local |
|---|---|
| Scheduler | `cron` del SO o ejecución manual (`python -m src.handler`) |
| Fetch + parseo del feed | Script Python con `feedparser` |
| Deduplicación | Archivo JSON local (`data/seen_incidents.json`) |
| Notificaciones | Logging a archivo (`logs/notifier.log`) |
| Observabilidad | `logging` estándar de Python |

## Recursos AWS del stack (referencia futura)

Cuando el proyecto migre a AWS, los adapters locales se reemplazan por:

| Recurso | Rol |
|---|---|
| EventBridge Scheduler / Rule (cron) | Dispara el chequeo periódico |
| Lambda (Python) | Fetch del feed, parseo, filtrado, decisión de notificar |
| DynamoDB | Reemplaza `json_dedup_store.py` |
| SNS (tópico con suscripciones email + sms) | Reemplaza `log_notifier.py` |
| SSM Parameter Store o Secrets Manager | Lista de destinatarios |
| CloudWatch Logs + Alarm | Reemplaza logging local |
| Step Functions (opcional) | Solo si la lógica crece a múltiples pasos |

No añadir servicios fuera de esta lista sin actualizar este archivo y
justificar el cambio con el flujo working-backwards de `product.md`.

## Dependencias Python permitidas

**Fase local (actual):**
- `feedparser` (parseo del feed RSS)
- Solo stdlib para el resto: `json`, `logging`, `pathlib`, `datetime`

**Fase AWS (futura):**
- `boto3` / `botocore` (SDK de AWS)
- `aws-cdk-lib`, `constructs` (infraestructura)

Cualquier dependencia adicional debe evaluarse antes de añadirse. En la
fase local, priorizar stdlib para mantener el entorno simple.

## Shell

- **fish** es el shell por defecto del usuario; los ejemplos de comandos
  se muestran primero en fish.
- **bash** debe considerarse igualmente, ya que scripts de CI/CD, hooks de
  Git y algunas herramientas de terceros (incluyendo el propio tooling de
  CDK) asumen bash como shell portable por defecto. Todo script de
  automatización (`scripts/*.sh`) se escribe en bash, no en fish, para
  máxima compatibilidad entre entornos (CI, contenedores, otras máquinas).
- **zsh** debe soportarse como alternativa interactiva (por ejemplo si se
  usa en macOS donde es el shell por defecto del sistema, aunque el
  usuario prefiera fish). La sintaxis de zsh es compatible con bash en la
  mayoría de casos prácticos de este proyecto (variables, condicionales,
  pipes), por lo que no se requieren ejemplos separados salvo que se use
  una característica específica de zsh (ej. globbing extendido).
- Cuando un comando difiera entre shells, mostrar la variante de fish y la
  variante de bash (esta última también válida para zsh); si zsh requiere
  algo distinto, aclararlo explícitamente.
- Los scripts de automatización del repo (`scripts/*.sh`) deben incluir
  `#!/usr/bin/env bash` y pasar `shellcheck` (ver `linting.md`); no se
  versionan scripts `.fish` o `.zsh` de despliegue para evitar duplicar
  lógica en múltiples shells.
