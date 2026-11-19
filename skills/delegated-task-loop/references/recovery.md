# Continuidad y recuperación

La conversación no es una fuente duradera. Mantener un checkpoint vigente en estado privado del host o bajo XDG_STATE_HOME (por defecto ~/.local/state)/agent-skills/delegated-task-loop, fuera del checkout, usando project binding y runId únicos. No almacenar secretos, transcripts ni datos de otras tareas. El checkpoint contiene referencias del intento, revisión, operaciones activas, recursos propios, presupuesto y siguiente acción. Los artefactos de evidencia permanecen en su proveedor.

Antes de sustituir o reanudar un worker: observar el handle nativo, Git/worktree, operaciones pendientes y estado real de Backlog. Un timeout o falta de fichero no certifican parada. Si ownership es desconocido, reconciliar primero y permitir trabajo independiente que no colisione. No recuperar un proceso mediante PID genérico ni borrar recursos ajenos. No resolver un conflicto destruyendo trabajo parcial.

Checkpoint antes de ceder control, y al recibir progreso material, resultado o interrupción. Revalidar autoridad con context_handoff receive. Si cambia el target o revisión, reevaluar evidencia y alcance. Mantener aprendizaje durable solo en el Knowledge Home. La limpieza comprueba ownership por recurso, no patrones globales de nombres. Registrar pendientes honestamente.

Usar [estado operativo](run-state.md) para reservar el escritor antes de lanzar, registrar el handle, confirmar parada y liberar. El router permanece puro. El helper solo coordina escritores cooperativos locales; el host verifica la parada real y el alcance de cada operación.

La parada del handle no acredita fin de sus operaciones. Aplicar [adopción](resource-adoption.md), inventario explícito y PENDING antes de sustituir o liberar; un worker nuevo hereda una operación viva y no la relanza. No liberar un recurso desconocido por mtime, timeout ni ausencia de PID.
