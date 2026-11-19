---
name: delegated-task-loop
description: "Coordina tareas Backlog.md mediante subagentes nativos, contexto mínimo, supervisión reactiva, evidencia y aprendizaje acumulativo. Úsala para delegar una secuencia acotada de tareas sin lanzar otros procesos del agente ni depender de PipelineK."
---

# Delegated Task Loop

El agente anfitrión es el supervisor Elephant. Una delegación, una tarea, contexto suficiente; el supervisor no implementa rutinariamente ni acumula conversaciones. Los workers son sustituibles; el conocimiento y la evidencia no.

## Entrada: observar antes de actuar

1. Fijar objetivo, alcance, autorización y límite de tareas/intentos. Aplicar [Endurance Relay](references/endurance-relay.md): nuevos runs start con relayPolicy="default", maxAttempts=2, objetivo de tarea <=60 min. Si se pide vaciar el tablero, acordar un límite de ejecución o detenerse al agotar el presupuesto del host; nunca interpretar autonomía como permiso ilimitado.
2. Descubrir capacidades reales de delegación fresca, background, notificación, intervención, cancelación y reanudación. No inferirlas por nombre del host. Consultar [hosts](references/host-capabilities.md); usar [canaries nativos](references/host-canaries.md) cuando falte evidencia de capacidades.
3. Descubrir las skills instaladas por el mecanismo del host. Localizar el Home Repo registrado mediante software-knowledge; Backlog.md es la única autoridad de trabajo. Leer las políticas AGENTS.md aplicables, incluidas las de cada repositorio afectado; descubrir delivery-first-testing para planes proporcionales.
4. Ejecutar el router puro con un objeto de estado observado: `python3 scripts/affordances.py -`. Ver [navegación](references/workflow-navigation.md). Leer como máximo dos lentes relevantes; recalcular al cambiar estado. Los enlaces son recomendaciones, no autorización ni ejecución.
5. Recuperar cualquier intento activo antes de crear otro. Usar [estado operativo](references/run-state.md) para reservar, adjuntar handle y reconciliar sin doble escritor. No abrir dos escritores sobre el mismo recurso. [Adoptar operaciones](references/resource-adoption.md) antes de sustituir o liberar. Si no hay subagentes nativos con contexto nuevo, declarar NOT_RUN; nunca lanzar otra instancia del agente.

## Bucle de entrega

- **Seleccionar** una tarea lista de valor, con AC y DoD, desde backlog-agile-workflow. Dimensionar por valor observable, dividir oversized cuando sea viable. Antes del claim confirmar anclajes y resolver dudas materiales con readiness técnica; mantener un trabajador escritor. Para investigaciones independientes y permisos probados, consultar [fan-out de lectura](references/parallel-read.md). La reserva protege de escritores concurrentes, no impone un gate WIP al tablero.
- **Preparar** el brief mediante handoff de autoridad y context-pack; referencias a fuentes con revisión real, instrucciones mínimas, límites de alcance y resultado esperado. Usar [Handoff Engineering](references/handoff-engineering.md): envelope v2 con políticas efectivas, hechos reutilizables, operaciones vivas y plan de pruebas de delivery-first-testing. Compilar con handoff_compiler.py y validar envelope y resultado con [contratos operativos](references/contracts.md). No ofrecer delegación hasta observar preflight preparado y recursos claros; el supervisor sigue siendo responsable de la claridad semántica. Ver [composición](references/skill-composition.md) y [contexto](references/context-policy.md).
- **Delegar** con la herramienta nativa del host; pasar solo el brief, no la conversación. Fresh para nuevas tareas, resume para correcciones pequeñas si está disponible; para relevo por presupuesto o contexto exigir fresh, nunca resume. Sustitución tras parada y checkpoint, baton validado y presupuesto restante. No delegación recursiva por defecto. Ver [delegación](references/delegation.md).
- **Supervisar** eventos relevantes del host; no sondear continuamente ni incorporar transcripts al contexto; usar [telemetría local](references/telemetry.md) en checkpoints autorizados. Usar pacing.py en eventos observados y transferir plazos del journal al brief. Preparar relevo a checkpointAt, reconciliar a deadlineAt. Si solo hay resultado síncrono, declarar que el límite es cooperativo. Aplicar flow-recovery ante señales reales. Ver [supervisión](references/supervision.md); reducir eventos observados con [filtro compacto](references/event-supervision.md) cuando el host los exponga.
- **Verificar** evidencia de cada criterio, revisión, alcance y políticas de entrega. Si el riesgo lo requiere, usar goldfish-review con contexto nuevo y permisos de solo lectura. Aplicar [verificación proporcional](references/proportional-verification.md), sin repetir suites; ejecutar solo el oráculo decisivo previsto y auditar alcance real. El worker devuelve READY_FOR_REVIEW, no PASS autoritativo; PENDING conserva reserva.
- **Aceptar** mediante backlog-agile-workflow y su CLI/MCP, solamente con permisos reales, AC/DoD satisfechos y evidencia vinculada a la tarea. No imponer PR, rama main ni documentación ajena a las políticas observadas.
- **Aprender** mediante software-knowledge checkpoint/reconcile, guardar solo conocimiento duradero en su proveedor autorizado. No exigir enriquecimiento para cerrar una entrega. Separar administración del implementador; delegar gestión breve solo con permisos/aislamiento comprobados, mediante [Steward](references/steward.md).
- **Continuar** con un checkpoint compacto del supervisor. Medir coste por intento si es observable, referenciar métrica en release. Liberar únicamente recursos propios confirmados y conservar trabajo parcial. Parar al alcanzar objetivo, límite, bloqueo real o petición humana.

## Invariantes

- Nunca crear otro tracker, base de conocimiento, scheduler, daemon o cliente externo de agentes.
- No ejecutar otra instancia de un agente, ni depender de PipelineK.
- Un handoff o una recomendación del router no otorga permisos.
- No afirmar aislamiento ni observabilidad no demostrados; las pruebas puras no certifican el host.
- Si falta una skill, declarar la capacidad degradada; no inventar equivalentes ni instalar automáticamente. La ausencia de conocimiento no bloquea trabajo técnicamente independiente autorizado.
- Ver [recuperación](references/recovery.md) para interrupciones y reconciliación.
