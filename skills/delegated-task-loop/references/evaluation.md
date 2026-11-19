# Evaluación operacional por pares

La recuperación semántica y los benchmarks documentales pertenecen a software-knowledge. Esta evaluación mide el workflow completo, no el ranking de conocimiento. No usa agentes como simuladores de tokens.

Diseñar casos con un conjunto fijo de tareas y base Git exacta, AC/DoD, política de acceso, límites de esfuerzo y orden reproducibles; hash SHA-256 del manifiesto (workloadDigest). Comparar agente único, supervised-task-loop y delegated-task-loop; usar clones desechables equivalentes, sin compartir memoria generada entre variantes. Repetir y alternar el orden para reducir sesgo de caché. environmentDigest representa el modelo/host/versión, presupuesto, permisos y herramientas comunes, excluyendo únicamente el tratamiento comparado. Si no se puede igualar la configuración, declarar comparabilidad limitada; no agrupar pares distintos.

Medir desde el host: totalTokens suma supervisor, workers y revisores incluyendo intentos fallidos; si falta algún consumo, omitir la métrica. Separar transferBytes de tokens. Medir pico de contexto del supervisor solo con contador real, no longitud del checkpoint. Latencia en ms, lecturas repetidas equivalentes, intervenciones, recuperación, recursos huérfanos y tareas reabiertas. Ausencia no es cero. Un evaluador independiente contrasta aceptación y evidencias; no usar el estado Done como única evidencia. Para aceptación pass, todas las tareas del caso deben estar aceptadas y el run completado. Registrar resultados parciales/failed/blocked con costes observados, no descartarlos. Reaperturas requieren ventana igual para los tres tratamientos.

El ejemplo es sintético, no una campaña ejecutada:

```bash
python3 scripts/evaluate_runs.py examples/evaluation-plan.json
```

Guardar esa plantilla y las observaciones reales en estado privado, no en el checkout del consumidor. Ejecutar evaluate_runs.py PLAN OBSERVACIONES. Cada registro incluye case, pair, variant, runId, workloadDigest, environmentDigest, status, metrics, acceptance, reviewerRef y evidenceRefs. El planDigest impide confundir planes. NOT_RUN no lleva mediciones. Métricas admitidas: acceptedTasks, totalTokens, elapsedMs, transferBytes, supervisorPeakContextTokens, repeatedReads, interventions, recoveryMs, resourceLeaks, reopenedTasks, confirmedDefects. Todas enteras no negativas; desconocidas se omiten.

El informe compara el candidato frente a cada baseline por separado. Registra muestras excluidas, regresiones de completitud/calidad y deltas con tamaño de muestra, incluyendo el coste de fallos. Tokens y tiempo por entrega se calculan solo entre ejecuciones aceptadas. Sin observaciones: not-evaluated, medianas null. No certifica los datos ni permite afirmar superioridad a partir de fixtures. Una muestra pequeña es exploratoria, no significación estadística.

Los resultados no se inyectan al supervisor habitual; consultarlos al evaluar metodología o ajustar presupuestos.

Métricas adicionales opcionales: briefPreparationMs, firstUsefulChangeMs, contextQuestions, redundantVerificationMs, administrativeWorkerMs, stewardMs, bureaucracyBlockedMs, duplicateOperations, workerOutputTokens, workerRounds. Medir solo con evidencia observada, misma unidad y alcance. [Telemetría](telemetry.md) local; coste de todos los agentes incluidas esperas, intentos e intervenciones. Ajustar model routing por coste por entrega aceptada, no por precio/token aislado.
