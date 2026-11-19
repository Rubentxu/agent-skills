# supervised-task-loop

Bucle supervisado de sesiones de agente sobre un tablero Backlog.md: **una sesión, una
tarea, contexto en cero**. El supervisor no recuerda; mide. Lo que cruza entre sesiones son
solo el tablero (qué está hecho) y el handoff (cómo fue la anterior).

Incluye el runtime en Python (configuración, preflight, handoff, iteración, informe, espera
honesta), la pipeline de PipelineK que da el ritmo, la plantilla del prompt con el contrato
de la sesión y las pruebas que lo cubren.

## Los tres sitios que la configuración distingue

| Sitio | Qué es |
|---|---|
| **workspace agéntico** | el directorio desde el que el agente ve sus repos: el propio proyecto, o el padre de varios |
| **home repo** | el repo del proyecto: el que lleva el tablero (`backlog/`); aquí corre la pipeline |
| **runtime** | donde viven los scripts (`agent_*.py`): la skill instalada o el propio proyecto |

En el **patrón home repo** los tres no coinciden: el workspace agéntico es el directorio
padre, el home repo es uno de sus hijos, y el runtime puede vivir en el home repo o en la
skill instalada.

## Uso mínimo

```bash
# el runtime en el proyecto
cp -r <skill>/scripts <proyecto>/scripts
cp -r <skill>/assets  <proyecto>/assets
cp <skill>/assets/pipeline.agent.kts <proyecto>/pipeline.agent.kts

# el runtime en la skill instalada: el proyecto solo lleva la configuracion
cp <skill>/assets/agent-loop.env <proyecto>/agent-loop.env   # rellenalo una vez

python3 <proyecto>/scripts/agent_run.py     # o <skill>/scripts/agent_run.py
```

Requiere `pipelinek`, la CLI de `backlog`, `gh` autenticado y un perfil de sesión del host.

Instalación selectiva desde la colección pública:

```bash
npx skills add Rubentxu/agent-skills --skill supervised-task-loop --agent opencode
```

Antes de publicar, ejecutar el validador (`python3 scripts/validate_skills.py`) y las pruebas
de `skills/supervised-task-loop/tests/`.

La recuperación distingue sesión terminada de intento incompleto, preserva artefactos y evita re-medir. Consultar [fallos](references/04-failure-modes.md) para reconciliación, proxy y deadline autónomo.
