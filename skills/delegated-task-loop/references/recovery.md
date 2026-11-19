# Continuidad y recuperación

La conversación no es una fuente duradera. Mantener un checkpoint vigente en estado privado del host o bajo XDG_STATE_HOME (por defecto ~/.local/state)/agent-skills/delegated-task-loop, fuera del checkout, usando project binding y runId únicos. No almacenar secretos, transcripts ni datos de otras tareas. El checkpoint contiene referencias del intento, revisión, operaciones activas, recursos propios, presupuesto y siguiente acción. Los artefactos de evidencia permanecen en su proveedor.

Antes de sustituir o reanudar un worker: observar el handle nativo, Git/worktree, operaciones pendientes y estado real de Backlog. Un timeout o falta de fichero no certifican parada. Si ownership es desconocido, reconciliar primero y permitir trabajo independiente que no colisione. No recuperar un proceso mediante PID genérico ni borrar recursos ajenos. No resolver un conflicto destruyendo trabajo parcial.

Checkpoint antes de ceder control, y al recibir progreso material, resultado o interrupción. Revalidar autoridad con context_handoff receive. Si cambia el target o revisión, reevaluar evidencia y alcance. Mantener aprendizaje durable solo en el Knowledge Home. La limpieza comprueba ownership por recurso, no patrones globales de nombres. Registrar pendientes honestamente.

Primer incremento: este procedimiento se ejecuta por el anfitrión; el router no mantiene ni bloquea estado persistente. Hasta disponer de reserva local atómica, no ejecutar varios supervisores sobre el mismo proyecto/alcance.
