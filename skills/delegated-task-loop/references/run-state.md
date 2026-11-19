# Estado operativo privado

El helper run_state.py realiza reservas locales, identidad de run/intento, control optimista de versión, checkpoints por referencia y reemplazo seguro. No es Backlog ni ejecuta agentes. Solo POSIX (flock); si no está disponible, no declarar reserva atómica. No protege frente a otros programas que ignoren la reserva ni frente a varias máquinas.

Usar el binding estable registrado de software-knowledge (no basename) y el workspace real. Estado bajo XDG_STATE_HOME, con raíz privada y rechazo de checkouts. El directorio compartido agent-skills puede existir con permisos de lectura públicos, pero no admitir escritura de otros usuarios; la raíz de esta skill y el proyecto deben ser privados. JSON pequeño, escritura atómica y fsync; nunca transcripts, secretos ni contenido de código. La proyección vigente sustituye la anterior; Backlog conserva la historia de entregas. El journal no otorga permisos y no verifica el evento del host.

Interfaz: python3 scripts/run_state.py --binding BINDING --workspace WORKSPACE OPERACION; JSON por stdin salvo read. El resultado contiene state, authorized=false y runtimeVerified=false.

| Operación | Campos adicionales |
| --- | --- |
| read | ninguno, devuelve null si no hay run |
| start | maxTasks, maxAttempts, objectiveRef opcional; expectedVersion si termina un run previo |
| claim | taskId, briefRef |
| attach | attemptId, handle nativo |
| checkpoint | attemptId, checkpointRef |
| observe-stop | attemptId, observation (terminated/never-launched), observationRef |
| replace | attemptId, briefRef |
| release | attemptId, resultRef |
| supervisor-checkpoint | checkpointRef |
| finish | ninguno |

Todas excepto read/start requieren runId y expectedVersion observados. Cada mutación incrementa version; ante conflicto, releer y reconciliar, no reintentar una delegación automáticamente. claim consume una plaza de tarea; replace consume un intento de la misma tarea. Reservar la referencia privada de brief antes de claim y materializar/validar el envelope con el attemptId devuelto antes de delegar. Si se reanuda la misma conversación nativa después de una parada, reservar primero el nuevo intento vía replace, adjuntar el mismo handle solo si el host revalida su identidad y atribuir el resultado al nuevo intento (nunca reusar el resultado previo). Un intento reservado puede haber lanzado un worker antes de attach: en caso de caída, comprobar el host, no reutilizar ni expirar la reserva por tiempo.

Secuencia normal: start → claim → capacidad nativa fresh → attach → checkpoint(s) → confirmación de fin del host → observe-stop → verificación/resultado → release → supervisor-checkpoint. Agotar presupuesto o pausar no libera escritores activos. Reemplazar conserva referencia de checkpoint y requiere stop observado; reanudar mediante herramienta nativa únicamente si se puede comprobar identidad, permisos y que no hay escritor anterior. finish requiere ninguna reserva activa.

Los campos observationRef y resultRef contienen referencias observadas, no evidencias verificadas por este helper. La autoridad de cierre pertenece a Backlog, no al journal. Usar este mecanismo solo para proteger la concurrencia local propia de la skill; no imponer cupos WIP al tablero.

## Recursos desprendidos y Steward

Antes de replace/release, observe-resources {attemptId,resourceStatus clear/live/unknown,inventoryRef} registra inventario observado. mark-pending {attemptId,pendingRef} invalida inventario previo y mantiene la reserva. replace exige stop, checkpoint e inventario reconciliado; live exige adoptionRef y se conservan inventario, pendingRef y dominios. El siguiente brief v2 incorpora los recursos existentes; nunca relanzar operationKey. release exige clear incluso después de fin del worker, y acepta metricsRef opcional (null = desconocido). Para journals anteriores sin inventario, tratar como unknown y reconciliar; no borrar estado. Ver [adopción](resource-adoption.md).

claim admite effectDomains observados; sin ellos reserva '*', incompatible con cualquier Steward. claim-steward {briefRef,effectDomains,isolationObservationRef} reserva único agente auxiliar solo con ámbitos disjuntos; attach-steward {attemptId,handle}, observe-steward-stop {attemptId,observation terminated/never-launched,observationRef,resourcesClearedRef}, release-steward {attemptId,resultRef}. Todas requieren versiones CAS. finish no admite ninguna reserva. No confundir igualdad de strings con aislamiento: dominios canónicos incluyen raíz real y efectos indirectos (hooks, autoCommit, publicación), ver [Steward](steward.md). Si no hay separación comprobada, serializar gestión o usar CLI directa; este journal no certifica autorización.

La observación clear previa a attach/stop caduca: confirmar inventario nuevamente **después** de la parada antes de release o replace. El ref heredado conserva procedencia, no actualidad.
