# backlog-agile-workflow

Skill portable para **trabajo ágil ligero** con [Backlog.md](https://github.com/MrLesk/Backlog.md). En vez de reimplementar tareas en scripts, usa la CLI oficial y selecciona una guía por problema. No requiere Scrum, sprints, servicio remoto ni integración MCP.

## Activaciones

- «Convierte mi ROADMAP, ADR, SPEC, hitos y gates en tareas priorizadas y trazables, sin duplicar trabajo»
- «Reconcilia cambios del roadmap con el tablero y respeta cierres ya certificados»
- «Convierte esta idea en tareas pequeñas y criterios de aceptación»
- «Prioriza lo que puedo implementar ahora, respetando dependencias»
- «Prepara un plan para la tarea actual, sin tocar código»
- «¿Está lista para cerrar? ¿Qué falta en su Definition of Done?»
- «Revisa bloqueos, WIP y trabajo obsoleto del backlog»
- «¿Cómo configuro Backlog.md en un proyecto local-first sin commits automáticos?»

## Contrato

1. **Lectura primero:** detectar la CLI, el proyecto y su configuración; `backlog instructions overview` es el primer manual operativo.
2. **Ruta bajo demanda:** seleccionar una o dos lentes; no cargar todos los documentos.
3. **Sugerir antes de escribir:** la skill distingue exploración, propuestas y ejecución autorizada.
4. **Un único propietario:** tareas/estados/IDs solo los escribe Backlog.md. Esta skill nunca toca archivos de trabajo ni crea su propio estado.
5. **Entrega verificable:** criterios de aceptación y DoD demostrados, no checkboxes optimistas. No modificar aplicaciones por el mero uso de la skill.

## Documentación de código en cualquier lenguaje

La [lente de documentación de código](references/lenses/code-documentation.md) separa contrato vigente, comentario interno y trazabilidad histórica. No presupone Kotlin: consulta las [recetas por lenguaje](references/code-documentation-languages.md) para KDoc/Dokka, Javadoc, Python docstrings, Rust rustdoc, Go doc, TSDoc/JSDoc, C# XML docs, Swift DocC, Dart y otros stacks. No crea tickets ni instala linters por defecto.

```bash
python3 skills/backlog-agile-workflow/scripts/affordances.py \\
  skills/backlog-agile-workflow/examples/code-documentation.json
```

Funciona sin Backlog.md instalado para orientar la revisión. Si la aplicación ya dispone de tareas, los cambios de API se reflejan en los AC/DoD vigentes y la procedencia queda en Backlog.md y trailers Git, **no** en los comentarios del producto. Los identificadores semánticos de protocolos y del dominio siguen documentándose cuando son parte del contrato.

## Proyección de especificaciones (sin escribir backlog)

[Contrato y reglas de trazabilidad](references/spec-contract.md) · [lente de documentación](references/lenses/specification-intake.md) · [descomposición](references/lenses/spec-decomposition.md) · [reconciliación](references/lenses/spec-reconciliation.md).

```bash
python3 skills/backlog-agile-workflow/scripts/spec_projection.py \
  skills/backlog-agile-workflow/examples/spec-packet.json \
  skills/backlog-agile-workflow/examples/spec-existing-tasks.json
```

El JSON resultante es solo un **plan revisable**; los comandos `backlog` se ejecutan después, con aprobación y a partir de la configuración real. Los documentos canónicos no se reescriben.

## Uso local (tests del router, sin Backlog.md instalado)

```bash
python3 skills/backlog-agile-workflow/scripts/affordances.py skills/backlog-agile-workflow/examples/triage.json
python3 skills/backlog-agile-workflow/scripts/ready_candidates.py skills/backlog-agile-workflow/examples/ready-list.json
python3 -m unittest discover -s skills/backlog-agile-workflow/tests -p 'test_*.py' -v
```

Instalación desde `Rubentxu/agent-skill` cuando esté publicada:

```bash
npx skills add Rubentxu/agent-skill --skill backlog-agile-workflow --agent opencode
```

La herramienta **Backlog.md** es un requisito separado para usar tareas reales. No se instala automáticamente. Tras instalarla y con un proyecto autorizado, empezar por `backlog instructions overview`. Para ejecución ocasional, `npx backlog.md <comando>`; `npx backlog` corresponde a otro paquete.

## Compatibilidad y límites

- Probado: selector, rutas internas, escenarios sintéticos. No se afirma haber ejecutado una CLI externa ni un proyecto real.
- Integraciones opcionales: `delivery-first-testing` (garantías), `pure-functional-design` (diseño/refactor), `cognicode-diagrams` (observaciones con sus restricciones). Sin acoplamiento de archivos.
- En backlog sin inicializar, la recomendación es preparación, no una ejecución de `init` en segundo plano.

## Gestión privada fuera de Git y trazabilidad

Por política del consumidor, ROADMAP, ADR, SPEC, documentos de Backlog.md y ZIP de gestión **no** se rastrean en el índice Git. Detectar primero con el [guard](references/repository-hygiene.md); `git rm --cached` preserva bytes pero requiere respaldo privado, sincronización colaborativa y consentimiento. Las fuentes de esta skill son artefactos distribuibles y **sí** se versionan.

```bash
python3 skills/backlog-agile-workflow/scripts/git_artifact_guard.py --repo . --check
python3 skills/backlog-agile-workflow/scripts/commit_trace.py commit-messages.json spec-packet.json
python3 skills/backlog-agile-workflow/scripts/spec_projection.py spec-packet.json task-list.json implementation-references.json
```

Los JSON son efímeros, se mantienen fuera del índice y no son una nueva base de datos. El índice de commits solo identifica trabajo posiblemente implementado; no confirma cierre. Ver [contrato de commit](references/commit-traceability.md).

## Especialistas recomendados cuando estén instalados

`delivery-first-testing` selecciona pruebas; `pipelinek-local-ci` gobierna gates locales si PipelineK es la CI del proyecto; `pure-functional-design` diagnostica arquitectura y refactors; `agent-secretless` ejecuta operaciones protegidas sin exponer credenciales. `backlog-agile-workflow` es dueño de las tareas, no de esos dominios.

## Integración opcional con Groma.md

[Guía detallada](references/groma-integration.md) · [lente C4](references/lenses/groma-architecture.md) · [lente de enlaces](references/lenses/groma-task-linking.md).

Groma lee tareas desde Backlog.md, y muestra sus referencias y archivos modificados sobre componentes del mapa C4. No necesita otra base de datos. Para activarla se verifica primero `groma plugin list` y las instrucciones oficiales `groma agent-instructions backlog`; `groma plugin add backlog` requiere permiso explícito.

```bash
groma plugin list
groma agent-instructions backlog
groma view --plain
groma view src/mi-archivo.rs
python3 skills/backlog-agile-workflow/scripts/groma_task_links.py \
  skills/backlog-agile-workflow/examples/groma-task-links.json
```

El helper solo propone argumentos, sin ejecutar comandos. El mapa inicial es evidencia de scanner, no diseño certificado. `groma scan` escribe OKF y `groma web` puede iniciar un servidor. Groma es opcional y Backlog.md continúa funcionando sin él.

**Privacidad:** OKF `groma/`/`.groma/` y exports fuera del índice Git del consumidor, con backup privado. Se pierden garantías de historia, action en PR y colaboración basada en OKF versionado. `groma export` puede incluir código fuente: nunca publicar por defecto. Rust dispone de scanner; Kotlin es experimental, sin fingerprints para detección de duplicaciones.

## Kanban CRUD — CLI completa, no solo planificación

Las lentes [crear tarjeta](references/lenses/board-create.md), [transicionar estado](references/lenses/board-transitions.md) y [archivar/restaurar](references/lenses/board-archive-restore.md) utilizan comandos oficiales; no editan Markdown de Backlog.md directamente.

```bash
# Leer tablero sin abrir TUI ni servicio web
backlog config get statuses
backlog task list --json
backlog task view TASK-7 --json

# Crear solo tras buscar coincidencias y revisar referencias
backlog task create "Título accionable" -d "Por qué hace falta" --ac "Resultado comprobable"
# Mover usando un estado real de la configuración
backlog task edit TASK-7 -s "In Progress"
# Archive no es Done: se realiza por separado
backlog task archive TASK-7
backlog task restore TASK-7
```

Comandos propuestos por el **planificador puro**, sin ejecutar Backlog.md:

```bash
python3 skills/backlog-agile-workflow/scripts/board_crud.py \
  skills/backlog-agile-workflow/examples/board-create.json
python3 skills/backlog-agile-workflow/scripts/board_crud.py \
  skills/backlog-agile-workflow/examples/board-transition.json
python3 skills/backlog-agile-workflow/scripts/board_crud.py \
  skills/backlog-agile-workflow/examples/board-archive.json
```

Los estados terminales, nombres de columnas, opciones de Git y callbacks deben observarse localmente. Los ejemplos son sintéticos. Los permisos no proceden del script: el agente debe confirmarlos antes de ejecutar la CLI real; después vuelve a leer la tarea y el board. La operación `delete` se bloquea por defecto, no es equivalente al archivo.

## Plugin contextual Claude Code opcional

`plugins/backlog-context` (véase el [README del plugin](https://github.com/Rubentxu/agent-skills/tree/main/plugins/backlog-context)) recuerda sincronizar tareas después de ediciones y aprovecha `groma view` para dar contexto arquitectónico al leer código, sin escanear, sin editar tareas y sin nuevos servidores. Para otros agentes las lentes de alineamiento, trabajo imprevisto, dependencias y jerarquías permanecen disponibles sin hooks.
\n
## Ghost Context: decisiones y traspasos

Las decisiones aprobadas son objetos **nativos de Backlog.md** (`backlog decision list/view/create/edit`, `--superseded-by`), no una segunda base de datos. Las referencias privadas a mensajes humanos incluyen origen, ID, fecha y digest, y solo se interpretan como autoridad tras contraste con el mensaje original. Las proyecciones ejecutables `scripts/authority_context.py`, `owner_memory.py`, `context_handoff.py` y `context_exchange.py` trabajan sobre JSON/snapshots obtenidos previamente y no invocan CLIs ni escriben el proyecto. Véanse [ADR-003](ADR-003.md), [ADR-004](ADR-004.md), [ADR-005](ADR-005.md) y las lentes de [procedencia](references/lenses/decision-provenance.md), [memoria](references/lenses/owner-memory.md) y [handoff](references/lenses/authority-handoff.md).

Los JSON son afirmaciones no autenticadas por sí solos: el host debe verificar identidad del mensaje y controlar permisos efectivos. Las pruebas unitarias no equivalen a un ensayo multiagente en vivo.

## Glosario, conocimiento semántico y OKF

Se incorporan [glosarios por contexto](references/lenses/ubiquitous-language.md), [etiquetado semántico](references/lenses/semantic-tagging.md), [investigación dirigida](references/lenses/research-orchestration.md), [arquitectura emergente](references/lenses/emergent-architecture.md) y [proyección OKF](references/lenses/okf-documentation.md).

Validador y grafo determinista: python3 scripts/knowledge_graph.py examples/knowledge-corpus.json --mode graph

Exportación opt-in a directorio nuevo: python3 scripts/knowledge_graph.py examples/knowledge-corpus.json --mode export --output /tmp/new-okf-bundle

El [contrato de datos](references/knowledge-contract.md) explica cómo normalizar lecturas CLI sin introducir una segunda autoridad.

## Límites de trabajo en curso (WIP)

[Política configurable](references/wip-policy.md) y verificación previa en `scripts/board_crud.py`. Valor inicial recomendado: **1 tarea activa por responsable y 3 en total** (incluidas coasignaciones, las no asignadas como cupo compartido); la política y las columnas se ajustan por proyecto. Ejecutar `python3 scripts/board_crud.py examples/board-wip-start.json` para consultar un ejemplo sin escribir tareas. El control necesita foto completa de `backlog task list --json`; **no** ofrece exclusión mutua transaccional entre agentes.
