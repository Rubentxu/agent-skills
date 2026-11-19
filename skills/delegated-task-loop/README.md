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

Composición, políticas de contexto, router puro, [reservas y checkpoints privados](references/run-state.md) y evaluaciones de contrato. El host ejecuta y supervisa; no hay garantía de background, eventos, interrupción ni aislamiento sin comprobar cada capacidad. No se ejecutan agentes desde Python.

```bash
python3 skills/delegated-task-loop/scripts/affordances.py skills/delegated-task-loop/examples/ready.json
python3 -m unittest discover -s skills/delegated-task-loop/tests -p 'test_*.py' -v
```
