# Evidencia reusable sin crear otro tracker

## Evidencia adaptada, no promesa del runtime

`pipelinek.evidence/v1` es un **formato propuesto para un adaptador** y NO una salida existente de `pipelinek steps` ni de `pipelinek run`. La autoridad de ejecución son eventos tipados + journal + artefactos verificados. Backlog.md sigue siendo dueño de tareas/decisiones. Un enlace corto de run o contenido basta en la tarea; no generar un segundo sistema administrativo.

Campos mínimos: `schema`, `workflow`, `source{commit,tree,dirty}`, `inputsDigest`, `runtime{version,buildCommit}`, `pluginsDigest`, `policyDigest`, `toolchainDigest`, `execution{runId,exit,outcome}`, `coverage{scope,selected,measured,skipped,notRun}`, `artifacts{paths,digests}`, `trustClass`.

## Estados y reutilización

- `PASS`, `FAIL`, `UNSTABLE`, `BLOCKED`, `NOT_RUN`, `NOT_MEASURED`. Falta de evento terminal, exit/outcome contradictorios, skipped obligatorio o reporte vacío jamás producen PASS.
- `scope`: `SUBSET`, `FULL`, `CERTIFICATION` no son convertibles entre sí. Un full del árbol fuente no equivale a un test de producto publicado.
- `trustClass`: un worker local no autenticado aporta evidencia operativa, no atestación independiente de release. La procedencia certificada requiere ejecutor con identidad y controles adecuados.
- Reutilizar solo con coincidencia de árbol, pipeline, inputs, toolchain, plugins, política, permisos y entorno significativo; dependencias temporales y recursos mutables pueden obligar a reejecutar. Proteger contra versiones obsoletas y evidencia fabricada.
- En clones/worktrees distintos, aislar journal, locks, workspace y archivos de evidencia. Un run `PENDING` no es PASS y un timeout no demuestra que el proceso haya muerto: reconciliar antes de reanudar.
- Si el supervisor recibe evidencia con origen y cobertura probados, reejecutar solo el oráculo decisivo o el componente invalidado, no toda la batería del worker.

## Seguridad

Guardar recibos sin payloads de comandos sensibles, secretos, valores de entorno, logs en claro ni paths con credenciales. Incluir hashes solo de artefactos permitidos. Un hash de contenido no autentica al productor: diferenciar integridad, procedencia y autorización.
