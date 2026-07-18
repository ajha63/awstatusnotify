---
inclusion: always
---

# Linters y formateadores

## Python (aplicación + CDK)

Herramientas: **ruff** (lint + formato, reemplaza flake8/isort/black) y
**mypy** (tipado estático).

`pyproject.toml` (fragmento de referencia):

```toml
[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.12"
strict = true
exclude = ["adapters/"]  # SDK de AWS no siempre tipa bien; revisar caso a caso
```

Comandos (fish):

```fish
ruff check .
ruff format .
mypy src/
```

Reglas:

- `domain/` y `application/` deben pasar `mypy --strict` sin excepciones.
- `adapters/` puede usar `# type: ignore` puntual, siempre con comentario
  explicando por qué (no un ignore silencioso genérico).
- Cero warnings de `ruff` antes de abrir PR.

## Bash

Herramienta: **shellcheck**.

```fish
shellcheck scripts/*.sh
```

- Cualquier script `.sh` en el repo (deploy, utilidades) debe pasar
  shellcheck sin warnings, o justificar el `# shellcheck disable=SCxxxx`
  inline.

## Fish

No hay un linter estándar equivalente a shellcheck para fish. Convención:

- Scripts `.fish` deben poder ejecutarse con `fish -n <script>` (chequeo
  de sintaxis sin ejecutar) sin errores antes de commitear.
- Preferir funciones cortas y explícitas sobre one-liners densos, ya que
  fish tiene menos tooling de análisis estático que bash.

```fish
fish -n scripts/deploy.fish
```

## Infraestructura (CDK)

- `cdk synth` debe ejecutarse sin errores como parte del checklist
  pre-push (ver `git-workflow.md`).
- Opcional pero recomendado: `cfn-lint` sobre el CloudFormation sintetizado
  para detectar problemas de plantilla que CDK no valida por sí solo:

```fish
cdk synth > /tmp/template.yaml
cfn-lint /tmp/template.yaml
```

## Integración con CI (referencia, no bloqueante para este documento)

El orden esperado de un pipeline de verificación es:

1. `ruff check .`
2. `mypy src/`
3. Tests unitarios (`domain/`, sin AWS)
4. Tests de integración (`adapters/`, con `moto` o mocks de boto3)
5. `cdk synth`
6. `cfn-lint` sobre el template sintetizado
