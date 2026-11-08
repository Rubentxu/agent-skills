# Execution — implementar el siguiente incremento útil

1. Leer `backlog task view <id> --json` y las instrucciones de ejecución. Confirmar resultado esperado y dependencias **técnicas/funcionales reales**. No exigir un snapshot global del tablero para empezar a construir.
2. Implementar el slice más pequeño que aporte valor verificable. Si hay demasiado WIP, recomendar cerrar o pausar otras tareas, **no bloquear** por cupos ni preflights administrativos.
3. Registrar progreso relevante en la propia tarea con `--append-notes` cuando sea útil. No crear diarios, ROADMAP, CHANGELOG, recibos o ficheros adicionales de seguimiento.
4. Modificar implementación, tests focalizados y contratos públicos afectados. Evitar IDs administrativos o notas históricas en comentarios de código.
5. Si surge un bloqueo técnico, describirlo en Backlog.md y trabajar en su desbloqueo o continuar con una tarea independiente de valor. La ausencia de un gate, un ADR o una herramienta optativa **no es bloqueo**.
6. Usar especialistas cuando estén disponibles y aporten garantías/eficiencia, sin introducir ceremonias. Las herramientas de aplicación pertenecen al agente anfitrión.

**Salida:** comportamiento entregado, comprobaciones reales o `NOT_RUN`, riesgos técnicos y estado reflejado en Backlog.md. El commit puede vincular el ID de tarea, sin trailers documentales obligatorios.

**Groma y hooks:** solo si aclaran ownership o progreso. No exigir `groma view` ni actualización de `modifiedFiles` después de cada edición. Ningún hook de lectura ordena bloquear trabajo ni crea un Done automático.
