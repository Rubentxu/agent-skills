# Reconciliación excepcional de planificación legada

**Uso solo por solicitud expresa** para migrar/contrastar ROADMAP/SPEC/ADR heredados. No se invoca en creación, ejecución, verificación o cierre habitual.

1. Leer tareas, borradores, hitos y decisiones **nativos** de Backlog.md, evitando duplicados.
2. Si se aportaron documentos heredados, crear `spec-packet.json` **efímero** y utilizar `scripts/spec_projection.py` solo si el volumen lo justifica. No almacenarlo como tracking.
3. `NEEDS_CORPUS`, `INSPECT_STATUS` y otras salidas del proyector describen únicamente **esa migración**, no bloquean implementación técnica independiente.
4. Crear/actualizar tareas con la CLI autorizada, preservando AC, notas y estado. No convertir párrafos, recibos ni gates en tickets por rutina.
5. Tras migrar, Backlog.md se convierte en **fuente única**. No sincronizar permanentemente los documentos de origen ni exigirlos para cerrar tareas.
6. Si falta la CLI, informar de que el tablero no puede actualizarse; se puede seguir desarrollando o verificando código con permiso.

**Salida:** backlog nativo reconciliado, sin doble mantenimiento.
