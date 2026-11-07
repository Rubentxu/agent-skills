# Reconciliación de hallazgos Goldfish

1. Leer tarea actual, duplicados, fuentes y revisión Git mediante CLI; comprobar cambios del SHA desde la revisión.
2. Diferenciar defecto confirmado, sospecha, riesgo, opinión, refutación y evidencia ausente. Considerar KEEP_AS_IS frente al coste/beneficio y radio de impacto.
3. Registrar progreso en la tarea existente con `--append-notes`; crear documento Backlog para conocimiento reusable etiquetado `kind:research/risk/invariant`, contexto y términos; registrar decisiones mediante `backlog decision` solo con procedencia humana aprobada.
4. Nueva tarea solo para entrega independiente justificada, tras buscar duplicados, y respetando WIP. Nunca usar reportes o hooks como autorización.
5. Verificar help de CLI local y releer tras cada operación. La lente no ejecuta comandos.

**Salida:** KEEP_AS_IS, PROPOSE_CHANGE, EXPERIMENT, NEED_EVIDENCE o BLOCKED.
