# Trazabilidad mínima, orientada a entregas

## Fuente única de tracking

Backlog.md conserva tareas, planes, hitos, decisiones, estados, dependencias, criterios y progreso. No pedir `ROADMAP.md`, `CHANGELOG.md`, ADR o especificaciones de gestión separados para trabajar. Las decisiones y documentos nativos de Backlog.md ofrecen contexto durable; las guías técnicas de producto pueden existir cuando son útiles a sus consumidores.

Git indica qué código cambió. Las pruebas y revisiones pertinentes demuestran las propiedades verificadas. Ni un commit ni un gate de gestión sustituyen esa evidencia.

## Mensajes de commit sencillos

Escribir qué se cambió y por qué. Enlazar el ID real de Backlog.md solo cuando facilite navegación:

```text
fix(runtime): preservar el orden de efectos en reintentos

Evita duplicar un efecto al reanudar ejecución.
Backlog-Task: TASK-42
```

No exigir trailers `Roadmap-Block`, `ADR-Ref`, `Spec-Ref`, `Implementation` ni `Verification` para permitir commits o cierres. Respetar convenciones existentes; no inventar ceremonias.

## Evitar duplicados, registrar hechos

1. Buscar tareas relacionadas en Backlog.md, incluidas archivadas si corresponde.
2. Inspeccionar comportamiento de código existente para no reimplementar capacidades.
3. Registrar en la tarea entregas, pruebas reales (incluyendo `NOT_RUN` cuando aplique) y cerrar al cumplir aceptación y garantías pertinentes.
4. `commit_trace.py` y `spec_projection.py` se reservan para **migraciones históricas solicitadas**, no son herramientas de uso obligatorio.

Los IDs administrativos no deben insertarse en docstrings ni comentarios del producto. El código explica cómo, la documentación su contrato, Backlog.md y Git conservan la historia de gestión e implementación.
