# Observación por eventos: filtro antes del LLM

El supervisor usa únicamente las notificaciones o suscripciones nativas disponibles, o checkpoints naturales cuando el host sea síncrono. No hay daemon, hook global, sondeos periódicos ni ejecución de agentes mediante Python. Los hooks del host son una fuente opcional, no un canal de despertar garantizado.

En hosts instrumentados: el adaptador anfitrión normaliza hechos observados a un evento pequeño (identidad run/attempt/task/handle, seq contiguo por intento, kind, ref). No enviar argumentos, stdout, mensajes completos ni transcript. Solo la referencia recuperable. No inventar secuencias perdidas; reconciliar fuente si hay hueco. La proyección es rolling: conservar la última salida projection en estado privado fuera de Git y usarla como previous en la siguiente llamada. El helper no escribe. Serializar acceso desde el supervisor, no invocar múltiples reducers que sobrescriban la misma proyección.

```bash
python3 scripts/supervision.py < examples/supervision.json
```

Tipos: routine, operation-running, progress, new-hypothesis, error (fingerprint estable de error equivalente observado), active-without-progress (activeSeconds y operation healthy/waiting/none/unknown), question, scope-drift, context-pressure, budget-exhausted, result, terminal. Un hito es evidencia material, no un cambio de texto o latido. Un resultado o fin requiere reconciliar operaciones antes de liberar. No inferir contexto, presupuestos ni tiempo activo sin observación del host.

El reductor detecta dos errores equivalentes (reset con avance o hipótesis nueva); 20 minutos de trabajo activo observado sin avance y sin operación en curso producen stalled. Espera saludable/desconocida no es un bloqueo. El LLM recibe newAlerts solamente al aparecer una nueva señal; las pendientes se coalescen. Cada alerta guarda primera y última referencia/secuencia (lastRef/lastSeq); recuperar del origen el rango si hay varias preguntas o hechos distintos. Acknowledge por signal y lastSeq exacto únicamente después de decidir/registrar intervención; un evento posterior invalida el acuse antiguo. Al reconocer una alerta se recomienda atender la siguiente pendiente. Acknowledgement no suprime un problema futuro. El ciclo combina señal viva con el router existente. No cerrar tareas ni conceder permisos con esta salida.

Secuencia: observar evento → reducir → guardar projection → si wakeRecommended, recuperar evidencia pertinente y aplicar affordances/flow-recovery → decidir → reconocer alerta. Si hay pendientes al recuperar tras caída, atender signal aunque wakeRecommended sea falso. Las operaciones de host reales siguen siendo explícitas. El host decide cómo notificar un supervisor inactivo; si no puede, reportar capacidad result-only.

El filtro opera con hasta 64 eventos por lote y referencias de tamaño limitado, conserva solo cursor/último digest, último progreso, fingerprint/contador de fallo y un número acotado de alertas. Repetición exacta del último evento es idempotente; otros replays/huecos exigen reconciliación. No es un bus de eventos ni certifica la veracidad de inputs.

Señales adicionales pending, silence y resource-drift proceden de [liveness](telemetry.md) y reconciliación observada; no terminan reservas. Un heartbeat no demuestra avance material.
