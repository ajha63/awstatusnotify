---
inclusion: always
---

# Flujo de trabajo con Git

## Ramas

- `main`: siempre desplegable. Ningún commit directo; solo vía PR.
- `feature/<breve-descripcion>`: una rama por unidad de trabajo pequeña
  (ej. `feature/dynamo-dedup-store`, `feature/sns-notifier-adapter`).
- `fix/<breve-descripcion>`: correcciones puntuales.
- Sin ramas de larga duración tipo `develop`; el proyecto es pequeño y
  working-backwards favorece iteraciones cortas y desplegables.

## Commits

Usar Conventional Commits:

```
<tipo>(<alcance opcional>): <descripción en imperativo>
```

Tipos permitidos: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`,
`infra` (para cambios exclusivos de CDK/infraestructura).

Ejemplos:

```
feat(domain): agregar regla is_massive_impact
infra(notifier-stack): agregar alarma de CloudWatch para fallos del Lambda
docs(steering): actualizar lista de regiones vigiladas
```

- Un commit = un cambio lógico. Evitar commits que mezclen dominio +
  infraestructura salvo que sean inseparables.
- El cuerpo del commit (si se necesita) explica el *por qué*, no el *qué*
  (el diff ya dice el qué).

## Pull Requests

- Siempre contra `main`.
- Descripción mínima: outcome de negocio que resuelve (enlazar a
  `product.md` si aplica) + qué se dejó pendiente, si algo.
- CDK diff (`cdk diff`) pegado en la descripción cuando el PR toca
  `infra/`.
- Un PR pequeño y enfocado es preferible a uno grande; si crece, dividir.

## Firma de commits

Siguiendo la configuración ya establecida con 1Password como agente SSH/Git
signing (scoped a `~/src/CamiloSolutions/` vía `includeIf`), todos los
commits de este repositorio deben quedar firmados automáticamente si el
repo vive bajo esa ruta. Verificar con:

```fish
git log --show-signature -1
```

## Antes de hacer push

Checklist mínimo (ver `linting.md` para detalle de comandos):

1. Linter y formateador de Python en verde.
2. `mypy` sin errores en `domain/` y `application/` (adapters pueden tener
   excepciones documentadas si el SDK de AWS no tipa bien).
3. Tests unitarios de `domain/` pasan sin mocks de AWS.
4. `cdk synth` no falla, si se tocó `infra/`.

## Qué no hacer

- No mezclar en un mismo commit cambios de reglas de negocio
  (`domain/rules.py`) con cambios de recursos AWS (`infra/`) salvo que el
  cambio de infraestructura sea consecuencia directa e inseparable del
  cambio de dominio.
- No hacer `git commit --no-verify` para saltar hooks salvo emergencia
  documentada en el mensaje del commit.
