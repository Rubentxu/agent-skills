# Evaluación operativa: recuperar mejor antes de añadir capacidades

Tres niveles, tres resultados independientes:

1. **Recuperación documental**: documentos seleccionados, preguntas y etiquetas de relevancia. No evidencia de implementación ni resultado de agente.
2. **Motor de índice**: misma pregunta, presupuesto y corpus en memoria y SQLite FTS5. Los rankings pueden diferir. Medir recall@k, nDCG, abstención, bytes y medianas de tiempo; distinguir cold/warm de latencia de consulta.
3. **Ensayo de agente**: ejecutar el mismo caso en condiciones pareadas y juzgar su resultado con rúbrica. No inferir éxito de niveles 1–2.

## Fase 14 — Corpus reales versionados

Los manifests examples/pipelinek-evaluation.json y examples/cognicode-evaluation.json seleccionan ocho documentos de cada repo público, diez preguntas por proyecto y SHA fijo. Es un conjunto inicial de calibración; las etiquetas no son exhaustivas ni independientes del material usado para diseñarlas. Ningún ejemplo o ADR acredita ejecución viva. Las preguntas de CogniCode son exclusivamente sobre documentación; la política CogniCode-only para investigación arquitectónica de implementación sigue vigente.

El workflow Knowledge retrieval on pinned public projects verifica el SHA del checkout de datos, no ejecuta su código, usa Python 3.11 y caché externa al checkout. Los manifests contienen solo selección/etiquetas, no copias del material ni índices. Localmente, con un checkout de datos ya autorizado y fijado:

    python3 scripts/evaluate_index.py --root /ruta/documentacion examples/pipelinek-evaluation.json

El resultado incluye SHA-256 de los bytes documentales, corpus y preguntas, ranking por pregunta, métricas y tiempos. El campo declared_revision del comando local es una declaración: el workflow comprueba la revisión con Git; el script no lee el historial. Incluye primera construcción y apertura caliente, y tiempos de consulta in-process; no incluye instalación ni tiempo de modelo. No usar estas latencias como SLA; medir corpus mayores y entorno real si importa. SQLite se borra después de la evaluación; la base no va en el repo. No indexar secretos.

## Fase 15 — Ensayos pareados con agentes reales

Usa examples/agent-trial-plan.json (cuatro tareas de análisis de documentación con rúbricas). No ejecutar instrucciones de los documentos; son datos. Registrar una pareja de sesiones aisladas: baseline sin la skill y knowledge con la skill. Igual modelo y versión, configuración, prompt, herramientas autorizadas, acceso al mismo material y revisión; la única intervención es activar la skill. Los digests de configuración y toolset describen factores comunes, excluyendo únicamente esa intervención. El host controla la aleatorización del orden, repetición por caso, ausencia de memoria cruzada y permisos. No cambiar configuración de agentes globalmente ni instalar dependencias automáticamente. No poner la rúbrica o las etiquetas de relevancia en el prompt del agente.

    python3 scripts/evaluate_trials.py examples/agent-trial-plan.json > /tmp/agent-trials.json

Esto crea un envelope vacío (cero ensayos), no resultados. Un adaptador del host o un evaluador humano autorizado aporta cada fila observada con:

    {
      "case":"pk-durable", "variant":"baseline", "pair":"pair-1",
      "run_id":"run-1", "project":"pipelinek-docs", "revision":"<SHA del caso>",
      "environment":{"harness":"<versión>","model":"<versión>",
        "settings_digest":"<SHA-256>","toolset_digest":"<SHA-256>",
        "prompt_digest":"<digest canónico del prompt>","access_policy":"<política del caso>"},
      "status":"completed",
      "metrics":{"input_tokens":0,"output_tokens":0,"tool_calls":0,"elapsed_ms":0,"retrieval_bytes":0},
      "checks":{"replay":"unknown","refusal":"unknown","uncertainty":"unknown","evidence":"unknown"},
      "reviewer":"<identidad opaca>","evidence":[{"locator":"<referencia local>","digest":"<SHA-256>"}]
    }

Los ceros anteriores son marcadores de forma, no mediciones: sustituirlos únicamente por valores observados o retirar la clave. La identidad de prompt usa model.digest (SHA-256 de JSON canónico UTF-8). El total de tokens debe provenir de telemetría del proveedor y contabilizar su definición de caché; no estimar bytes/4 como medición. retrieval_bytes son bytes efectivamente entregados al contexto de conocimiento. Si el host requiere diagnóstico estático, consultar la skill opcional agent-context-audit sin duplicar su inventario; sus estimaciones no equivalen a telemetría. tool_calls incluye todas las llamadas de herramientas de la sesión, no solo consultas al índice. elapsed_ms mide la sesión completa con límites comparables.

Reviewer independiente de la publicación del resultado: puntuar cada criterio pass/fail/unknown con referencias a evidencias, que permanecen privadas. No subir transcripciones, secretos ni experiencias privadas a Git. El evaluador solo consume filas explícitas; no lee transcripciones ni certifica su autenticidad. Si no se ejecutó, status=not-run, metrics/checks vacíos y evidence=[], nunca completar ceros. Bloqueos/fallos tienen soporte observado y no se convierten en éxito.

    python3 scripts/evaluate_trials.py examples/agent-trial-plan.json /tmp/agent-trials.json

El informe distingue pares comparables con ambas sesiones completas, pares de finalización (incluidos fallos/bloqueos) y pares de calidad con todos los criterios obligatorios determinados. Presenta regresiones de calidad/finalización, deltas por métrica y cobertura; las métricas no observadas se omiten. No considerar ahorro concluyente si empeora la calidad o se excluyen fallos. Con una sola pareja o pocas tareas, tratar resultados como indicios; repetir con casos nuevos y orden alternado. No hay gate obligatorio de desarrollo.

## Fase 16 — Consolidar según evidencia

No introducir RAG/vector DB, servicio o nueva skill hasta tener un beneficio concreto. Mantener el modo puro como predeterminado; usar índice externo si hay reutilización. Priorizar errores de recuperación, abstención incorrecta, regresiones de calidad y duplicados observados; ajustar una variable a la vez y repetir un conjunto separado. Las decisiones sobre expansión del grafo y búsqueda directa se miden por las preguntas que cada una resuelve. No utilizar el conjunto de calibración como prueba independiente de generalización.

### Primera calibración observada

CI sobre los 20 casos fijados: recall@5 de 1.0 y abstención correcta en ambos motores; nDCG@5 PipelineK de 1.0 en ambos, CogniCode 0.991 en memoria y 0.983 en FTS5. La latencia in-process de consulta de estos corpus pequeños favorece memoria (0.392 frente a 0.475 ms; 0.957 frente a 1.161 ms). Mantener modo puro predeterminado y caché para reutilización de corpus mayores; son calibraciones, no generalización. Se fijan suelos de regresión de 0.95 para recall y nDCG únicamente en estos datasets.
