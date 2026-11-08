# Execution — implementar el siguiente incremento útil

1. Leer `backlog task view <id> --json` y las instrucciones de ejecución. Confirmar resultado esperado y dependencias **técnicas/funcionales reales**. No exigir un snapshot global del tablero para empezar a construir.
2. Implementar el slice más pequeño que aporte valor verificable y cerrarlo tan pronto como cumpla sus AC/DoD técnicos. Si hay demasiado WIP, recomendar cerrar o pausar otras tareas, **no bloquear** por cupos ni preflights administrativos.
3. Registrar progreso relevante en la propia tarea con `--append-notes` cuando sea útil. No crear diarios, ROADMAP, CHANGELOG, recibos o ficheros adicionales de seguimiento.
4. Modificar implementación, tests focalizados y contratos públicos afectados. Evitar IDs administrativos o notas históricas en comentarios de código.
5. **Antiestancamiento activo:** después de dos intentos sin información nueva, un error recurrente o unos 20–30 minutos de trabajo activo sin avance verificable (cuando el tiempo sea conocido), activar [flow-recovery](flow-recovery.md), probar una hipótesis y decidir **en esa sesión**: cerrar, reducir el slice, desbloquear, crear un desbloqueante con valor independiente, repriorizar o escalar. No mantener una tarea durante horas en el mismo bucle. Una dependencia real se registra en Backlog.md; un gate o un ADR ausente **no** bloquea.
6. Usar especialistas cuando estén disponibles y aporten garantías/eficiencia, sin introducir ceremonias. Las herramientas de aplicación pertenecen al agente anfitrión.

**Salida:** comportamiento entregado y tarea cerrada cuando proceda; si no, causa observable, hipótesis probada, decisión de desbloqueo y próxima acción concreta reflejadas en Backlog.md. El commit puede vincular el ID de tarea, sin trailers documentales obligatorios.

**Groma y hooks:** solo si aclaran ownership o progreso. No exigir `groma view` ni actualización de `modifiedFiles` después de cada edición. Ningún hook de lectura ordena bloquear trabajo ni crea un Done automático.
