# Informes y métricas locales de PipelineK

## Qué medir

PipelineK ya ofrece `pipelinek inspect <runId> --db <journal> --profile` y telemetría opcional. Para histórico de duración y recursos iniciales, la herramienta **instalada en `tools/`** añade un **adaptador offline** que consume `pipelinek events ... --typed`. No necesita OpenTelemetry Collector ni servicios externos.

- `CompilationStarted/CompilationFinished`: compilación de la DSL; también se mide extremo a extremo desde la compilación hasta RunFinished cuando existen ambos hechos.
- `RunStarted/RunFinished`: duración del run **solo cuando hay terminal**. No confundirla con el tiempo total incluyendo compilación.
- `StageStarted/StageFinished`: tiempos por stage, sucesivas ejecuciones y regresiones entre ventanas temporales.
- `StepStarted/StepFinished/StepFailed`: tiempos de steps emparejados de forma conservadora. Un evento sin pareja no tiene duración ficticia.
- Snapshot anterior al lanzamiento: CPU lógicos, afinidad CPU, cuota cgroup, carga 1/5/15, RAM host y límite cgroup, disco disponible; el wrapper registra por separado CPU user/system del proceso hijo reaped y RSS máximo de un proceso cuando es observable. El snapshot **no** mide consumo acumulado.
- `coverage`: COMPLETE o PARTIAL; run sin terminal o con stage abierto no se presenta como éxito de tiempo medido.
- Tendencia: histórico de hasta 50 muestras por stage y delta de medianas de los últimos cinco runs contra los cinco anteriores. Una muestra ausente nunca se imputa a cero.

## Lugar por defecto

`$XDG_STATE_HOME/pipelinek/projects/<sha256(path-canónico-del-worktree)[0:16]>/reports/`
(o `~/.local/state` si no se define XDG_STATE_HOME). No crear un nuevo tracker en Backlog ni registrar secretos. Los reportes son propiedad operativa de PipelineK y **no deben versionarse por defecto**.

```text
reports/
├── runs/
│   └── <sha256-runId>.json
└── dashboard.html
```

Los snapshots previos se guardan donde el supervisor lo indique con permisos restringidos. Puede exportarse `dashboard.html` a `reports/pipelinek/` del proyecto solo por petición expresa, revisión de sensibilidad y exclusión o inclusión intencional en Git.

## Uso directo desde cualquier repositorio

**Preferir la distribución instalada sobre scripts del checkout del motor.** La distribución de PipelineK lleva en `tools/` los helpers `pipelinek-run-with-metrics.py`, `pipelinek-local-report.py` y `pipelinek-resume-state.py`. Resuelven cualquier directorio de proyecto y script `.pipeline.kts`, sin necesitar fuentes, builds de PipelineK ni GitHub Actions.

```bash
PIPELINEK_BIN="$(command -v pipelinek)"
PIPELINEK_HOME="$(cd "$(dirname "$(readlink -f "$PIPELINEK_BIN")")/.." && pwd)"
RUNNER="$PIPELINEK_HOME/tools/pipelinek-run-with-metrics.py"

# Ejecuta con journal durable y registra tiempos, recursos, estado y HTML
python3 "$RUNNER" --project . --script pipeline.kts --workflow ci --resume-or-new

# Inspección local de sesiones tras un apagón (sin volver a ejecutar)
python3 "$RUNNER" --project . --script pipeline.kts --workflow ci --status

# Continuación estricta de una sesión pendiente
python3 "$RUNNER" --project . --script pipeline.kts --workflow ci --resume
```

Para scripts bajo `pipelines/` usar la misma opción `--script` con su ruta. El helper guarda sesiones privadas por UUID, un snapshot de recursos inicial por intento y `process-usage-attempt-N.json` con wall time de la invocación, CPU de los hijos reaped y una estimación de RSS máximo de proceso cuando el sistema operativo permite medirlo. Estos datos **no equivalen** a muestreo continuo ni al pico agregado del cgroup. Las métricas de stages/steps salen exclusivamente del journal de PipelineK y el dashboard no es autoridad sobre estado del run.

Si el helper no está disponible en una instalación antigua, es posible usar directamente `pipelinek run --db ... --control-root ...` y `pipelinek events --typed` con el proyector local; en ese caso el supervisor es responsable de conservar la identidad y los paths durables. Consultar [reanudación tras caída](15-crash-resume.md).

Los eventos tipados pueden contener payloads sensibles y el reportero debe consumirlos por un pipe, no archivarlos como JSONL bruto. Persistir solo campos permitidos y omitir nombres de steps/stages salvo consentimiento explícito. No mezclar históricos de proyectos, worktrees o máquinas con toolchains/coberturas distintas.

## Interpretación

- Dos runs de distinta máquina no son directamente comparables sin ver CPU afinidad/cuota, memoria disponible, carga inicial, toolchain y alcance. El snapshot no mide máximos ni energía consumida.
- La duración de stages concurrentes **no se suma** para estimar el tiempo total de run; el total viene de RunStarted/RunFinished. Las etapas pueden solaparse.
- Para diferenciar CPU/RAM efectivamente **consumidos** hay que añadir sampling del proceso/cgroup con identidad de run y permisos apropiados, sin confundir host con proceso. No declararlo medido hasta implementarlo.
- Un historial refleja evolución temporal observada; no implica que una regresión proceda necesariamente del código. Evaluar cambios de entorno, caché y cobertura antes de actuar.
- Los reportes HTML son estáticos, sin JavaScript ni red. Revisar antes de compartir incluso cuando no contengan logs.

## Agentes

Leer `runId`, outcome, duraciones, coverage y recursos iniciales desde JSON. Comparar medianas por stage entre runs con política/toolchain comparables; investigar el mayor incremento reproducible. No adjuntar históricos enteros al prompt: resumir los 3-5 mayores regresores con evidencias. Nunca volver a ejecutar pruebas solo para dibujar el dashboard.
