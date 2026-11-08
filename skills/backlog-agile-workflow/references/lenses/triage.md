# Triage — escoger trabajo que entrega valor

1. Leer tareas con `backlog task list --json` o `task list --ready --json`; confirmar IDs y estados reales por CLI cuando haga falta. No exigir inventarios globales por rutina.
2. Priorizar valor funcional, desbloqueo de otras tareas, urgencia y coste/riesgo técnico. Preferir finalizar trabajo empezado.
3. **WIP es recomendación**, no gate ni permiso. En caso de saturación, proponer foco sin declarar BLOCKED por cupo o falta de `boardSnapshot`.
4. Si `isReady` es falso, investigar la dependencia real; proponer retirar dependencias ficticias impuestas por orden, gate o documentación. No inventar que un ID desconocido equivale a dependencia satisfecha.
5. Capturar ideas inciertas como borrador nativo de Backlog.md, sin tickets cosméticos ni ficheros Markdown alternativos.

**Salida:** siguiente tarea valiosa y bloqueo técnico real, si lo hay.
