# WIP — recomendación de enfoque, nunca gate administrativo

**Objetivo:** favorecer terminar tareas y entregar valor. La orientación de **1 tarea activa por responsable y 3 globales** es configurable y no es requisito para iniciar, ejecutar o cerrar una tarea.

- Ante saturación, recomendar terminar un slice, reducir alcance o pausar trabajo realmente bloqueado. No exigir excepciones ceremoniales para continuar entregando.
- No falsear estados, archivar trabajo incompleto para ocultarlo ni marcar Done sin evidencia.
- Solo una **dependencia funcional o técnica genuina** puede impedir que una tarea se considere lista. WIP no crea dependencias ni convierte una tarea en BLOCKED.
- Para coordinar agentes, preferir tareas desacopladas y pequeñas. WIP orienta, **no autoriza**.
- Si un equipo **opta expresamente** por un control estricto, `scripts/board_crud.py` puede simular `wipPolicy` con `boardSnapshot` completo y `boardComplete=true`. `BLOCKED/INSPECT_MORE` describe **esa simulación optativa**, no una prohibición universal de la skill ni del CLI Backlog.md.
- Las transiciones reales se hacen por CLI con permisos adecuados. Protecciones ante comandos destructivos, callbacks y seguridad son independientes de WIP.

No obtener snapshots completos solo para comenzar trabajo ordinario. El helper nunca reserva cupos atómicamente.

## Ejemplo de control estricto, solo por petición

```json
{
  "wipPolicy": {"activeStatuses": ["In Progress"], "maxGlobal": 3, "maxPerAssignee": 1},
  "boardComplete": true,
  "boardSnapshot": {"schemaVersion": 1, "kind": "task-list", "tasks": []}
}
```

`python3 scripts/board_crud.py examples/board-wip-start.json` ilustra un modo opt-in y no forma parte del camino obligatorio de entrega.
