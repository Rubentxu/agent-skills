# Kanban — archivar y restaurar sin confundirlo con entrega

- **Done** es tarea verificada; **Archive** retira la tarjeta. No convertir archivo en requisito de cierre.
- Consultar `backlog task view <id> --json`; archivar solo con autorización y necesidad real de mantenimiento, no por rutina.
- Una tarea cancelada, duplicada u obsoleta puede archivarse sin falsear Done. Una dependencia sobre tarea archivada sin terminar sigue sin satisfacerse.
- Restaurar conserva ID y estado anterior. **No impedirlo por un WIP recomendado**: el helper estricto solo informa de capacidad cuando el proyecto lo ha elegido explícitamente.
- `backlog task delete` es destructivo y puede afectar referencias; requiere aprobación específica. `cleanup` no es un atajo automático.
- Revisar efectos reales de callbacks y Git; actualizar Backlog.md sin crear informes paralelos.

**Salida:** operación confirmada por CLI, historial y dependencias reales preservados.
