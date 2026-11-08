> **Archivo histórico de diseño de esta skill.** No es una fuente de tracking ni una plantilla para proyectos consumidores. Tareas, prioridades, seguimiento y estado se gestionan únicamente mediante Backlog.md. Los gates o fases descritos aquí no son exigencias para ejecutar esta skill.

# Roadmap de backlog-agile-workflow

## S0 — Skill portable y navegación (entregado)

- `SKILL.md` autodetectable por intención y recurso `lens-registry.json` `ready/planned`.
- Lentes de descubrimiento, captura, triage, refinamiento, ejecución, cierre y mantenimiento.
- Router puro y parser puro de instantáneas oficiales JSON; no instala ni ejecuta Backlog.md.
- Convivencia declarativa con skills relacionadas, sin imports entre skills.
- Pruebas unitarias de navegación, idempotencia, límites y casos adversariales.

## S1 — Compatibilidad real de CLI (pendiente)

- Evals de agente sobre un proyecto temporal Backlog.md, **autorizado** y efímero, siguiendo CLI verificada localmente.
- Verificar configuración especial `--no-git`, directorios custom, estados y prioridades configurables, DoD y callbacks.
- Comparar versiones de CLI; registrar diferencias como restricciones de compatibilidad, no heurísticas inventadas.
- Mantener duración y dependencia de herramientas por debajo de lo que exige el valor, sin un CI adicional.

## S2 — Mejora de utilidad por conversación (pendiente)

- Medir selección incorrecta de lentes, carga de contexto, abstenciones correctas, elección de tarea con dependencias y falsos cierres.
- Adicionar lentes solo si aportan una pregunta distinta; retirar redundantes.
- Reutilizar selección/lectura cuando otras skills puedan hacerlo mediante protocolos simples, no un motor universal.

## Fuera de alcance

- Ejecutar tareas, modificar código de aplicaciones consumidoras, ejecutar un daemon o duplicar Backlog.md.
- Sincronizar automáticamente roadmaps, crear sprints ficticios o instalar un MCP sin consentimiento.
- Dar por `PASS` pruebas del proyecto por haber pasado tests del router.

## S3 — Proyección segura de ROADMAP/ADR/SPEC/hitos (entregado)

- Lentes `specification-intake`, `spec-decomposition`, `spec-reconciliation`, descubiertas por intención.
- Contrato efímero `spec-packet` con IDs canónicos, hitos, dependencias, gates, estado declarado, requisitos, ADR/SPEC, AC/DoD y prioridad propuesta.
- Proyector puro determinista: rechaza referencias inválidas/ciclos/duplicidades; preserva trabajo histórico; compara `task-list` existente y bloquea creación ante corpus incompleto o coincidencia sospechosa; nunca ejecuta la CLI.
- Tests de comportamiento sobre escenarios sintéticos, sin alterar proyectos consumidores.

### S4 — Futuras evaluaciones (pendiente)

- Evals de agente con documentos sintéticos extensos y mezclados (planes, históricos, receipts, contradicciones).
- Validar con una instalación temporal de Backlog.md el formato exacto de `references` y compatibilidad de versiones antes de automatizar propuestas de `--ref`.
- Medir falsos positivos de extracción, cantidad de preguntas necesarias y coste de navegación. No introducir indexador, base de datos secundaria ni sincronización automática como requisito.

## S5 — Privacidad Git e identificadores cruzados

- Detectar planificaciones y ZIP rastreados en índices de aplicaciones consumidoras; conservar bytes, reubicar/respaldar y proponer `.gitignore`/untracking, no ejecutar destrucción de forma automática.
- Escribir en commits IDs estables de tarea, bloque roadmap, ADR/SPEC existentes junto con implementación y evidencia; revisar historia antes de generar trabajo duplicado.
- Reconciliar tareas con historial mediante índice puro opcional. Ante implementaciones ya abordadas, pedir revisión, no crear una segunda tarea ni certificar DONE.
- Invocar especialistas por disponibilidad: testing, CI PipelineK, refactorización funcional y secretless.
- Probar con fixtures sintéticas sin modificar proyectos reales. La modalidad de Backlog.md con Git ignorado requiere plan de conservación/sincronización externa.

## S6 — Groma integrado como capacidad opcional

- Investigación de la integración oficial mediante `workSources.backlog`, `task list/view --json`, `--watch`, referencias y changed files.
- Lentes de arquitectura C4 y enlace de tareas, router con Groma opcional y Backlog independiente.
- Helper puro que preserva la lista completa `modifiedFiles` y referencias, incluidos los IDs sustituidos por combine/rename.
- Guard Git de OKF, config y ZIP/exportaciones privadas, con advertencias sobre la historia Git que se pierde al ignorarlos.
- Validación sintética del router, helper y clasificación; **pendiente** una prueba conjunta de ambas CLIs en un workspace autorizado y efímero. No reclamar compatibilidad completa de versiones, watch, modo --no-git o action de PR sin ella.

## S7 — CRUD Kanban completo y seguro

- Nuevas lentes de creación, transiciones y archivo/restauración; `delete` permanece como operación destructiva fuera del ciclo automático.
- Router de intención que distingue `create-task`, `move-task`, `archive-task`, `restore-task`, `delete-task` sin inventar estados ni archivar automáticamente al cerrar.
- Propuestas deterministas de argv mediante `board_crud.py`: preflight de configuración, validación de evidencia de Done, readiness para comenzar, idempotencia y revisión de dependencias de cancelaciones.
- Tests unitarios con fixtures sintéticas sin escribir tareas ni abrir el tablero TUI. Validar en entorno temporal autorizado con versión real de la CLI antes de afirmar compatibilidad end-to-end.
- Conservar el mismo contrato de tareas privadas fuera de Git y trazabilidad mediante IDs/SHAs en commits.

## S8 — Eventos Claude Code y recomendaciones oportunistas

- Plugin opcional `plugins/backlog-context` con normalizador de eventos, núcleo de recomendaciones TypeScript, `PostToolBatch` para agrupar lecturas, `PostToolUse` para registrar ediciones y recordatorio `Stop` único.
- Groma solo lectura `groma view` con límite de tiempo e IDs de propietario validados; Backlog no se invoca desde el hook debido a potenciales migraciones y efectos configurables.
- Estado acotado en `CLAUDE_PLUGIN_DATA`, aislado por sesión/proyecto/subagente, deduplicado y sin guardar fuentes/prompts.
- Lentes `work-alignment`, `unplanned-work`, `dependency-management` y `epic-management`; el agente autorizado aplica CLI real y gates.
- Pruebas unitarias sintéticas en Node 22 y pruebas de navegación existentes. Pendiente smoke manual contra Claude Code/Backlog/Groma instalados en un workspace temporal.
\n
## S9 — Trail of Authority y decisión nativa (entregado en rama de propuesta)

- Función pura `authority_context.py`: pins verificables por consistencia, contraste del mensaje humano, estado de Backlog y expiry/supersession. Sin permisos de ejecución.
- Lentes para decisiones Backlog, memoria del propietario y sustitución humana. Sin base de datos de decisiones paralela.

## S10 — Handoff y hooks contextuales (entregado en rama de propuesta)

- `context_handoff.py` prepara y recibe handoffs mínimos por tarea/SHA con comprobaciones fail-closed.
- `backlog-context` observa candidatos en UserPromptSubmit y recomienda contexto al compactar y entregar subagentes, sin almacenar prompts.
- `owner_memory.py` recupera hasta cinco referencias, integra votos consultivos sin mutar Backlog.
- `context_exchange.py` permite paquete offline solo de referencias, sin autenticidad criptográfica ni transporte entre equipos.

## S11 — Validación y evolución posterior

- Tests sintéticos adversariales en Python y Node forman parte de la CI existente.
- **Pendiente de observación externa:** smoke con agentes y CLI reales por versión, obtención autenticada de message IDs del anfitrión, latencias de recuperación y medición de investigaciones repetidas. Si el host no ofrece identidad verificable, conservar `UNVERIFIED`.
- Sin sincronización automática multi-máquina, sin transferencia de transcripciones, sin incremento de suites E2E permanentes.

## S13 — Lenguaje ubicuo, arquitectura emergente y OKF (primer slice implementado)

- Lentes contextuales para términos, etiquetado, investigación, arquitectura y consistencia.
- Snapshot efímero knowledge-corpus v1. Los documentos y glosarios siguen siendo nativos de Backlog; los scripts no ejecutan Backlog.
- Grafo determinista con validación de términos, contextos, duplicidades y relaciones; exportación OKF v0.2 solo bajo pedido, con index.md.
- Pruebas unitarias sintéticas para rechazos y no sobrescritura; los estados verified/generated no se inventan.
- Pendiente: smoke real de extracción CLI en entorno efímero, contraste con cambios de versión, migración semántica incremental y medición del coste de contexto.

## S14 — Límite de trabajo en curso (WIP) por política de proyecto

- Preflight en `board_crud.py` antes de iniciar una tarea o restaurar una tarea archivada directamente activa; crear tareas solo en estado por defecto.
- Política explícita `activeStatuses, maxPerAssignee, maxGlobal`; recomendación inicial 1 por responsable y 3 globales. Se cuenta trabajo sin asignar y coasignado.
- Instantánea nativa `task-list` sin filtros/paginación, `boardComplete` observado y comparación con tarea detallada; fail-closed ante ausencia, inconsistencia, duplicados o saturación.
- Salidas de WIP y cambios entre estados activos no consumen cupos nuevos. No marcar Done ni archivar sin pruebas para vaciar el tablero.
- Tests unitarios sobre el planificador y ejemplo sintético; pendiente garantía atómica interagente si Backlog.md expone en un futuro una primitiva de transición condicional.

## S15 — Goldfish nativo (código y contratos, ensayo de host pendiente)

- Skill independiente, nuevas intenciones, rúbricas y reportes estructurados, sin segunda fuente de verdad.
- Tests unitarios adversariales; faltan ensayos en vivo para verificar permisos e instrucciones heredadas del host.
- Detección diferencial de fingerprints es señal de revisión, no evidencia de drift semántico.
