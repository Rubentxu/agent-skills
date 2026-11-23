# Convención opcional de automatizaciones de proyecto

## Regla de simplicidad

Un proyecto pequeño necesita únicamente `pipeline.kts`. Cuando existan varias automatizaciones con responsabilidades independientes, usar `pipelines/**/*.pipeline.kts`. Cada archivo es una entrada de ejecución autónoma; NO presuponer `@file:Import`, imports de scripts ni comando `pipelinek automation` sin soporte comprobado. El nombre de la carpeta clasifica la **finalidad**, no la política de obligatoriedad.

```text
repo/
├── pipeline.kts                     # punto de entrada principal (opcional)
├── pipelines/
│   ├── ci/
│   │   ├── affected.pipeline.kts    # solo si existe selección segura
│   │   └── full.pipeline.kts
│   ├── gates/
│   │   └── contracts.pipeline.kts
│   ├── certify/
│   │   └── installed-product.pipeline.kts
│   └── maintenance/
│       └── dependencies.pipeline.kts
└── scripts/                         # herramientas reales del repo
```

No generar estos ficheros vacíos ni directorios sin consumidores. No duplicar lógica del build system: `sh` invoca el wrapper/target existente. No separar artificialmente stages si la política del repo es una única autoridad como `scripts/verify-all.sh`.

## Convenciones operativas

- `ci`: fuente bajo desarrollo, tests focales y full gate definidos por la política del proyecto.
- `gates`: contratos y restricciones técnicas deterministas (API, arquitectura, seguridad). Los gates técnicos obligatorios no son trámites del backlog.
- `certify`: producto EMPAQUETADO/PUBLICADO, probado en consumidor limpio e independiente cuando el contrato lo exija. Certificar fuente no demuestra instalación de los bytes publicados.
- `maintenance`: tareas idempotentes o con efectos declarados; disparador externo optativo (`systemd`, `cron`, supervisor), nunca scheduler o cloud obligatorio.
- `pipeline.kts` puede ser la raíz o un entrypoint existente. No imponer alias ni capa de delegación inexistente.
- Estado de ejecución, diario y caché: XDG state/cache fuera del repo, aislamiento por identidad canónica de repo y worktree y permisos mínimos. Secretos nunca en artefactos versionados.
- Antes de migrar, registrar nombre del workflow anterior, criterio que comprueba, permisos, toolchain, inputs, outputs y efectos. No cambiar política sin una decisión explícita.
- Offline: pin de runtime y herramientas, dependencias provisionadas, plugins con trust/digest; si faltan, `BLOCKED_ENVIRONMENT`, no acceder a un servicio remoto silenciosamente.

## Promoción de trabajo repetido

Reutilizar primero, ampliar luego, extraer como pipeline cuando al menos dos operaciones reales comparten una garantía y su encapsulación reduce ambigüedad; NO crear un workflow por cada tarea de Backlog. Probar un positivo y un negativo pertinente en worktree desechable, preservar su identidad y registrar la evidencia mínima en la tarea.
