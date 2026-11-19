# Evaluaciones de comportamiento

Los unit tests prueban router, estado operativo, contratos y proyección de observaciones. No certifican ejecuciones LLM. Canaries a ejecutar en cada host real antes de afirmar soporte:

| Caso | Criterio observable |
| --- | --- |
| Fresh worker | Handle nativo, sin historial del supervisor; no nuevo proceso lanzado por la skill |
| Sin delegación | NOT_RUN, ningún fallback headless |
| Contexto acotado | Medir bytes/tokens transferidos por rol, sin transcripts |
| Bloqueo | Dos intentos estériles disparan flow-recovery; no sondeos |
| Evento activo | Notificación real, steering solo si disponible |
| Interrupción | No segundo escritor; checkpoint y reconciliación |
| Goldfish | Contexto nuevo, permisos de lectura efectivos; NOT_RUN si no disponibles |
| Cierre | Evidencia vinculada a tarea y revisión; AC/DoD individuales |
| Conocimiento | Referencias y reconciliación mediante proveedor, no memoria duplicada |
| Supervisor largo | Proyección acotada entre tareas, compactación real medida si disponible |

Comparar tres estrategias en tareas emparejadas, revisiones iniciales y presupuesto equivalentes: agente único, supervised-task-loop, delegated-task-loop. Medir tokens totales incluidos revisores y supervisor (UNKNOWN si no medible), tareas aceptadas, latencia, reaperturas, defectos confirmados, lecturas redundantes, tiempo de recuperación y recursos huérfanos. No extrapolar desde fixtures. No guardar transcripts por defecto. Estado inicial de canaries: NOT_RUN.

Protocolo reproducible: [canaries nativos](../references/host-canaries.md). No convertir fixtures de host_probe en ejecuciones reales.

Ejecutar [evaluación por pares](../references/evaluation.md) con revisiones y tareas idénticas. El validador de fixtures no mide productividad ni ejecuta agentes; el ejemplo se mantiene not-evaluated.

Fan-out: comprobar que el host permite dos lectores frescos realmente restringidos a snapshots inmutables, notificaciones atribuidas y límites agregados. No validar lectores mediante instrucciones únicamente. Los escritores permanecen serializados. [Contrato de fan-out](../references/parallel-read.md).

Evaluar brief v2 (anclas ausentes, dudas, políticas, delta antiguo), PENDING/adopción, Steward disjunto/capacidad no confirmada, selector proporcional y evidencia obsoleta. Canaries: interrupción durante integración real, adopción sin duplicar, tiempo hasta primer cambio y coste de contexto. Ver [telemetría](../references/telemetry.md), [alcance](../references/proportional-verification.md). Fixture no equivale a prueba de host.

Canarios OS reales en test_operational_canaries.py: operación que sobrevive a worker, reserva concurrente CAS y publicación inesperada a remoto bare desechable. No son ejecuciones de LLM ni certificación de aislamiento nativo.
