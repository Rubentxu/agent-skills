# Delegated Task Loop

Supervisor ligero con subagentes nativos y aprendizaje acumulativo. Independiente de supervised-task-loop.

Instalación selectiva (instala también las tres skills de composición si no están presentes):

```bash
npx skills add Rubentxu/agent-skills --skill delegated-task-loop
npx skills add Rubentxu/agent-skills --skill backlog-agile-workflow
npx skills add Rubentxu/agent-skills --skill software-knowledge
npx skills add Rubentxu/agent-skills --skill goldfish-review
```

Invocar desde un agente que disponga de delegación nativa: «Usa delegated-task-loop para avanzar hasta tres tareas listas del Home Repo. Conserva el contexto mínimo, verifica cada entrega y no publiques fuera de las políticas del proyecto».

[Contrato principal](SKILL.md) · [Navegación](references/workflow-navigation.md) · [Evaluaciones](tests/skill-evals.md).

Composición, políticas de contexto, router puro, [reservas y checkpoints privados](references/run-state.md) y [contratos de atribución](references/contracts.md). El host ejecuta y supervisa; no hay garantía de background, eventos, interrupción ni aislamiento sin comprobar cada capacidad. No se ejecutan agentes desde Python.

```bash
python3 skills/delegated-task-loop/scripts/affordances.py skills/delegated-task-loop/examples/ready.json
python3 -m unittest discover -s skills/delegated-task-loop/tests -p 'test_*.py' -v
```

[Canaries y perfiles nativos](references/host-canaries.md): capacidades observadas por sesión, no supuestas por marca del host. Estado inicial real: NOT_RUN hasta ejecutar los canaries.

[Supervisión por eventos](references/event-supervision.md): proyección compacta, alertas deduplicadas, intervención por señales verificables y detección de degradación. No añade procesos ni polling.

[Evaluación comparativa](references/evaluation.md): tres estrategias, coste total, calidad y recuperación; los datos ausentes no se convierten en cero.

[Fan-out de solo lectura](references/parallel-read.md): candidatos nativos acotados por slots, contexto y fuentes inmutables. El paralelismo de escritores sigue deshabilitado.

[Handoff Engineering v2](references/handoff-engineering.md): resolver ambigüedad, asignar criterios, proyección de políticas/hechos, plan de verificación, recursos y deltas versionados. Instalar delivery-first-testing si se desea el compilador público de pruebas: `npx skills add Rubentxu/agent-skills --skill delivery-first-testing`.

[Telemetría](references/telemetry.md) local y [verificación proporcional](references/proportional-verification.md). [Adopción de recursos](references/resource-adoption.md) y [Steward efímero](references/steward.md) conservan reservas hasta reconciliar efectos; requieren permisos y capacidades nativas comprobados.

El ejemplo [entrada del router](examples/ready.json) muestra preparación, no autoridad de lanzamiento. Usar preflightRef de un handoff realmente preparado; validar recursos antes de aceptar/liberar. La integración de contratos se comprueba en tests de colección sin imports entre skills.

[Validación operacional y piloto](references/pilot-validation.md): tres cambios acotados sobre código real fijado, oráculos separados y campaña pareada. No declara productividad hasta ejecutar agentes nativos.
