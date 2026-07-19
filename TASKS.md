# TASKS.md — awstatusnotify

Plan de implementación incremental. Cada tarea es una unidad de trabajo autónoma que entrega valor verificable. Las tareas están ordenadas por dependencia y prioridad.

> **Convención:** una tarea = una rama `feature/<id>-<desc>` + un PR + un conjunto de tests que pasan. Ninguna tarea se marca como completada hasta que `ruff`, `mypy` y `pytest` estén en verde.

---

## Estado de las tareas

| ID | Título | Estado | Rama |
|---|---|---|---|
| T-01 | Scaffold y configuración base | ✅ Completado | — (main) |
| T-02 | Entidad de dominio `Incident` | ✅ Completado | — (main) |
| T-03 | Reglas de negocio del dominio | ✅ Completado | — (main) |
| T-04 | Adapter `health_feed.py` — parseo RSS real | ✅ Completado | — (main) |
| T-05 | Adapter `json_dedup_store.py` | ✅ Completado | — (main) |
| T-06 | Adapter `log_notifier.py` | ✅ Completado | — (main) |
| T-07 | Caso de uso `process_feed` | ✅ Completado | — (main) |
| T-08 | Entry point `handler.py` | ✅ Completado | — (main) |
| T-09 | Limpieza automática del dedup store (TTL local) | ✅ Completado | `feature/t09-dedup-ttl` |
| T-10 | Retry con backoff en descarga de feeds | ⬜ Pendiente | `feature/t10-feed-retry` |
| T-11 | Notificación de resolución de incidentes | ⬜ Pendiente | `feature/t11-notify-resolved` |
| T-12 | Descubrir slugs dinámicamente desde el índice HTML | ⬜ Pendiente | `feature/t12-slug-discovery` |
| T-13 | Adapter `smtp_notifier.py` — email real vía SMTP | ⬜ Pendiente | `feature/t13-smtp-notifier` |
| T-14 | CLI con argumentos (dry-run, verbose, one-shot) | ⬜ Pendiente | `feature/t14-cli` |
| T-15 | Pre-commit hooks automatizados | ⬜ Pendiente | `feature/t15-pre-commit` |
| T-16 | Adapter `dynamo_dedup_store.py` — fase AWS | ⬜ Pendiente | `feature/t16-dynamo-dedup` |
| T-17 | Adapter `sns_notifier.py` — fase AWS | ⬜ Pendiente | `feature/t17-sns-notifier` |
| T-18 | Lambda handler + infraestructura CDK | ⬜ Pendiente | `feature/t18-lambda-infra` |

---

## Detalle de tareas pendientes

---

### T-09 — Limpieza automática del dedup store (TTL local)

**Prioridad:** Media  
**Dependencias:** T-05 (completado)  
**Rama:** `feature/t09-dedup-ttl`

**Contexto:**  
`seen_incidents.json` crece indefinidamente. Un incidente de hace 6 meses ya no necesita deduplicación — si vuelve a aparecer en el feed (raro pero posible tras rotación del feed), es legítimo notificarlo de nuevo.

**Objetivo:**  
Agregar TTL configurable al `JsonDedupStore`. Las entradas más antiguas que N días se eliminan automáticamente en cada ciclo de `mark_seen` o en una operación explícita de limpieza.

**Cambios requeridos:**

1. **`json_dedup_store.py`** — cambiar el formato de almacenamiento:
   ```json
   {
     "seen_ids": {
       "a3f8c1d2e4b56789": "2026-07-18T12:00:00+00:00",
       "b7e2f4a1c3d58920": "2026-06-01T08:30:00+00:00"
     }
   }
   ```
   - La clave es el `incident_id`, el valor es el ISO 8601 de cuándo fue marcado.
   - Migración: si el archivo tiene el formato antiguo (`list`), convertirlo automáticamente asignando `datetime.now(UTC)` a todas las entradas.

2. **`JsonDedupStore.__init__`** — aceptar `ttl_days: int = 90` como parámetro.

3. **`JsonDedupStore._load`** — al cargar, filtrar las entradas con `seen_at < now - ttl_days`.

4. **`config.json.example`** — añadir campo opcional `"dedup_ttl_days": 90`.

5. **`handler.py`** — leer `dedup_ttl_days` de config y pasarlo al constructor.

**Tests a agregar (`tests/integration/test_json_dedup_store.py`):**
- `test_expired_entry_not_seen`: entrada con fecha hace 91 días no aparece como vista.
- `test_fresh_entry_is_seen`: entrada con fecha de hoy sí aparece como vista.
- `test_migration_from_old_format`: archivo con formato lista es migrado correctamente.
- `test_ttl_configurable`: TTL de 0 días elimina todas las entradas al cargar.

**Criterios de aceptación:**
- [ ] El archivo JSON usa el nuevo formato con timestamps.
- [ ] Las entradas más antiguas que `ttl_days` no se consideran "vistas".
- [ ] El formato antiguo (lista de IDs) se migra automáticamente sin pérdida.
- [ ] `ruff`, `mypy --strict` y `pytest` en verde.

---

### T-10 — Retry con backoff en descarga de feeds

**Prioridad:** Media  
**Dependencias:** T-04 (completado)  
**Rama:** `feature/t10-feed-retry`

**Contexto:**  
Un timeout transitorio en `_fetch_xml` marca el feed como fallido para ese ciclo. Sin retry, un pico de latencia momentáneo genera un ciclo vacío innecesariamente.

**Objetivo:**  
Implementar retry con backoff exponencial en `_fetch_xml`. Máximo 3 intentos. Delay inicial de 2 segundos, multiplicador 2 (2s → 4s → 8s).

**Cambios requeridos:**

1. **`health_feed.py`** — nueva función `_fetch_xml_with_retry`:
   ```python
   def _fetch_xml_with_retry(
       url: str,
       max_attempts: int = 3,
       initial_delay_s: float = 2.0,
   ) -> str:
       ...
   ```
   - Usar `time.sleep` entre intentos.
   - Loguear cada intento fallido con nivel WARNING.
   - Loguear el intento exitoso después de fallos previos con nivel INFO.
   - Después del último intento fallido, lanzar `RuntimeError`.

2. **`_fetch_xml`** — convertirse en thin wrapper de `_fetch_xml_with_retry`.

3. **`config.json.example`** — añadir campos opcionales:
   ```json
   "fetch_max_attempts": 3,
   "fetch_initial_delay_s": 2.0
   ```

**Tests a agregar (`tests/unit/test_health_feed_parser.py`):**  
Con `unittest.mock.patch` sobre `subprocess.run`:
- `test_retry_succeeds_on_second_attempt`: falla una vez, tiene éxito en la segunda.
- `test_retry_exhausted_raises`: falla 3 veces, lanza `RuntimeError`.
- `test_no_retry_on_success`: éxito inmediato, solo 1 llamada a subprocess.

**Criterios de aceptación:**
- [ ] Máximo 3 intentos por feed antes de loguear error y continuar.
- [ ] Delay entre intentos es exponencial (no lineal).
- [ ] El ciclo completo no falla si un feed agota sus reintentos.
- [ ] `ruff`, `mypy --strict` y `pytest` en verde.

---

### T-11 — Notificación de resolución de incidentes

**Prioridad:** Baja  
**Dependencias:** T-03, T-07 (completados)  
**Rama:** `feature/t11-notify-resolved`

**Contexto:**  
Actualmente `should_notify` retorna `False` para incidentes RESOLVED (DEC-009). No se notifica el cierre. Esto es correcto como comportamiento por defecto, pero algunos operadores necesitan saber cuándo un incidente se resuelve.

**Objetivo:**  
Agregar comportamiento opt-in de notificación al resolverse un incidente, configurable en `config.json`.

**Cambios requeridos:**

1. **`process_feed.py`** — agregar parámetro `notify_on_resolve: bool = False`:
   ```python
   def process_feed(
       fetcher, dedup, notifier,
       critical_services, watched_regions,
       notify_on_resolve: bool = False,
   ) -> int:
   ```
   Lógica adicional: si `notify_on_resolve` es `True` y el incidente está RESOLVED Y el `incident_id` está en el dedup store (fue notificado al abrirse), notificar la resolución y limpiar la entrada del dedup store.

2. **`domain/rules.py`** — sin cambios (el dominio no sabe de preferencias del operador).

3. **`config.json.example`** — agregar `"notify_on_resolve": false`.

4. **`handler.py`** — leer `notify_on_resolve` de config y pasarlo a `process_feed`.

5. **`log_notifier.py`** — el formato de log ya incluye `status`, por lo que las notificaciones de resolución serán distinguibles (`status=resolved`).

**Tests a agregar (`tests/unit/test_process_feed.py`)** (archivo nuevo):
- `test_notify_on_resolve_true_notifies_resolved_incident`: incidente RESOLVED notificado cuando flag es True.
- `test_notify_on_resolve_false_skips_resolved_incident`: incidente RESOLVED no notificado cuando flag es False (comportamiento actual).
- `test_resolved_removed_from_dedup_store`: tras notificar resolución, el ID se elimina del store.

**Criterios de aceptación:**
- [ ] `notify_on_resolve: false` mantiene el comportamiento actual exactamente.
- [ ] `notify_on_resolve: true` emite notificación cuando un incidente previamente visto pasa a RESOLVED.
- [ ] La entrada se elimina del dedup store tras notificar la resolución (para no volver a notificar si el feed lo repite).
- [ ] `ruff`, `mypy --strict` y `pytest` en verde.

---

### T-12 — Descubrir slugs dinámicamente desde el índice HTML

**Prioridad:** Baja  
**Dependencias:** T-04 (completado)  
**Rama:** `feature/t12-slug-discovery`

**Contexto:**  
Los slugs actuales están hardcodeados en `config.json`. AWS añade y quita servicios ocasionalmente. Mantener la lista manualmente es tedioso y propenso a omisiones.

**Objetivo:**  
Agregar un comando o función de utilidad que descargue `https://status.aws.amazon.com/`, extraiga todos los slugs RSS disponibles y los filtre según `watched_regions` y `critical_services`.

**Cambios requeridos:**

1. **`src/adapters/health_feed.py`** — nueva función pública:
   ```python
   def discover_slugs(
       watched_regions: list[str],
       critical_services: list[str],
   ) -> list[str]:
       """Descarga el índice de AWS y retorna los slugs relevantes."""
   ```
   - Descargar `https://status.aws.amazon.com/` con curl.
   - Extraer todos los `href="rss/<slug>.rss"` con regex.
   - Filtrar slugs que coincidan con las regiones vigiladas o con los servicios críticos.
   - Incluir siempre los slugs `multipleservices-<region>` para las regiones vigiladas.

2. **`src/handler.py`** — modo de descubrimiento:
   ```bash
   python -m src.handler --discover-slugs
   ```
   Imprime los slugs sugeridos en formato JSON, listos para copiar en `config.json`.

**Tests a agregar (`tests/unit/test_health_feed_parser.py`):**
Con HTML de muestra (fixture local, sin red):
- `test_discover_slugs_filters_by_region`: solo retorna slugs de regiones vigiladas.
- `test_discover_slugs_includes_critical_services`: incluye servicios críticos globales.
- `test_discover_slugs_includes_multipleservices`: incluye slugs `multipleservices-<region>`.

**Criterios de aceptación:**
- [ ] El comando `--discover-slugs` imprime JSON válido con slugs relevantes.
- [ ] Funciona sin necesidad de actualizar manualmente `references/feed-slugs.md`.
- [ ] `ruff`, `mypy --strict` y `pytest` en verde.

---

### T-13 — Adapter `smtp_notifier.py` — email real vía SMTP

**Prioridad:** Alta (primer paso hacia notificaciones reales)  
**Dependencias:** T-06 (completado)  
**Rama:** `feature/t13-smtp-notifier`

**Contexto:**  
El `log_notifier.py` es útil para desarrollo pero no sirve como canal de alerta real. SMTP es el primer paso hacia notificaciones reales sin necesidad de infraestructura AWS.

**Objetivo:**  
Implementar `SmtpNotifier` que envíe un email estructurado por cada incidente notificable.

**Cambios requeridos:**

1. **`src/adapters/smtp_notifier.py`** — nueva clase:
   ```python
   class SmtpNotifier:
       def __init__(
           self,
           smtp_host: str,
           smtp_port: int,
           sender: str,
           recipients: list[str],
           use_tls: bool = True,
           username: str | None = None,
           password: str | None = None,
       ) -> None: ...

       def notify(self, incident: Incident) -> None:
           # Construir email con subject y body estructurado
           # Enviar via smtplib (stdlib)
           ...
   ```

2. **Formato del email:**
   - Subject: `[{severity.upper()}] AWS {service} — {title} ({region})`
   - Body (texto plano): campos del incidente formateados, incluyendo `has_rca` y `detected_at`.

3. **`config.json.example`** — agregar sección `smtp`:
   ```json
   "smtp": {
     "host": "smtp.gmail.com",
     "port": 587,
     "sender": "alerts@example.com",
     "recipients": ["oncall@example.com"],
     "use_tls": true,
     "username_env": "SMTP_USER",
     "password_env": "SMTP_PASS"
   }
   ```
   Las credenciales se leen de variables de entorno (nunca en el JSON).

4. **`handler.py`** — seleccionar el notifier según la config:
   - Si existe `config["smtp"]` → usar `SmtpNotifier`.
   - Si no → usar `LogNotifier` (fallback actual).

**Tests a agregar (`tests/unit/test_smtp_notifier.py`):**
Con `unittest.mock.patch("smtplib.SMTP")`:
- `test_notify_sends_email`: verifica que `sendmail` es llamado con subject y recipients correctos.
- `test_subject_includes_severity`: subject tiene el formato correcto.
- `test_credentials_from_env`: usa variables de entorno para usuario y contraseña.
- `test_smtp_error_propagates`: error de smtplib no es suprimido silenciosamente.

**Criterios de aceptación:**
- [ ] Las credenciales nunca se leen del JSON directamente (solo env vars).
- [ ] Si `smtp` no está en config, el comportamiento es idéntico al actual.
- [ ] Error de envío loguea el error pero no detiene el ciclo (tolerante a fallos de red).
- [ ] `ruff`, `mypy --strict` y `pytest` en verde.

---

### T-14 — CLI con argumentos (dry-run, verbose, one-shot)

**Prioridad:** Media  
**Dependencias:** T-08 (completado)  
**Rama:** `feature/t14-cli`

**Contexto:**  
`handler.py` no tiene interfaz CLI. No hay forma de hacer un dry-run, aumentar verbosidad o ejecutar contra un feed específico sin modificar el código.

**Objetivo:**  
Agregar una CLI con `argparse` que exponga las opciones más útiles para operación y debugging.

**Cambios requeridos:**

1. **`src/handler.py`** — agregar parser de argumentos:

   | Argumento | Descripción |
   |---|---|
   | `--dry-run` | Evalúa incidentes y loguea los que notificaría, sin escribir al dedup store ni al notifier. |
   | `--verbose` | Cambia el nivel de log raíz a DEBUG (muestra incidentes omitidos). |
   | `--slug SLUG` | Procesa solo el slug indicado, ignorando `feed_slugs` del config. Útil para debugging. |
   | `--config PATH` | Ruta alternativa al archivo de configuración (default: `config.json`). |
   | `--list-slugs` | Equivalente a `--discover-slugs` de T-12 (dependencia opcional). |

2. **`process_feed.py`** — sin cambios en la firma pública. El dry-run se implementa en `handler.py` pasando un `Notifier` que solo loguea sin efecto.

**Tests a agregar (`tests/unit/test_handler_cli.py`)** (archivo nuevo):
- `test_dry_run_does_not_write_dedup`: con `--dry-run`, el dedup store no se modifica.
- `test_verbose_sets_debug_level`: con `--verbose`, el nivel de log es DEBUG.
- `test_config_path_arg`: con `--config /ruta`, se lee esa ruta.

**Criterios de aceptación:**
- [ ] `python -m src.handler --help` muestra todos los argumentos con descripción.
- [ ] `--dry-run` no modifica `seen_incidents.json` ni escribe notificaciones reales.
- [ ] `--slug ec2-us-east-1` procesa solo ese feed.
- [ ] `ruff`, `mypy --strict` y `pytest` en verde.

---

### T-15 — Pre-commit hooks automatizados

**Prioridad:** Media  
**Dependencias:** ninguna  
**Rama:** `feature/t15-pre-commit`

**Contexto:**  
El checklist pre-push está documentado en `git-workflow.md` pero no está automatizado. Es fácil olvidar ejecutarlo.

**Objetivo:**  
Configurar pre-commit hooks que ejecuten automáticamente `ruff`, `mypy` y `pytest` antes de cada commit.

**Cambios requeridos:**

1. **`.pre-commit-config.yaml`** (archivo nuevo en raíz):
   ```yaml
   repos:
     - repo: https://github.com/astral-sh/ruff-pre-commit
       rev: v0.5.7
       hooks:
         - id: ruff
         - id: ruff-format

     - repo: local
       hooks:
         - id: mypy
           name: mypy
           entry: .venv/bin/mypy src/
           language: system
           pass_filenames: false

         - id: pytest-unit
           name: pytest (unit tests only)
           entry: .venv/bin/pytest tests/unit/ -q
           language: system
           pass_filenames: false
   ```

2. **`pyproject.toml`** — agregar `pre-commit` a dev dependencies:
   ```toml
   [project.optional-dependencies]
   dev = [
       ...
       "pre-commit==3.7.1",
   ]
   ```

3. **README.md** — agregar instrucción de instalación:
   ```bash
   pip install -e ".[dev]"
   pre-commit install
   ```

4. **`git-workflow.md`** — actualizar la sección "Antes de hacer push" para indicar que los hooks son automáticos.

**Criterios de aceptación:**
- [ ] `pre-commit install` instala los hooks correctamente.
- [ ] Un commit con código que falla `ruff` es rechazado automáticamente.
- [ ] Un commit con tests rotos es rechazado automáticamente.
- [ ] Los hooks no tienen falsos positivos en el código existente.

---

### T-16 — Adapter `dynamo_dedup_store.py` — fase AWS

**Prioridad:** Baja (fase AWS)  
**Dependencias:** T-05, T-09 (completados/pendientes)  
**Rama:** `feature/t16-dynamo-dedup`

**Contexto:**  
Primer adapter de la migración a AWS. Reemplaza `json_dedup_store.py` sin modificar el dominio ni el caso de uso.

**Objetivo:**  
Implementar `DynamoDedupStore` con el mismo contrato que `JsonDedupStore`.

**Cambios requeridos:**

1. **`src/adapters/dynamo_dedup_store.py`** — nueva clase:
   ```python
   class DynamoDedupStore:
       def __init__(
           self,
           table_name: str,
           boto_client: Any,  # type: ignore[misc]
           ttl_days: int = 30,
       ) -> None: ...

       def is_seen(self, incident_id: str) -> bool: ...
       def mark_seen(self, incident_id: str) -> None:
           # PutItem con partition key = incident_id
           # TTL attribute = epoch(now + ttl_days)
           ...
   ```

2. **Schema DynamoDB:**
   - Partition key: `incident_id` (String)
   - TTL attribute: `expires_at` (Number, epoch UTC)
   - Sin sort key (no se necesita)

3. **Tests (`tests/integration/test_dynamo_dedup_store.py`):**
   Usar `moto` para mockear DynamoDB:
   ```python
   @pytest.fixture
   def ddb_table(aws_credentials):
       with mock_aws():
           client = boto3.client("dynamodb", region_name="us-east-1")
           client.create_table(...)
           yield client
   ```
   - `test_new_id_not_seen`
   - `test_mark_seen_persists`
   - `test_ttl_attribute_is_set`
   - `test_table_not_found_raises`

**Criterios de aceptación:**
- [ ] El contrato es idéntico a `JsonDedupStore` (intercambiables sin cambiar `handler.py`).
- [ ] TTL se almacena como atributo numérico (epoch) para que DynamoDB lo expire automáticamente.
- [ ] Los tests usan `moto`, no AWS real.
- [ ] `ruff`, `mypy` y `pytest` en verde.

---

### T-17 — Adapter `sns_notifier.py` — fase AWS

**Prioridad:** Baja (fase AWS)  
**Dependencias:** T-13 (pendiente, recomendado primero), T-06 (completado)  
**Rama:** `feature/t17-sns-notifier`

**Objetivo:**  
Implementar `SnsNotifier` que publica en un tópico SNS.

**Cambios requeridos:**

1. **`src/adapters/sns_notifier.py`**:
   ```python
   class SnsNotifier:
       def __init__(self, topic_arn: str, boto_client: Any) -> None: ...
       def notify(self, incident: Incident) -> None:
           # sns.publish(TopicArn=..., Subject=..., Message=...)
           ...
   ```

2. **Formato del mensaje SNS:**
   - Subject (máx 100 chars): `[{severity}] AWS {service} — {title[:60]} ({region})`
   - Message: texto estructurado con todos los campos del `Incident`.

3. **Tests (`tests/integration/test_sns_notifier.py`):** usar `moto`.

**Criterios de aceptación:**
- [ ] El subject nunca supera 100 caracteres (límite de SNS).
- [ ] `ruff`, `mypy` y `pytest` en verde.

---

### T-18 — Lambda handler + infraestructura CDK

**Prioridad:** Baja (fase AWS)  
**Dependencias:** T-16, T-17 (pendientes)  
**Rama:** `feature/t18-lambda-infra`

**Objetivo:**  
Convertir `handler.py` en Lambda handler y crear el stack CDK con todos los recursos AWS.

**Cambios requeridos:**

1. **`src/handler.py`** — agregar `lambda_handler`:
   ```python
   def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, int]:
       # Crea clientes boto3, lee config de SSM/env, ejecuta main(), retorna count
       ...
   ```

2. **`infra/stacks/notifier_stack.py`** — stack CDK:
   - `aws_lambda.Function` (Python 3.12, timeout 60s, memory 256MB)
   - `aws_dynamodb.Table` (PAY_PER_REQUEST, TTL habilitado)
   - `aws_sns.Topic` con suscripciones email + SMS
   - `aws_scheduler.Schedule` (cron cada 5 minutos)
   - `aws_cloudwatch.Alarm` (errores del Lambda > 0 en 5 minutos)
   - `aws_ssm.StringParameter` para lista de destinatarios

3. **`infra/app.py`** — CDK App.

**Criterios de aceptación:**
- [ ] `cdk synth` no produce errores.
- [ ] `cfn-lint` sobre el template sintetizado no produce errores.
- [ ] El Lambda puede ejecutarse localmente con SAM CLI o invocación directa.
- [ ] La alarma CloudWatch se dispara si el Lambda falla.

---

## Orden de implementación recomendado

Para el mayor valor en el menor tiempo:

```
T-09 (TTL dedup)
  → T-10 (retry feeds)
    → T-13 (SMTP — notificaciones reales)
      → T-14 (CLI — operabilidad)
        → T-15 (pre-commit — calidad automática)
          → T-11 (notify resolved — opcional)
          → T-12 (slug discovery — opcional)
          → T-16 (DynamoDB)
            → T-17 (SNS)
              → T-18 (Lambda + CDK)
```

Las tareas T-09 a T-15 completan la fase local. Las tareas T-16 a T-18 son la migración a AWS y pueden hacerse en paralelo una vez que T-09 y T-13 estén completas.
