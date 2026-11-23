---
name: pipelinek-local-ci
description: "Diseña y ejecuta automatizaciones CI, testing progresivo, gates, certificaciones y métricas locales con PipelineK. Descubre firmas de DSL y workflows reales, gestiona evidencias y secretos seguros sin depender de plataformas CI remotas. Úsala para discover, bootstrap, scaffold, review, plan, run, diagnose, evidence, certify, automate o metrics."
metadata:
  version: "2.1.0"
---

# PipelineK local CI — agent-first

PipelineK debe convertirse en la **autoridad local ejecutable** de CI del repositorio. No traduzcas YAML/Groovy mecánicamente y no inventes DSL.

> Esta skill es un router. Carga sólo la referencia necesaria para el modo actual.

## Modos

| Modo | Cuándo | Referencias |
|---|---|---|
| `bootstrap` | PipelineK no está instalado, hay conflicto mise/asdf o hay que fijar versión | `04-version-resolution.md` |
| `scaffold` | Crear o ampliar `pipeline.kts` | `00-decision-tree.md`, `01-pipeline-authoring.md`, `06-jenkins-familiar-dsl.md` |
| `review` | Auditar pipeline existente | `01-pipeline-authoring.md`, `06-jenkins-familiar-dsl.md`, `08-review-checklist.md` |
| `run` | Usar PipelineK como gate del trabajo del agente | `02-agentic-loop.md`, `05-events-and-troubleshooting.md` |
| `migrate` | Sustituir Jenkins/GitHub Actions/GitLab CI | `03-migration-hosted-ci.md`, `06-jenkins-familiar-dsl.md` |
| `diagnose` | Fallo de DSL, ejecución, toolchain, shim o evento | `04-version-resolution.md`, `05-events-and-troubleshooting.md` |
| `publish` | Ejecutar packaging y publicación por canal de productos confirmados | `09-artifact-publishing.md`, y `distribution-first-release` si está disponible |
| `discover` | Encontrar workflows del repo y consultar firmas exactas disponibles | `10-dsl-discovery.md`, `11-project-automation-layout.md` |
| `plan` | Elegir checks afectados por un cambio sin falsear cobertura | `12-progressive-verification.md` |
| `evidence` | Validar procedencia, alcance y frescura del resultado de un worker | `13-evidence-contract.md` |
| `certify` | Certificar artefacto/consumidor con evidencia independiente | `13-evidence-contract.md`, `09-artifact-publishing.md` |
| `automate` | Promover un procedimiento recurrente a workflow reproducible | `11-project-automation-layout.md`, `12-progressive-verification.md` |
| `metrics` | Capturar recursos iniciales y comparar duración de fases/steps en un dashboard HTML offline | `14-local-metrics.md` |

Si el usuario no nombra modo, infiérelo por intención. Una adopción desde cero normalmente ejecuta `bootstrap → scaffold → run`.

## No negociables

1. **Identidad exacta.** Antes de acreditar CI conoce `command → realpath → pipelinek version`. Si se pidió `V` y runtime reporta otra versión, es `IDENTITY_MISMATCH`.
2. **Cero comandos ficticios.** Nunca generes `project-wrapper`, `run-tests-here` ni placeholders ejecutables. Detecta comandos reales del repo.
3. **Proyecto primero.** Prefiere `./gradlew`, `./mvnw`, scripts de `package.json`, `uv`, `cargo`, `go`, `make` o `just` realmente presentes.
4. **DSL observada.** Descubre la composición instalada con `pipelinek steps --json`, `pipelinek describe` y `pipelinek capabilities`. Para scripts no confiables, utiliza `pipelinek validate --compile-only`; `validate` sin esa opción evalúa el cuerpo del script. Solo valida funcionalmente código autorizado y confiable. Ver `10-dsl-discovery.md`.
5. **Fallos visibles.** No añadas `|| true`, `--quiet`, `/dev/null` ni redirecciones que oculten el comando causal. Si usas `tee`, conserva el exit con `pipefail`.
6. **Estado fuera del repo.** Journal/control-root bajo XDG state salvo política explícita; identifica repositorio y worktree, nunca solamente `basename` en entornos con clones homónimos.
7. **Sin dependencia remota.** El CI, gates, certificaciones y reportes funcionan offline con dependencias locales fijadas. No crear GitHub Actions ni servicios remotos de CI como prerrequisito. El sistema de build y los pipelines del proyecto son la única autoridad de sus verificaciones.
8. **No rebajar gates para obtener verde.** Clasifica el fallo y corrige causa o contrato.
9. **Distribución opcional.** `pipelinek-local-ci` ejecuta gates; `distribution-first-release` decide productos y destinos si aplica. `archiveArtifacts` guarda artefactos locales y no acredita publicación externa. Ningún canal remoto es requisito de automatización local.
10. **Credenciales no se imprimen.** Usa bindings soportados; para runs durables con secretos exige `PIPELINE_CREDENTIALS_MASKING=required`, sin permitir `best-effort` en CI/certificación. Esa política rechaza secretos demasiado cortos, pero no garantiza seguridad frente a cualquier proceso malicioso. Consulta `07-security.md`.
11. **Jenkins-familiar ≠ Jenkins mágico.** Mantén nombres/patrones familiares donde tengan semántica real; fail-closed para lo aún no soportado.

## Flujo por defecto

### 1. Inspeccionar

Lee `AGENTS.md`, build manifests, wrappers, lockfiles, scripts, CI existente y `pipeline.kts`. Detecta stack con `00-decision-tree.md`.

### 2. Bootstrap si hace falta

Si PipelineK falta o la resolución es ambigua, usa `04-version-resolution.md`. En modo bootstrap la instalación **sí está dentro de scope**: prefiere pin por proyecto; no cambies globales salvo petición explícita.

### 3. Diseñar o revisar

Descubre primero los pipelines existentes en `pipeline.kts` y `pipelines/**/*.pipeline.kts`; no crea otro si ya hay un entrypoint autoritativo. Construye stages por responsabilidad observable: validate/static → build → unit/contract → integration/UAT → package. Usa templates de `examples/` sólo después de comprobar que sus comandos existen en el repo.

### 4. Validar DSL

```bash
pipelinek validate --compile-only pipeline.kts
```

La compilación no certifica efectos ni políticas de runtime. Ejecuta `pipelinek validate pipeline.kts` sin `--compile-only` solo en un entorno confiable y autorizado; después exige un run real y un negativo discriminante cuando corresponda. Una feature no soportada se rediseña, no se simula.

### 5. Ejecutar como gate agentic

Usa `02-agentic-loop.md` y `12-progressive-verification.md`: inspecciona cambios staged/unstaged/untracked, selecciona pruebas afectadas y expande conservadoramente cuando no puedas demostrar cobertura. Las ejecuciones filtradas son SUBSET, jamás un PASS global. Pipeline completa solamente en la frontera que establezca la política de cada repositorio.

### 6. Publicar cuando el objetivo sea distribución

Usa [`09-artifact-publishing.md`](references/09-artifact-publishing.md): identifica los productos mediante `distribution-first-release`, valida rutas/tareas reales, ejecuta gates una sola vez, solicita autorización para subir y verifica cada producto desde el canal remoto. No crea automáticamente Actions ni declarará DONE desde un `archiveArtifacts` local.

### 7. Cerrar con evidencia

Reporta: HEAD, path real de PipelineK, versión, pipeline, comando, exit, `RunFinished.outcome`, primer fallo causal, stages realmente ejecutados y skips/bloqueos.

## Definition of Done

- [ ] No quedan placeholders ejecutables ni comandos inventados.
- [ ] PipelineK resuelto y versión exacta verificada.
- [ ] La DSL compila con la instalación seleccionada y cualquier evaluación del script fue explícitamente autorizada.
- [ ] Existe al menos un run positivo real.
- [ ] Si se creó/migró pipeline, existe un negativo discriminante que falla donde debe.
- [ ] Los comandos de build/test proceden del proyecto, no de memoria.
- [ ] Los eventos/outcome y exit no se contradicen; si lo hacen, queda reportado.
- [ ] No se dejó estado operativo dentro del repo sin política explícita.
- [ ] El workflow funciona en local sin servicio remoto obligatorio; cualquier dependencia externa está declarada y autorizada.
- [ ] La superficie Jenkins-familiar usada figura como soportada o fue validada explícitamente.
- [ ] Si hubo `publish`, solo se acredita lo realmente publicado en los destinos autorizados, sin dar PASS a entregas pendientes.

## Automatizaciones reutilizables

La convención de carpetas y el alcance de cada perfil están en [layout](references/11-project-automation-layout.md). Consulta [firmas y directivas](references/10-dsl-discovery.md) antes de autorar DSL, y [testing progresivo](references/12-progressive-verification.md) antes de ejecutar. El formato de [evidencia](references/13-evidence-contract.md) distingue una prueba local de certificación de un artefacto. [Las métricas](references/14-local-metrics.md) ofrecen tiempos históricos y recursos iniciales por run sin servicios externos. No añadir manifiestos duplicados, un segundo scheduler ni dependencias cloud.

## Colaboración opcional con backlog-agile-workflow

Cuando `backlog-agile-workflow` esté disponible, asociar cada gate local a las tareas pertinentes y decisiones existentes; registrar run/outcome, evidencia y SHA reales antes de marcar DoD, sin exigir ROADMAP/ADR/SPEC paralelos. Auditar archivos de gestión y ZIP privados antes de la publicación: no deben versionarse en aplicaciones consumidoras. No excluir ZIP de binarios de distribución por su extensión. PipelineK no modifica automáticamente el backlog ni declara DONE por un run verde sin contrato verificado.


## Procedencia inter-agente y Ghost Context

Antes de modificar gates, etapas o cobertura, contrastar decisiones humanas vigentes del Backlog con implementación y tests reales. Un handoff no autoriza rebajar CI; revisar permisos efectivos y riesgos. Una discrepancia entre rúbrica y pipeline actual se reporta, no se resuelve suprimiendo tests.

Si `backlog-agile-workflow` está disponible, enlazar IDs de tarea/decisión y su origen. Si no, conservar la incertidumbre sin crear otra autoridad.
