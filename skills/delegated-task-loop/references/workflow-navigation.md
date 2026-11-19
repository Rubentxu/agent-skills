# Router de affordances

Entrada JSON explícita, observada por el host; no accede a Backlog, Git, al filesystem del proyecto ni al agente. No es un motor transaccional. El estado no sustituye el tablero.

Campos: schemaVersion=1; kind=delegated-loop-state; phase (discover, ready, running, verify, review, accept, learn, release, interrupted, stopped); availableSkills (nombres confirmados); capabilities (booleanos observados: fresh, background, notify, progress, steer, cancel, resume, reviewReadOnly); budgetRemaining (entero no negativo); taskId (ID o null); signal (normal, repeated-failure, stalled, budget-exhausted, context-pressure, scope-drift, question, result); ownership (unknown, clear, active, terminated); evidence (unknown, sufficient, insufficient); review (none, required, resolved, not-run); outcome (unknown, accepted, blocked). Los booleanos ausentes son capacidades no confirmadas. El estado no concede autoridad.

```bash
python3 scripts/affordances.py examples/ready.json
```

El resultado devuelve decision, hasta dos lenses y _links con operaciones simbólicas. El host comprueba de nuevo precondiciones antes de actuar y aporta un nuevo estado observado. No ejecutar valores como comandos. No convertir un cambio de estado del router en transición Backlog.

- discover: descubrir skills/host y reconciliar intentos.
- ready: seleccionar tarea con Backlog; preparar contexto y delegar solo con ownership clear, capacidad fresh y presupuesto.
- running: observar por eventos si disponible, esperar resultado nativo o activar flow-recovery; no inferir capacidad de intervenir.
- verify/review: comprobar evidencia y revisión con el proveedor competente.
- accept: ofrecer cierre solo si evidencia suficiente, revisión no requerida o resuelta, y Backlog disponible; es una recomendación, no certificación.
- learn/release: aprendizaje opcional y limpieza segura; interrupted: reconciliar y recuperar, nunca relanzar un escritor de estado desconocido.

La señal se puede obtener del [reductor de eventos](event-supervision.md). Goldfish requiere fresh y reviewReadOnly observados. La capacidad no concede permiso ni verifica un revisor concreto.

Ready prepara anclajes, authority-handoff con taskDigest, plan de verificación y facts; validar el [brief v2](handoff-engineering.md) y permisos antes de utilizar delegate-after-preflight. No es un gate administrativo ni prueba semántica, y la estructura no permite omitir una obligación.

Signals pending, silence y resource-drift indican espera/reconciliación, no liberación ni cancelación. En interrupted se recomienda adopción de operaciones vivas antes de resume/replace. El journal exige inventario observado; las affordances siguen sin ejecutar nada.

Nuevos campos observados opcionales (ausencia = unknown): preflight unknown/needs-refinement/prepared, preflightRef obligatorio al prepared (referencia de brief validado y permisos revalidados), resourceState unknown/clear/live/adoptable. Ready con tarea ofrece preparar y validar; no ofrece delegación hasta contar con preflight preparado y recursos claros. Interrupted requiere clear o adoptable (inventario y adopción comprobados), verify/accept/release requieren clear (sin efectos pendientes incompatibles). Estas observaciones no conceden permisos ni sustituyen CAS del journal. Las entradas anteriores siguen válidas pero conservadoras.

Endurance añade señales relay-assess, relay-checkpoint, relay-deadline. En interrupted, relayRequired=true evita resume; relayReady=true significa baton y sucesor validados contra estado vigente, no permiso ni reserva. Solo con preflight prepared, recursos claros/adoptables, presupuesto y fresh confirmado se ofrece delegate-successor, siempre tras replace CAS. Ver [Endurance Relay](endurance-relay.md).
