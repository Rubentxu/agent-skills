---
name: delegated-task-loop
description: "Coordina tareas Backlog.md mediante subagentes nativos, contexto mínimo, supervisión reactiva, evidencia y aprendizaje acumulativo. Úsala para delegar una secuencia acotada de tareas sin lanzar otros procesos del agente ni depender de PipelineK."
---

# Delegated Task Loop

El agente anfitrión es el supervisor Elephant. Una delegación, una tarea, contexto suficiente; el supervisor no implementa rutinariamente ni acumula conversaciones. Los workers son sustituibles; el conocimiento y la evidencia no.

## Entrada: observar antes de actuar

1. Fijar objetivo, alcance, autorización y límite de tareas/intentos. Si se pide vaciar el tablero, acordar un límite de ejecución o detenerse al agotar el presupuesto del host; nunca interpretar autonomía como permiso ilimitado.
2. Descubrir capacidades reales de delegación fresca, background, notificación, intervención, cancelación y reanudación. No inferirlas por nombre del host. Consultar [hosts](references/host-capabilities.md); usar [canaries nativos](references/host-canaries.md) cuando falte evidencia de capacidades.
3. Descubrir las skills instaladas por el mecanismo del host. Localizar el Home Repo registrado mediante software-knowledge; Backlog.md es la única autoridad de trabajo. Leer las políticas AGENTS.md aplicables, incluidas las de cada repositorio afectado.
4. Ejecutar el router puro con un objeto de estado observado: `python3 scripts/affordances.py -`. Ver [navegación](references/workflow-navigation.md). Leer como máximo dos lentes relevantes; recalcular al cambiar estado. Los enlaces son recomendaciones, no autorización ni ejecución.
5. Recuperar cualquier intento activo antes de crear otro. Usar [estado operativo](references/run-state.md) para reservar, adjuntar handle y reconciliar sin doble escritor. No abrir dos escritores sobre el mismo recurso. Si no hay subagentes nativos con contexto nuevo, declarar NOT_RUN; nunca lanzar otra instancia del agente.

## Bucle de entrega

- **Seleccionar** una tarea lista de valor, con AC y DoD, desde backlog-agile-workflow. Mantener un worker escritor por defecto; la reserva protege de escritores concurrentes, no impone un gate WIP al tablero.
- **Preparar** el brief mediante handoff de autoridad y context-pack; referencias a fuentes con revisión real, instrucciones mínimas, límites de alcance y resultado esperado. Validar envelope y resultado con [contratos operativos](references/contracts.md). Ver [composición](references/skill-composition.md) y [contexto](references/context-policy.md).
- **Delegar** con la herramienta nativa del host; pasar solo el brief, no la conversación. Fresh para nuevas tareas, resume para correcciones pequeñas si está disponible, sustitución tras confirmar parada y checkpoint. No delegación recursiva por defecto. Ver [delegación](references/delegation.md).
- **Supervisar** eventos relevantes del host; no sondear por shell ni releer transcripts. Si solo hay resultado síncrono, declarar esa limitación. Aplicar flow-recovery ante señales reales. Ver [supervisión](references/supervision.md); reducir eventos observados con [filtro compacto](references/event-supervision.md) cuando el host los exponga.
- **Verificar** evidencia de cada criterio, revisión, alcance y políticas de entrega. Si el riesgo lo requiere, usar goldfish-review con contexto nuevo y permisos de solo lectura. El worker devuelve READY_FOR_REVIEW, no PASS autoritativo.
- **Aceptar** mediante backlog-agile-workflow y su CLI/MCP, solamente con permisos reales, AC/DoD satisfechos y evidencia vinculada a la tarea. No imponer PR, rama main ni documentación ajena a las políticas observadas.
- **Aprender** mediante software-knowledge checkpoint/reconcile, guardar solo conocimiento duradero en su proveedor autorizado. No exigir enriquecimiento para cerrar una entrega.
- **Continuar** con un checkpoint compacto del supervisor. Liberar únicamente recursos propios confirmados y conservar trabajo parcial. Parar al alcanzar objetivo, límite, bloqueo real o petición humana.

## Invariantes

- Nunca crear otro tracker, base de conocimiento, scheduler, daemon o cliente externo de agentes.
- No ejecutar otra instancia de un agente, ni depender de PipelineK.
- Un handoff o una recomendación del router no otorga permisos.
- No afirmar aislamiento ni observabilidad no demostrados; las pruebas puras no certifican el host.
- Si falta una skill, declarar la capacidad degradada; no inventar equivalentes ni instalar automáticamente. La ausencia de conocimiento no bloquea trabajo técnicamente independiente autorizado.
- Ver [recuperación](references/recovery.md) para interrupciones y reconciliación.
