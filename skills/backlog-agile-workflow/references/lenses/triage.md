# Triage — escoger trabajo que entrega valor

1. Leer tareas con `backlog task list --json` o `task list --ready --json`; confirmar IDs y estados reales por CLI cuando haga falta. No exigir inventarios globales por rutina.
2. Priorizar valor funcional, desbloqueo de otras tareas, urgencia y coste/riesgo técnico. **Primero comprobar si alguna tarea activa ya puede cerrarse.** Preferir terminar trabajo comenzado y los desbloqueantes con mayor impacto.
3. **WIP es recomendación**, no gate ni permiso. En caso de saturación, proponer foco sin declarar BLOCKED por cupo o falta de `boardSnapshot`.
4. Si `isReady` es falso, investigar la dependencia real; proponer retirar dependencias ficticias impuestas por orden, gate o documentación. No inventar que un ID desconocido equivale a dependencia satisfecha.
5. Si una tarea acumula dos intentos estériles o una sesión activa prolongada sin progreso observable, activar [flow-recovery](flow-recovery.md) **antes de volver a elegir el mismo enfoque**. Comparar terminar slice, resolver dependencia, crear tarea desbloqueante independiente o repriorizar otra tarea lista; ejecutar la decisión, no solo generar un plan.
6. Capturar ideas inciertas como borrador nativo de Backlog.md, sin tickets cosméticos ni ficheros Markdown alternativos.

**Salida:** siguiente tarea valiosa y bloqueo técnico real, si lo hay.
