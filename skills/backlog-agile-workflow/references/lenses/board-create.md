# Kanban — crear tareas útiles con Backlog.md

1. Consultar `backlog instructions task-creation` y la configuración **relevante**. No convertir la creación en una auditoría global de ramas, documentos o commits.
2. Buscar duplicados razonables con `backlog search ... --json`; usar borrador para una idea incierta o `backlog task create` para un resultado observable.
3. Escribir criterios de aceptación verificables. Asignar prioridad, `--project`, referencias o `--dep` solo con valores/IDs reales y cuando aporten valor.
4. Crear en el estado inicial configurado y mover a activo al comenzar. **WIP no puede impedirlo** por falta de cupo o snapshot. Nunca exigir archivos ROADMAP, ADR, SPEC ni un Markdown paralelo.
5. Confirmar el ID devuelto y el resultado por CLI. No editar archivos gestionados por Backlog.md directamente, inventar IDs o activar efectos sin permiso.

**Salida:** tarea nativa y accionable, no un paquete documental.
