# Política configurable de trabajo en curso (WIP)

## Regla y motivo

No iniciar trabajo adicional si ya se ha alcanzado el cupo. **Valor inicial recomendado, no universal:** máximo **1 tarea activa por responsable y 3 en total** por tablero; adaptar a la capacidad real y al número de agentes. Evitar arrancar cinco tareas para entregar ninguna. La política activa se confirma para cada proyecto y no sustituye sus columnas configuradas.

- Una tarea cuenta si su estado es uno de `activeStatuses`, aunque esté bloqueada informalmente. **Bloqueado** solo deja de consumir WIP si el proyecto tiene una columna real de espera y se mueve allí con explicación y seguimiento.
- Una tarea coasignada consume una plaza **para cada responsable**; sin responsable, consume el cupo compartido `<unassigned>`.
- Las tareas finalizadas y archivadas no ocupan cupo; no mover a Done ni archivar para inflar métricas. Un cambio entre columnas activas no crea una plaza nueva.
- Crear en `defaultStatus` y luego iniciar con preflight; una restauración a estado activo también debe cumplir el límite.
- Ante saturación: **acabar primero**, o pausar explícitamente trabajo legítimamente detenido con nota de causa/siguiente condición de reactivación. Para una urgencia, preemptar otra tarea o proponer cambiar temporalmente la política con aprobación humana y referencia; no bypass del guard.
- El límite debe alinearse con el universo visible: equipo/repositorio/proyecto y ramas/worktrees. `task list --json` filtrado o paginado no sirve para decidir la capacidad global.

## Entrada de la política en el planificador

`wipPolicy` es política explícita observada (no una opción nativa de Backlog.md):

```json
{
  "wipPolicy": {
    "activeStatuses": ["In Progress"],
    "maxGlobal": 3,
    "maxPerAssignee": 1
  },
  "boardComplete": true,
  "boardSnapshot": {
    "schemaVersion": 1,
    "kind": "task-list",
    "tasks": []
  }
}
```

Un agente obtiene `boardSnapshot` directamente desde `backlog task list --json` sin `--status`, `--assignee`, `--max-count` ni `--skip`. El array `tasks` debe contener `id`, `status`, `archived`, `assignees` como en el JSON oficial. `boardComplete: true` significa que el agente comprobó que el alcance y la visibilidad son suficientes; **no la deduce el script**. Si la salida tiene `total` o `nextSkip`, el guard rehúsa el preflight.

El `task` de una transición viene de `backlog task view <ID> --json`; `isReady=true` es obligatorio antes de entrar. El helper compara estado e identidad de ambas vistas y, si se aportan propietarios en la vista, también el propietario. Releer ambas inmediatamente antes de escribir y comprobar de nuevo después, porque **Backlog.md no reserva el cupo de forma transaccional**.

### Probar sin escribir

```bash
python3 scripts/board_crud.py examples/board-wip-start.json
```

El programa solo produce `AUTHORIZED_ACTION`, `PROPOSE_ONLY`, `BLOCKED` o `INSPECT_MORE` y los argumentos sugeridos cuando procede. No invoca CLI ni modifica tareas.

Si no existe `wipPolicy`, o el snapshot no es completo, se devuelve `INSPECT_MORE`, sin argumentos de escritura. Si se supera el límite devuelve `BLOCKED`. Para políticas con una o varias columnas activas se cuentan todas en conjunto; no hay forma de eludir el límite iniciando directamente en `Review`.

Las reglas de seguridad de configuración `autoCommit`, `onStatusChange`, permisos y los criterios AC/DoD se mantienen intactos. Una excepción autorizada exige revisar/modificar explícitamente la política del proyecto antes de volver a ejecutar el preflight, y documentar la motivación.
