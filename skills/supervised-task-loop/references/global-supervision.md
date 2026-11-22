# Supervisión interoperable por demanda

El bucle de esta skill conserva una tarea por sesión y contexto limpio. No es autoridad global exclusiva ni debe reclamar una segunda copia del tablero. Cuando el `available_skills` del host incluye `backlog-agile-workflow`, abrir la lente `inspect-stalled`: `multi_agent_cli.py triage` detecta tareas con lease vencido, sin progreso real, solicitudes de yield y cuarentena mediante comentarios nativos de Backlog.

Cada revisión es puntual, sin nuevo daemon. Varios supervisores pueden leer simultáneamente; toda escritura necesita un claim/generación verificados y publicación Git CAS. Si aparece `SUSPECT`, no reiniciar automáticamente otro proceso: solicitar cesión si el host responde, o cuarentena y observación de recursos. `QUARANTINED` conserva sus recursos hasta prueba de parada/adopción.

No mezclar la métrica de sesión (llamadas, compaction, CPU) con progreso material de tarea ni declarar que un timeout demuestra parada. Regresar a [fallos](04-failure-modes.md) y [medición](03-measurement.md) cuando proceda, sin leer todos los documentos por defecto.
