# WORKPLAN.md — Plan de trabajo awstatusnotify

Plan de ejecución priorizado derivado del análisis de `DESIGN.md` y `TASKS.md`.
Define el orden exacto de las tareas, su justificación estratégica y los criterios
que deben cumplirse antes de avanzar a la siguiente.

> **Protocolo de avance:**
> 1. Kiro implementa la tarea activa completa (código + tests + lint + mypy).
> 2. Kiro presenta un resumen de lo entregado y solicita revisión al desarrollador.
> 3. El desarrollador revisa, señala mejoras o aprueba.
> 4. Kiro describe la siguiente tarea y espera confirmación para avanzar.

---

## Análisis de priorización

### Criterios aplicados

| Criterio | Peso | Descripción |
|---|---|---|
| **Valor inmediato** | Alto | ¿Resuelve una limitación que impide usar el sistema en producción? |
| **Resiliencia** | Alto | ¿Previene pérdida de datos o comportamiento silencioso incorrecto? |
| **Deuda técnica** | Medio | ¿Bloquea o complica tareas futuras si no se hace primero? |
| **Dependencias** | Alto | ¿Otras tareas lo necesitan como prerequisito? |
| **Esfuerzo** | Medio | ¿Cuánto cambia y a cuántos archivos toca? |

### Hallazgos del análisis

**Desde DESIGN.md — limitaciones activas que deben resolverse:**
1. `seen_incidents.json` crece indefinidamente → riesgo operativo real con el tiempo (Sección 12)
2. No hay retry en la descarga → un timeout transitorio genera silencio innecesario (Sección 9 + 12)
3. `log_notifier.py` no es un canal de alerta real → el sistema no notifica a nadie todavía (Sección 6.3)
4. No hay CLI → depurar requiere modificar código (Sección 7)
5. La calidad de código no está automatizada → el checklist pre-push depende de disciplina manual

**Desde TASKS.md — dependencias entre tareas:**
- T-09 (TTL) → prerequisito lógico de T-16 (DynamoDB TTL comparte el concepto)
- T-10 (retry) → independiente, pero mejora la confiabilidad antes de exponer notificaciones reales
- T-13 (SMTP) → prerequisito práctico de T-17 (SNS comparte el contrato de `Notifier`)
- T-14 (CLI) → depende de T-13 para `--dry-run` ser útil con un notifier real
- T-15 (pre-commit) → independiente, pero más valioso cuando hay más código que proteger
- T-11, T-12 → opcionales, sin dependientes directos, bajo riesgo de postergar
- T-16, T-17, T-18 → fase AWS, solo después de que la fase local esté completa y estable

---

## Plan de trabajo priorizado

### FASE 1 — Estabilidad del sistema local
*Objetivo: el sistema puede correr en producción local sin riesgos operativos.*

| Orden | ID | Título | Justificación |
|---|---|---|---|
| **1** | T-09 | TTL en dedup store | `seen_incidents.json` crece para siempre. Con el historial de incidentes analizado (EVT-002: >3,500h activo), un incidente puede generar cientos de entradas sin TTL. Riesgo de archivo enorme + IDs de incidentes resueltos hace meses que nunca expiran. |
| **2** | T-10 | Retry con backoff en feeds | La descarga de feeds es el único punto sin resiliencia. Con 17 slugs en `config.json.example`, un timeout transitorio en la red produce un ciclo completamente vacío. Corto, alto impacto. |

### FASE 2 — Notificaciones reales
*Objetivo: el sistema alerta a personas reales, no solo a un archivo de log.*

| Orden | ID | Título | Justificación |
|---|---|---|---|
| **3** | T-13 | Adapter SMTP | El sistema no notifica a nadie todavía. `log_notifier.py` es solo para desarrollo. SMTP es el paso mínimo para que el sistema cumpla su propósito real. Usa solo stdlib, sin nuevas dependencias. |
| **4** | T-11 | Notificación de resolución (opt-in) | Una vez que hay notificaciones reales (SMTP), el operador necesita saber también cuándo se resuelve el incidente. Pequeño cambio en `process_feed.py`. Se mueve aquí porque sin T-13 no hay forma de ver el valor real. |

### FASE 3 — Operabilidad y calidad
*Objetivo: el sistema es operable sin modificar código y la calidad se mantiene automáticamente.*

| Orden | ID | Título | Justificación |
|---|---|---|---|
| **5** | T-14 | CLI (dry-run, verbose, slug) | Con SMTP activo, necesitamos poder probar sin enviar emails reales. `--dry-run` se vuelve crítico. `--verbose` y `--slug` son esenciales para debugging operativo. |
| **6** | T-15 | Pre-commit hooks | Con 5 tareas acumuladas de código, es el momento de automatizar la calidad. Previene regresiones en el trabajo restante. |
| **7** | T-12 | Descubrimiento de slugs | AWS añade servicios nuevos. Con el análisis de incidentes históricos vimos 135-144 servicios afectados simultáneamente — la lista manual puede quedar desactualizada. Utilidad operativa clara. |

### FASE 4 — Migración a AWS
*Objetivo: el sistema corre en AWS con DynamoDB, SNS y Lambda.*
*Prerequisito: FASE 1, 2 y 3 completas y estables en producción local.*

| Orden | ID | Título | Justificación |
|---|---|---|---|
| **8** | T-16 | DynamoDB dedup store | Primer adapter AWS. El concepto de TTL de T-09 se hereda directamente. |
| **9** | T-17 | SNS notifier | Segundo adapter AWS. El contrato es idéntico a `SmtpNotifier` de T-13. |
| **10** | T-18 | Lambda handler + CDK | Cierra la migración completa. Requiere T-16 y T-17 funcionales y testeados. |

---

## Tabla resumen

| # | ID | Título | Fase | Estado |
|---|---|---|---|---|
| 1 | T-09 | TTL en dedup store | Estabilidad local | ⬜ Siguiente |
| 2 | T-10 | Retry con backoff en feeds | Estabilidad local | ⬜ Pendiente |
| 3 | T-13 | Adapter SMTP | Notificaciones reales | ⬜ Pendiente |
| 4 | T-11 | Notificación de resolución (opt-in) | Notificaciones reales | ⬜ Pendiente |
| 5 | T-14 | CLI (dry-run, verbose, slug) | Operabilidad | ⬜ Pendiente |
| 6 | T-15 | Pre-commit hooks | Calidad automática | ⬜ Pendiente |
| 7 | T-12 | Descubrimiento de slugs | Operabilidad | ⬜ Pendiente |
| 8 | T-16 | DynamoDB dedup store | Migración AWS | ⬜ Pendiente |
| 9 | T-17 | SNS notifier | Migración AWS | ⬜ Pendiente |
| 10 | T-18 | Lambda handler + CDK | Migración AWS | ⬜ Pendiente |

---

## Tarea activa: #1 — T-09 TTL en dedup store

### Descripción

`seen_incidents.json` acumula IDs indefinidamente. El análisis de incidentes históricos confirmó que un evento puede durar meses (EVT-002: >3,500h). Pasado su TTL, si un incidente con el mismo nombre volviera a aparecer en el feed, es correcto notificarlo de nuevo.

### Lo que se implementará

**`src/adapters/json_dedup_store.py`**
- Cambio de formato: `{"seen_ids": ["id1"]}` → `{"seen_ids": {"id1": "2026-07-18T12:00:00+00:00"}}`
- Constructor: nuevo parámetro `ttl_days: int = 90`
- `_load()`: filtra entradas cuyo timestamp sea anterior a `now - ttl_days`
- Migración automática del formato antiguo (lista → dict con `datetime.now(UTC)`)

**`config.json.example`**
- Añade campo opcional `"dedup_ttl_days": 90`

**`src/handler.py`**
- Lee `dedup_ttl_days` del config y lo pasa al constructor de `JsonDedupStore`

**`tests/integration/test_json_dedup_store.py`**
- 4 tests nuevos: `test_expired_entry_not_seen`, `test_fresh_entry_is_seen`,
  `test_migration_from_old_format`, `test_ttl_configurable`

**Criterios de aceptación:**
- [ ] Nuevo formato JSON con timestamps ISO 8601
- [ ] Entradas expiradas no se consideran "vistas"
- [ ] Formato antiguo migra sin pérdida de datos
- [ ] `ruff` ✅ · `mypy --strict` ✅ · `pytest` ✅

### Archivos que cambian
- `src/adapters/json_dedup_store.py` (refactor)
- `src/handler.py` (lectura de nuevo campo config)
- `config.json.example` (nuevo campo)
- `tests/integration/test_json_dedup_store.py` (4 tests nuevos)
- `TASKS.md` (T-09 → ✅ Completado)
- `WORKPLAN.md` (actualizar estado)

---

*Esperando aprobación para comenzar T-09.*
