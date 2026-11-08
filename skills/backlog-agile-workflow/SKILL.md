---
name: backlog-agile-workflow
description: "Flujo value-first con Backlog.md como única autoridad de tareas. Prioriza incrementos verificados y desbloquear dependencias reales, sin ROADMAP/CHANGELOG paralelos, gates burocráticos ni WIP como freno. Pruebas y documentación de producto proporcionadas al riesgo."
---

# Backlog Agile Workflow — navegación contextual, no otro gestor de tareas

**Propósito:** ayudar a agentes y humanos a entregar valor en incrementos pequeños usando la CLI de [Backlog.md](https://github.com/MrLesk/Backlog.md); Backlog.md es el sistema de registro y su CLI la autoridad sobre tareas, identificadores, estados, dependencias y configuración. Esta skill es **portable** entre aplicaciones, repositorios y agentes. No añade servidor, daemon, motor de scheduling, base de datos, ni API de tareas alternativa.

## Principios obligatorios: valor antes que burocracia

1. **Entregar valor es la máxima prioridad:** completar incrementos funcionales pequeños y verificables. Minimizar el coste administrativo y no introducir ceremonias que retrasen el producto.
2. **Backlog.md es la única fuente de seguimiento:** tareas, planes, hitos, estados, decisiones, prioridades, dependencias, criterios de aceptación, progreso y evidencias se gestionan mediante su CLI/MCP oficial. **No promover, crear ni exigir** ROADMAP.md, CHANGELOG.md de progreso, otros Markdown de tareas, ADR/SPEC administrativos, recibos o informes de gates como tracking paralelo.
3. **Prohibidos los gates burocráticos:** no impedir iniciar, avanzar o cerrar una tarea por cupos WIP, snapshots globales, sincronizaciones documentales, comités o certificaciones administrativas. Si Backlog.md está temporalmente inaccesible, se puede continuar el trabajo técnico autorizado y registrar después el estado pendiente.
4. **Calidad demostrada en el producto:** comprobar AC, comportamiento observable, pruebas proporcionales al riesgo, seguridad, contratos y compatibilidad afectados. No declarar PASS sin ejecutar pruebas ni ignorar fallos relevantes. Permisos reales y requisitos técnicos/regulatorios de publicación se siguen respetando.
5. **Bloqueos solo por dependencias técnicas/funcionales reales:** eliminar aristas de orden, burocracia, gates o documentos. Si falta una capacidad necesaria, registrar el hecho en Backlog.md y desbloquearla o continuar con otra tarea independiente.
6. **Cierre ligero:** documentar en la propia tarea resultado, verificaciones reales y límites, marcar Done cuando se entregue el valor comprometido. No exigir ficheros ni recibos externos.
7. **Legado solo a petición:** las lentes de ROADMAP/ADR/SPEC sirven únicamente para migrar fuentes ya existentes si se solicita. Tras importar, no mantener doble seguimiento.
8. **Documentación técnica sí:** contratos de API, guías de usuario, decisiones técnicas y conocimiento duradero son producto cuando aportan valor propio. Para conocimiento de tareas, preferir decisiones y documentos nativos de Backlog.md.

## Contrato de arranque y descubrimiento

1. Determinar la **intención de la conversación** y etapa vigente: `discover|capture|triage|refine|plan|execute|verify|close|review|maintain|specify|decompose|sync-specs|document-code|git-hygiene|trace|architecture|curate-architecture|map-task|create-task|move-task|archive-task|restore-task|delete-task|align-work|unplanned-work|manage-dependencies|manage-epic|decide|authority-check|recall|handoff|memory-feedback|context-exchange|ubiquitous-language|semantic-tagging|okf-documentation|semantic-consistency|research-orchestration|emergent-architecture|independent-review|review-resolution|context-drift|catalog`. No arrastrar lentes de otra intención por inercia.
2. Verificar si `backlog` existe y qué proyecto está activo **sin instalar ni inicializar automáticamente**. Para tareas reales, leer primero `backlog instructions overview`; después solo `backlog instructions task-creation`, `task-execution` o `task-finalization` cuando correspondan. La ayuda local prevalece si difiere de la documentación empaquetada.
3. Si la CLI no está disponible, mostrar opciones de instalación para aprobación; `npx backlog.md ...` es una alternativa ocasional, **nunca** `npx backlog ...` (paquete distinto). Si no hay proyecto inicializado, proponer `backlog init` pero no ejecutar una configuración interactiva sin autorización.
4. Descubrir preferencias y límites del proyecto vía `backlog config get <clave>` cuando se conozca el comando y consultando la CLI actual; `statuses`, `defaultStatus`, `definition_of_done`, `projects`, `remoteOperations`, `autoCommit`, `bypassGitHooks`, `checkActiveBranches`, `onStatusChange`. No suponer columnas fijas ni que cerrar equivale a archivar.
5. Leer el estado **real** mediante `backlog task list --json`, `backlog task view <id> --json`, `backlog search ... --json`, `backlog milestone list --plain`; usar `schemaVersion` y `kind` para los parsers. `--watch` es una suscripción de larga duración, no una consulta puntual.
6. Seleccionar como máximo **dos lentes** desde `references/lens-registry.json` según intención y hechos disponibles. `scripts/affordances.py` es un router determinista y **sin acceso a la CLI ni a aplicaciones**; emite enlaces a recursos y recomendaciones, nunca ejecuta comandos. `scripts/spec_projection.py` compara un paquete explícito de especificaciones con una instantánea `task-list` sin mutar ninguno. `scripts/ready_candidates.py` valida una instantánea JSON **ya obtenida** y devuelve tareas listas sin mutarla ni consultar Backlog.md.
7. Si aparecen huecos, abrir solo la lente siguiente. Los handoffs a otras skills se ofrecen únicamente si el anfitrión confirma `available_skills`. No importar ficheros de otra skill.

## Autoridad humana y continuidad de contexto (Ghost Context)

- **Decisiones nativas:** preferir capacidades realmente anunciadas de `backlog decision list/create` y, cuando existan en la versión instalada, `view/edit` y `--superseded-by` para la autoridad de decisiones, con estado verificado y texto original enlazado mediante pin privado; un estado `accepted` sin fuente humana corroborada **no** basta. Consultar [decision-provenance](references/lenses/decision-provenance.md).
- **Origen:** `scripts/authority_context.py` compara registros con `decision-list --json` y mensajes originales aportados por un adaptador autorizado; `VERIFIED` solo expresa consistencia de snapshots, **no** autenticación independiente de JSON ni permiso de ejecución. Nunca inventar message ID, fecha, cita o aprobación.
- **Memoria selectiva:** `scripts/owner_memory.py` filtra decisiones relevantes (máximo cinco) por IDs de tarea y scope Groma, sin guardar prompts. [owner-memory](references/lenses/owner-memory.md).
- **Traspaso:** `scripts/context_handoff.py` empaqueta referencias y SHA, y el receptor los revalida. El handoff nunca es un permiso. [authority-handoff](references/lenses/authority-handoff.md).
- **Votos y portabilidad:** feedback de agente solo genera sugerencias de revisión; `scripts/context_exchange.py` exporta punteros, sin contenido, firma ni transporte automático. Revalidar siempre en destino. [feedback](references/lenses/memory-feedback.md) · [intercambio](references/lenses/context-exchange.md).
- No crear una base de datos, servidor ni vaciar transcripciones por defecto. Las decisiones son de Backlog, la propiedad del código de Groma y los permisos reales del host. Una skill no tiene capacidad para ampliar por sí sola autoridad humana o reglas organizativas.

## Revisión Goldfish propia y opcional

- Intenciones `independent-review`, `review-resolution` y `context-drift`: usar la lente apropiada (máximo dos) y delegar a `goldfish-review` solo si `available_skills` confirma la instalación y el host ofrece subagentes de contexto nuevo.
- El Elephant recupera términos, decisiones, tareas y código por las capacidades ya existentes. Goldfish recibe rúbrica, target y fuentes permitidas, **nunca la conversación del autor**. No añadir memoria, base de datos, tareas ni decisiones alternativas.
- El host controla permisos de solo lectura, revisión SHA y aislamiento conversacional. Instrucciones del proyecto pueden filtrarse por el host: documentar aislamiento parcial; sin subagentes nuevos, NOT_RUN. No interpretar resultados sintéticos como prueba del host.
- Resolver hallazgos con evidencia y KEEP_AS_IS; registrar conocimiento reusable mediante Backlog CLI, sin producir tickets por cada observación; usar WIP solo como consejo de foco, nunca como bloqueo. Fingerprint modificado solo indica candidato a drift.
- Ver [revisión independiente](references/lenses/independent-review.md), [resolución](references/lenses/review-resolution.md) y [drift](references/lenses/context-drift.md).

## Flujo ágil: valor, límites de WIP y evidencia

- **Desde la necesidad y Backlog.md:** elegir un incremento útil y administrarlo en el backlog nativo. Solo para **migración de legado solicitada** consultar [spec-packet](references/spec-contract.md) y [proyección](references/lenses/spec-reconciliation.md). Ninguna fuente externa conserva autoridad de seguimiento tras la importación.
- **Operar Kanban (CRUD real):** activar `create-task` para crear, `move-task` para cambiar columnas, `archive-task` para retirar del board y `restore-task` para recuperarla; `delete-task` obliga a mantenimiento humano independiente. Cargar solo la lente aplicable desde el [catálogo](references/lens-registry.json). El helper `scripts/board_crud.py` es optativo y prepara comandos, pero no crea gates administrativos obligatorios ni ejecuta Backlog.md. Done y Archive son conceptos distintos; una archivada inacabada continúa bloqueando sus dependientes.
- **Capturar:** buscar duplicados antes de crear. Ambigüedades → borrador (`backlog draft create`) o tarea con incertidumbre explícita, según aceptación; no convertir una idea vaga en veinte tareas especulativas.
- **Refinar:** una capacidad observable por tarea, criterios de aceptación verificables y pequeños, Definition of Done del proyecto; dependencias solamente si son bloqueantes reales. Si el cambio afecta a contratos de código, añadir aceptación documental proporcionada al impacto, sin crear tareas cosméticas por cada comentario. Registrar decisiones arquitectónicas como decisiones, no como pseudo-tareas.
- **Priorizar:** terminar entregas valiosas y desbloquear dependencias funcionales auténticas; `isReady` informa del grafo, no añade autorizaciones WIP o documentales. No inventar prioridades ni estimaciones.
- **Planificar justo antes de construir:** usar `backlog task edit <id> --plan ...` cuando reduzca incertidumbre real; no exigir plan para un cambio trivial. La implementación pertenece al agente anfitrión.
- **Eventos contextuales (Claude Code opt-in):** `plugins/backlog-context` observa lecturas/ediciones y recomienda el comando oportuno. Consulta **únicamente** propietarios con `groma view <file>` sin escanear ni escribir; una lectura no es modificación. Lentes portables: [work-alignment](references/lenses/work-alignment.md), [unplanned-work](references/lenses/unplanned-work.md), [dependency-management](references/lenses/dependency-management.md) y [epic-management](references/lenses/epic-management.md); ver [contrato de eventos](references/lenses/contextual-events.md). Hooks no autorizan automáticamente comandos ni deducen Done.
- **Groma.md opcional:** solo si el mapa aporta valor a la tarea, consultar `groma plugin list`, `groma agent-instructions backlog` y `groma view <archivo>` para localizar componentes C4 conocidos. Referencias `--add-ref` = alcance planificado; `--modified-file` = cambios realmente efectuados y **reemplaza toda la lista**. Conservar entradas previas y reconciliar IDs `replaced: A -> B` tras operaciones estructurales. El proyector puro [groma_task_links.py](scripts/groma_task_links.py) solo prepara argv revisables. Ver [integración](references/groma-integration.md). No hacer `scan`, `plugin add`, `web` ni edición OKF por una simple lectura.
- **Ejecutar:** actualizar junto al cambio las explicaciones de contratos públicos, invariantes y ejemplos afectados; evitar notas históricas, IDs administrativos o autoría personal en comentarios de producto. **Una tarea por flujo** por defecto; registrar notas con `--append-notes` (no reemplazar progreso existente), observar cambios y verificar el contrato mediante las herramientas autorizadas.
- **Verificar:** si cambia una API, comprobar la documentación frente a comportamiento real; no interpretar un generador sin errores como prueba de veracidad, ni añadir E2E a cambios solo documentales sin riesgo observable. Comprobar criterios de aceptación y DoD de **forma individual**, marcándolos solo tras evidencia real; tests `NOT_RUN` no equivalen a `PASS`. Delegar selección de pruebas a `delivery-first-testing` solo si disponible.
- **Cerrar sin ceremonias:** comprobar el producto y garantías pertinentes, resumir el resultado en `--final-summary` y marcar el estado final. No exigir recibos, gates administrativos ni documentos paralelos; archivar es independiente.
- **Revisar:** analizar bloqueos, exceso de WIP y tareas abandonadas; ajustar primero políticas y descomposición, no multiplicar reuniones ni burocracia.


## WIP: recomendación de enfoque, nunca bloqueo

Terminar antes de empezar es una buena práctica, **no un requisito de autorización**. La orientación de 1 tarea activa por responsable y 3 globales es ajustable y no crea un gate. No detener implementación ni declarar BLOCKED por cupo, falta de snapshot completo o ausencia de `wipPolicy`.

El control estricto de `scripts/board_crud.py` solo se usa si el equipo lo solicita expresamente; sus resultados describen ese modo opcional y no una prohibición nativa de Backlog.md. No falsear estados para mejorar métricas. Ver [WIP optativo](references/wip-policy.md).

## Contrato transversal de documentación de código (cualquier lenguaje)

**Regla:** el código explica cómo funciona; la documentación explica el contrato vigente y las decisiones no evidentes; el historial de desarrollo pertenece a Git y Backlog.md, no a comentarios de producción. Aplicar a cualquier stack, con el formato nativo del lenguaje, sin suponer Kotlin ni herramientas instaladas.

- **API pública:** documentar para sus consumidores propósito, restricciones, entradas/salidas no obvias, errores/refusals, efectos, concurrencia, seguridad y compatibilidad donde proceda. **Implementación:** comentar solo invariantes sorprendentes, razones actuales, límites de confianza y algoritmos difíciles; primero mejorar nombres y tipos. Eliminar comentarios triviales, desfasados, de migraciones o que contradigan código/tests.
- **Trazabilidad fuera del código:** tickets, issues, IDs de gestión, commits, nombres de solicitantes/autores y decisiones históricas van en Backlog.md, decisiones y trailers Git, no en docstrings, KDoc, Javadoc, rustdoc ni comentarios del producto. **Excepción:** identificadores de API y dominio (p. ej. `RunId`), códigos de error, estándares, vulnerabilidades o enlaces técnicos que el consumidor necesita; tampoco censurar la documentación de uso y sus usuarios finales.
- **Herramientas por stack:** KDoc/Dokka, Javadoc, Python docstrings, Rust rustdoc, Go doc, TSDoc/JSDoc, XML Docs y otras según archivos y build observados. Preferir checks/generadores existentes y minimizar coste y falsos positivos. La documentación pública de producto sí puede versionarse si el proyecto lo requiere: la política de gestión privada solo cubre documentos **de planificación**.
- **Cómo usarlo:** intención `document-code` → [lente de documentación](references/lenses/code-documentation.md) → [recetas por lenguaje](references/code-documentation-languages.md). Funciona sin Backlog.md instalado en modo guía. Esta skill no reescribe código ni archivos de tareas; cualquier edición requiere autorización del agente anfitrión. En refinamiento, ejecución, verificación y mantenimiento aplicar el mismo criterio al alcance real, sin imponer una limpieza global.

## Trazabilidad ligera, sin archivos paralelos

- **Flujo ordinario:** leer la tarea Backlog.md → implementar el slice → probar comportamiento y calidad pertinentes → registrar evidencia breve en la tarea → cerrar. No generar ROADMAP.md, CHANGELOG.md, ADR/SPEC de seguimiento, informes ni recibos administrativos.
- **Backlog.md es dueño de tareas y decisiones:** utilizar sus capacidades nativas. El almacenamiento/versionado Git o privado es elección del proyecto, no una política impuesta por esta skill.
- **Git conserva el código:** mensaje claro y enlace opcional al ID Backlog-Task, sin trailers obligatorios de roadmap, ADR, SPEC o Verification. Ver [trazabilidad mínima](references/commit-traceability.md).
- **Higiene no bloqueante:** el detector `git_artifact_guard.py` es optativo; ningún Markdown ni artefacto Backlog.md bloquea un commit por su nombre. Los riesgos de exposición de secretos sí merecen tratamiento real. Ver [higiene](references/repository-hygiene.md).
- **Especialistas optativos:** `delivery-first-testing`, `pipelinek-local-ci`, `pure-functional-design` y `agent-secretless` cuando ayuden, no como gates de gestión.
- **Protecciones reales:** mantener permisos del host, callbacks peligrosos, seguridad y comprobaciones regulatorias/técnicas obligatorias; no confundirlas con burocracia inventada.

## Políticas de seguridad, Git y concurrencia

- Las **lecturas** no autorizan **escrituras**; para init, config, create/edit/status, archivar, restaurar o eliminar se necesita intención explícita del usuario o permiso previo específico. Los scripts de esta skill no ejecutan comandos Backlog.md.
- No editar directamente Markdown/frontmatter de tareas, borradores, docs, decisiones ni milestones gestionados por Backlog.md; usar CLI/MCP oficial. Si el CLI rechaza un bloque legado sin marcadores, no sobrescribirlo manualmente; registrar que la actualización de tracking requiere reparación, sin detener por ello trabajo técnico independiente autorizado.
- `autoCommit=true` puede crear commits; `remoteOperations=true` puede consultar remotos; `bypassGitHooks=true` omite hooks; `onStatusChange` puede ejecutar shell. **Inspeccionar antes de modificar** y advertir si afectan a la operación. No cambiar la configuración silenciosamente. `checkActiveBranches` condiciona coste/visibilidad, no habilita estados inventados.
- Git tiene historia; el backlog puede tener estados diferentes en ramas/worktrees. No confiar en un ID ambiguo. `backlog doctor` es diagnóstico; `--fix` requiere autorización y revisión de cambios. Nunca usar `backlog task delete` o `backlog cleanup` automáticamente.
- Las subtareas son opcionales, no una métrica. Evitar tareas huérfanas y dependencias circulares. No crear nuevos estados o prioridades sin observar configuración real.
- `--notes` reemplaza el campo; preferir `--append-notes` para progresos. Las secuencias literales `\n` no se convierten en saltos: usar saltos reales o flags repetidas. Para mensajes de comentario, usar `--comment`; para cierre, `--final-summary`.
- En automatizaciones no interactivas, evitar `backlog config` sin argumentos, `backlog init` interactivo, `board`, `browser`, `cleanup`, editores y suscripciones `--watch` sin ciclo de vida controlado.

## Conocimiento semántico y arquitectura emergente

Backlog.md conserva tareas, documentos y decisiones como autoridad. Los glosarios por bounded context son documentos Backlog gestionados solo por CLI/MCP oficial. El grafo semántico es una proyección derivada y no sustituye Groma, Backlog ni la autoridad humana.

- [Lenguaje ubicuo](references/lenses/ubiquitous-language.md): IDs estables context.concept, definiciones, alias y ejemplos, sin imponer un vocabulario único entre contextos.
- [Etiquetado semántico](references/lenses/semantic-tagging.md): etiquetas ctx:context y term:context.concept en documentos de conocimiento; relaciones con predicado, destino y términos.
- [Google OKF v0.2](references/lenses/okf-documentation.md): exportación opt-in e interoperable, sin sobrescribir documentos de Backlog.
- [Consistencia y grafo](references/lenses/semantic-consistency.md): validador puro scripts/knowledge_graph.py sobre instantáneas explícitas.
- [Investigación dirigida](references/lenses/research-orchestration.md): hipótesis, evidencia, alternativas, costes y criterio de parada.
- [Arquitectura emergente](references/lenses/emergent-architecture.md): contratos, invariantes, seams reales y cambios reversibles.
- [Contrato de normalización y CLI](references/knowledge-contract.md): tipos nativos de documento limitados a readme, guide, specification y other. Usar tags kind:term, kind:research, kind:invariant, etc. No escribir frontmatter personalizado a mano.

## Enlaces bajo demanda

| Pregunta | Lente |
|---|---|
| ¿Hay Backlog.md y qué configuración es segura? | [discovery](references/lenses/discovery.md) |
| ¿Están los documentos o ZIP de gestión versionados? | [git-artifact-hygiene](references/lenses/git-artifact-hygiene.md) |
| ¿Cómo enlazar una tarea con su commit sin tracking paralelo? | [commit-traceability](references/lenses/commit-traceability.md) |
| ¿Qué componente posee el código y cómo afecta al mapa C4? | [groma-architecture](references/lenses/groma-architecture.md) |
| ¿Cómo mantener referencias y archivos de tareas en Groma? | [groma-task-linking](references/lenses/groma-task-linking.md) |
| ¿Cómo migrar planificación heredada si se solicita? | [specification-intake](references/lenses/specification-intake.md) |
| ¿Cómo priorizar hitos y descomponerlos en tareas útiles? | [spec-decomposition](references/lenses/spec-decomposition.md) |
| ¿Cómo conciliar especificaciones y tareas ya existentes? | [spec-reconciliation](references/lenses/spec-reconciliation.md) |
| ¿Cómo registrar ideas y evitar duplicados? | [capture](references/lenses/capture.md) |
| ¿Cómo crear una tarjeta nueva en el Kanban? | [board-create](references/lenses/board-create.md) |
| ¿Cómo mover a In Progress, Done o reabrir? | [board-transitions](references/lenses/board-transitions.md) |
| ¿Cómo archivar, restaurar y evitar borrado destructivo? | [board-archive-restore](references/lenses/board-archive-restore.md) |
| ¿Qué tarea aporta valor y está desbloqueada? | [triage](references/lenses/triage.md) |
| ¿Cómo documentar contratos y eliminar comentarios obsoletos en cualquier lenguaje? | [code-documentation](references/lenses/code-documentation.md) |
| ¿Cómo separar una capacidad en una tarea verificable? | [refinement](references/lenses/refinement.md) |
| ¿Cómo ejecutar un ciclo corto sin deriva? | [execution](references/lenses/execution.md) |
| ¿Cuándo marcar AC/DoD y finalizar? | [verification](references/lenses/verification.md) |
| ¿Qué mejorar del flujo y cómo limpiar? | [review-maintenance](references/lenses/review-maintenance.md) |

[Backlog.md + Groma.md, optativo](references/groma-integration.md) · [Higiene no bloqueante](references/repository-hygiene.md) · [Trazabilidad mínima](references/commit-traceability.md) · Navegación [HATEOAS-like](references/navigation.md) · [Comandos comprobados](references/cli-reference.md) · [Configuración avanzada y riesgos](references/configuration.md) · [integración con otras skills](references/skill-registry.json) · [fuentes](references/sources.md). El router nunca certifica una ejecución ni presume capacidades instaladas.

## Trazabilidad oportunista y seguridad de hooks

Un hook de lectura puede añadir al contexto IDs de propietario C4 observados, pero no crea componentes ni enlaza automáticamente la tarea. Una edición observada es candidato a `modifiedFiles`, que reemplaza el conjunto: conservar SIEMPRE la lista previa. Si se descubre trabajo nuevo, comprobar alcance/duplicados y proponer borrador o nueva tarea solo cuando tenga valor independiente. Nunca equiparar `TaskCreated` de Claude con registros Backlog.md. El plugin requiere Node >=22 y estado privado `CLAUDE_PLUGIN_DATA`; la skill sigue funcionando sin él.
