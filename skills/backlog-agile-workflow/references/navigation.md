# Router conversacional y affordances

Entrada JSON para evaluación de **decisiones de la skill**, no un reflejo fiel de la CLI; todas las observaciones provienen del agente anfitrión y requieren corroboración.

```json
{
  "intent":"triage", "basis":"observed", "cli":"available", "project":"initialized",
  "mode":"read", "task":{"id":"TASK-4","isReady":true,"archived":false},
  "config":{"autoCommit":false,"remoteOperations":false,"bypassGitHooks":false,"onStatusChange":false},
  "available_skills":["delivery-first-testing"]
}
```

- `intent`: `discover|capture|triage|refine|plan|execute|verify|close|review|maintain|specify|decompose|sync-specs|document-code|git-hygiene|trace|architecture|curate-architecture|map-task|create-task|move-task|archive-task|restore-task|delete-task|align-work|unplanned-work|manage-dependencies|manage-epic|catalog`.
- `basis`: `observed|unknown|stale`; `observed` describe evidencias **declaradas**, el router no las verifica.
- `cli`: `available|missing|unknown`; `project`: `initialized|absent|unknown`.
- `mode`: `read|propose|apply` (default `read`). `apply` representa autorización declarada por el llamante, **no ejecuta nada**.
- `task`: `id`, `isReady`, `archived`, `status`, `acceptanceCriteriaCount`, `acceptanceCriteriaCompleted`, `definitionOfDoneCount`, `definitionOfDoneCompleted`, todos opcionales salvo lo que cada fase exige. No adivinar lo no observado.
- `config`: `autoCommit|remoteOperations|bypassGitHooks|onStatusChange`; bool o `null` (desconocido). Otras claves y estados configurables son responsabilidad de la CLI.
- `available_skills`: solo inventario de habilidades confirmado por el anfitrión.

Orden de decisión: validar entrada → resolver capacidades/proyecto → escoger lente → evaluar lectura/propuesta/escritura → riesgos Git/estado → emitir enlaces. Los enlaces a lentes existen dentro de la skill. Para seleccionar candidatos en una instantánea JSON `task-list` ya descargada, usar el helper `ready_candidates.py`: preserva el orden de la CLI, no inventa prioridad y advierte cuando la instantánea puede estar filtrada o paginada. Para la CLI, el router anuncia **comandos de lectura orientativos**, sin ejecutarlos ni construir cadenas de shell a partir de datos del usuario.

Resultados: `DISCOVER`, `INSPECT_MORE`, `READY`, `PROPOSE_ONLY`, `AUTHORIZED_ACTION`, `KEEP_AS_IS`, `BLOCKED`. Ninguno significa `PASS` de tests ni que se haya escrito una tarea. Los cambios de fase y objetivo se reevalúan; no se conserva un estado de conversación en archivos.

## Importación excepcional de planificación heredada

`specify` y `sync-specs` solo se usan ante una migración expresamente solicitada de fuentes antiguas; `decompose` puede organizar hitos nativos de Backlog.md sin roadmap externo. El proyector de legado solo emite propuestas, nunca sustituye la autoridad de Backlog.md ni impide entregas ordinarias. Ver [contrato](spec-contract.md).

## Documentación de código transversal (sin CLI)

`document-code` selecciona [code-documentation](lenses/code-documentation.md) sin requerir Backlog.md, Groma ni conexión de red. El router devuelve **orientaciones**, nunca edita un archivo, no ejecuta linters ni crea tareas. Distinguir documentación de producto versionable de ADR/roadmaps y material privado de gestión. Si hay Backlog.md, el agente puede vincular esta revisión a AC/DoD **reales** mediante la CLI autorizada; no abrir tickets por cada KDoc o comentario. La [tabla por lenguaje](code-documentation-languages.md) es opt-in y solo se consulta tras detectar el stack.

## Auditoría y trazabilidad sin CLI

`git-hygiene` enlaza únicamente a la auditoría de índice y no requiere Backlog.md instalado. `trace` enlaza el índice de identidades documentales/commits, igualmente sin escribir ni necesitar Backlog.md. El `mode=apply` de estas consultas no autoriza sacar archivos del índice ni hacer commits; requieren consentimiento de operación específico. Handoffs solo hacia IDs presentes en `available_skills`.

## Groma.md opcional

`groma` acepta `available|missing|unknown` y no se deduce de `cli` de Backlog.md. `architecture` y `curate-architecture` pueden inspeccionar el mapa aun sin backlog; `map-task` exige ambos programas y un ID de tarea observado. Si Groma falta, solo propone descubrir la instalación, sin degradar las operaciones Backlog.md. Las operaciones `groma scan`, `web`, `plugin add` y edición OKF no son lecturas y requieren autorización específica. En el ciclo `plan|execute|verify` se ofrece una navegación Groma solo cuando `groma=available`, sin añadir más lentes obligatorias. Ver [integración](groma-integration.md).

## Kanban CRUD operativo

Los intents `create-task`, `move-task`, `archive-task`, `restore-task` y `delete-task` seleccionan una lente **sin cargar el resto**. `move-task` necesita un ID real; archivar/restaurar necesitan además `archived` observado. `delete-task` bloquea toda automatización normal por el riesgo de reutilizar IDs y alterar dependencias. Las opciones `mode=apply` en navegación **siguen siendo solo propuestas**; para generar un argv de escritura con evidencias concretas se usa `scripts/board_crud.py`, que también es puro y no ejecuta la CLI. El agente verifica el resultado después de cada operación, sin usar el tablero interactivo como API.

## Recomendaciones contextuales

`align-work` propone reconciliar tareas y cambios reales sin certificar Done; `unplanned-work` clasifica hallazgos no planificados; `manage-dependencies` exige ID real y verifica bloqueos; `manage-epic` elige milestone, padre o tarea independiente sin jerarquía artificial. El plugin opcional `plugins/backlog-context` proporciona observaciones de Claude Code y Groma sin alterar Backlog ni ejecutar escaneos. Ver [contextual-events](lenses/contextual-events.md).

## Navegación semántica

Las intenciones ubiquitous-language, semantic-tagging, okf-documentation, semantic-consistency, research-orchestration y emergent-architecture consultan el contrato knowledge-contract.md y una lente propia. Solo ubiquitous-language y semantic-tagging se consideran candidatas a escrituras CLI autorizadas. El resto analiza o proyecta archivos fuera de Backlog. No se exige Groma para el glosario; las lecturas doc list se sugieren solo si la CLI está presente.

## WIP opcional

Para una transición ordinaria, basta observar la tarea, estado válido, permisos y dependencias técnicas reales. No exigir snapshot completo ni un control de cupo. Solo si el equipo **solicita explícitamente** el modo estricto, `board_crud.py` evalúa [WIP](wip-policy.md) y puede devolver BLOCKED/INSPECT_MORE sobre **esa simulación optativa**; jamás se convierte en gate general de implementación.

## Intenciones de revisión independiente

`independent-review`, `review-resolution` y `context-drift` funcionan para lectura sin CLI. Solo recomiendan `goldfish-review` cuando está instalada; no ejecutan subagentes, no escriben Backlog y `mode=apply` no concede autoridad. Ver [guía](lenses/independent-review.md).
