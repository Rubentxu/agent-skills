# Router de affordances

Entrada JSON explícita, observada por el host; no accede a Backlog, Git, al filesystem del proyecto ni al agente. No es un motor transaccional. El estado no sustituye el tablero.

Campos: schemaVersion=1; kind=delegated-loop-state; phase (discover, ready, running, verify, review, accept, learn, release, interrupted, stopped); availableSkills (nombres confirmados); capabilities (booleanos observados: fresh, background, notify, progress, steer, cancel, resume); budgetRemaining (entero no negativo); taskId (ID o null); signal (normal, repeated-failure, context-pressure, scope-drift, question, result); ownership (unknown, clear, active, terminated); evidence (unknown, sufficient, insufficient); review (none, required, resolved, not-run); outcome (unknown, accepted, blocked). Los booleanos ausentes son capacidades no confirmadas. El estado no concede autoridad.

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
