# Delegación nativa

El supervisor conserva ownership del objetivo. Topología estrella: un worker escritor por defecto; no delegación recursiva. Usar exclusivamente herramientas anunciadas del host.

El [brief v2](handoff-engineering.md) se prepara por el supervisor, resuelve preguntas materiales y contiene project binding, runId, taskId, attemptId, revisión Git completa, objetivo, AC/DoD efectivos, alcance permitido, restricciones, presupuesto, referencias al handoff y context-pack, formato de resultado y política de stop. Ver [plantilla](../assets/worker-prompt.md). Validar el sobre y el resultado con [contratos operativos](contracts.md). No duplicar los contratos semánticos de los proveedores.

Fresh: tarea nueva o revisor independiente. Resume: mismo worker para corrección o continuación cuando el host lo permita, revalidando fuentes y permisos. Fork: solo si el host expone esa opción y la información heredada está acotada; nunca para Goldfish. Sin fresh real, NOT_RUN.

Resultado mínimo: identidad de intento, outcome READY_FOR_REVIEW/PENDING/PARTIAL/BLOCKED/FAILED, repos/revisiones, AC observados y referencias de pruebas, pendientes, recursos propios, siguiente acción y candidatos de aprendizaje. No autoconceder Done.

Antes de aceptar: contrastar identidad, revisión actual, evidencia y política Git efectiva. El supervisor o actor autorizado actualiza Backlog mediante su proveedor. No cerrar otra tarea ni ampliar alcance sin autorización.

Referencias de patrones: [Superpowers](https://github.com/obra/superpowers), [GSD](https://github.com/gsd-build/get-shit-done), [Building effective agents](https://www.anthropic.com/research/building-effective-agents). Inspiración, no copia de prompts ni garantía de rendimiento.
