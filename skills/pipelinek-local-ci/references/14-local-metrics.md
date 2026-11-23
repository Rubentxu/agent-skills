# Informes y métricas locales de PipelineK

## Qué medir

PipelineK ya ofrece `pipelinek inspect <runId> --db <journal> --profile` y telemetría opcional. Para histórico de duración y recursos iniciales, `pipeline-kotlin/scripts/pipelinek-local-report.py` añade un **adaptador offline** que consume `pipelinek events ... --typed`. No necesita OpenTelemetry Collector ni servicios externos.

- `CompilationStarted/CompilationFinished`: compilación de la DSL; también se mide extremo a extremo desde la compilación hasta RunFinished cuando existen ambos hechos.
- `RunStarted/RunFinished`: duración del run **solo cuando hay terminal**. No confundirla con el tiempo total incluyendo compilación.
- `StageStarted/StageFinished`: tiempos por stage, sucesivas ejecuciones y regresiones entre ventanas temporales.
- `StepStarted/StepFinished/StepFailed`: tiempos de steps emparejados de forma conservadora. Un evento sin pareja no tiene duración ficticia.
- Snapshot anterior al lanzamiento: CPU lógicos, afinidad CPU, cuota cgroup, carga 1/5/15, RAM host y límite cgroup, disco disponible. Se mide capacidad/carga del entorno, **no consumo real de CPU/RAM del proceso**.
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

## Receta local de extremo a extremo

```bash
# Desde el proyecto consumidor, usando la copia/version de script instalada:
REPORTER=/ruta/confiable/pipelinek-local-report.py
REPORTS="${XDG_STATE_HOME:-$HOME/.local/state}/pipelinek/my-project/reports"
python3 "$REPORTER" snapshot --workspace . --out "$REPORTS/before-run.json"

# Ejecutar el pipeline local real con journal persistido (obtener runId del recibo):
pipelinek run --db "$REPORTS/../journal.db" --control-root "$REPORTS/../control" pipeline.kts

# Una vez observado RunFinished, establecer RUN_ID con el ID real:
# RUN_ID=<identidad emitida por PipelineK>
pipelinek events "$RUN_ID" --db "$REPORTS/../journal.db" --typed --limit 1000000 \
  | python3 "$REPORTER" ingest --events - --snapshot "$REPORTS/before-run.json" \
      --workflow ci --history-dir "$REPORTS"

python3 "$REPORTER" dashboard --history-dir "$REPORTS"
# Abrir localmente $REPORTS/dashboard.html
```

No ejecutar la captura contra un run aún no terminado si se pretende un resultado final; una lectura parcial queda marcada como incompleta. `events` tiene límite por defecto de 100: usar `--limit` suficiente y comprobar terminal y rechazos. La captura `--typed` puede incluir payloads sensibles: pasarla directamente al proyector, no guardar JSONL bruto. El proyector solo persiste campos seleccionados y omite nombres de steps/stages por defecto. `--include-names` es una decisión de confianza explícita para nombres estáticos que no contienen datos sensibles.

## Interpretación

- Dos runs de distinta máquina no son directamente comparables sin ver CPU afinidad/cuota, memoria disponible, carga inicial, toolchain y alcance. El snapshot no mide máximos ni energía consumida.
- La duración de stages concurrentes **no se suma** para estimar el tiempo total de run; el total viene de RunStarted/RunFinished. Las etapas pueden solaparse.
- Para diferenciar CPU/RAM efectivamente **consumidos** hay que añadir sampling del proceso/cgroup con identidad de run y permisos apropiados, sin confundir host con proceso. No declararlo medido hasta implementarlo.
- Un historial refleja evolución temporal observada; no implica que una regresión proceda necesariamente del código. Evaluar cambios de entorno, caché y cobertura antes de actuar.
- Los reportes HTML son estáticos, sin JavaScript ni red. Revisar antes de compartir incluso cuando no contengan logs.

## Agentes

Leer `runId`, outcome, duraciones, coverage y recursos iniciales desde JSON. Comparar medianas por stage entre runs con política/toolchain comparables; investigar el mayor incremento reproducible. No adjuntar históricos enteros al prompt: resumir los 3-5 mayores regresores con evidencias. Nunca volver a ejecutar pruebas solo para dibujar el dashboard.
