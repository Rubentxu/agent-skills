# Review & Maintenance — mejora continua sin burocracia

1. Inspeccionar `backlog task list --json` completo y columnas configuradas; comparar WIP global y por responsable con los límites declarados, bloqueos, antigüedad visible y tareas listas, sin inventar velocity. Una tarea archivada/finalizada no consume WIP; las no asignadas cuentan en cupo compartido. Ver [política](../wip-policy.md).
2. Si hay documentación desfasada, priorizar contratos expuestos y decisiones de seguridad/replay antes de comentarios cosméticos; revisar solo el diff y los componentes de alto riesgo. Usar [code-documentation](code-documentation.md) y no abrir una tarea por cada línea de comentario.
3. Preguntar qué impidió entregar valor: tareas demasiado grandes, dependencias evitables, AC difusos, fallos repetidos o interrupciones. Elegir **una** mejora de flujo que pueda verificarse.
4. Repriorizar con autorización, registrar una decisión si cambia una política real. No reescribir todo el backlog ni regenerar ROADMAP.md automáticamente.
5. `backlog doctor` es lectura/diagnóstico; `backlog doctor --fix` puede reorganizar ficheros/IDs y requiere revisión expresa. No usar `backlog cleanup` en agentes no interactivos.
5. `backlog task archive <id>` conserva ID/historia y retira del board; solo por solicitud explícita. `backlog task delete <id>` es definitivo y afecta referencias: por defecto rechazar automatización y requerir confirmación específica.
7. `backlog board export` crea/sobrescribe ficheros según flags: confirmar destino antes de generar un informe.

**Salida:** 1 problema del proceso, 1 mejora, 1 señal futura para revisarla; mantener el resto `KEEP_AS_IS`.

**Archivo y restauración:** usar [board-archive-restore](board-archive-restore.md) para tareas Done, canceladas, duplicadas o inválidas. No marcar Done para sacarlas del tablero, no archivar automáticamente al cerrar y no borrar registros para simplificar métricas. Tras cualquier operación, comprobar el estado real vía CLI.
