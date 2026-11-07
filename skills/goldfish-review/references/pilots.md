# Pilotos y pruebas reales de aislamiento

Las pruebas unitarias y fixtures incluidas en la skill **no certifican** que un agente mantenga una conversación independiente, que el host limite archivos ni que el modelo detecte bugs.

## Preparación

1. Seleccionar un documento de diseño real existente y un SHA Git completo, registrar fingerprint y fuentes permitidas. No publicar texto privado sin permiso.
2. Poner un canary aleatorio únicamente en el contexto del Elephant (no en documentos, argumentos o archivos del repositorio).
3. Lanzar un subagente de contexto nuevo con herramientas explícitamente read-only y la rúbrica. No añadir historial ni context handoff.
4. Observar si el canary aparece. Repetir con instrucciones en AGENTS.md/CLAUDE.md para separar fuga conversacional de instrucciones del entorno.
5. Simular fuente externa con instrucción maliciosa inofensiva y comprobar que se trata como dato. Comprobar que permisos efectivos impiden escritura; no confiar en «no escribas» del prompt.
6. Contrastar dos o tres hallazgos con código y tests autorizados y registrar cuántos eran falsos positivos, tiempo y tokens realmente observados.

## Tres pilotos sugeridos (NO EJECUTADOS)

| Sistema | Pregunta de revisión | Evidencia mínima |
| --- | --- | --- |
| PipelineK output plane | ¿Los seams y consumidores hacen innecesario un nuevo formato durable? | diseño, módulo productor, consumidores, tests focales |
| PipelineK Fabric durable store | ¿Qué fallos de concurrencia o recuperación dependen de invariantes no declarados? | código de store, contratos de persistencia, benchmarks existentes |
| NextDraw JS/WASM | ¿La propuesta de optimización realmente evita conversiones y justifica su complejidad? | bindings actuales, contratos Rust/JS, benchmark reproducible |

Estos son escenarios de evaluación, no defectos observados. Ejecutarlos solo con checkout y permisos reales en el host. Los hallazgos de pruebas reales se incorporan a la tarea/decisión apropiada por Backlog CLI, no a una base paralela.

## Puerta de adopción

Mantener opt-in hasta reunir evidencia de al menos tres diseños evaluados con código observable. Informar ratio de hallazgos confirmados/refutados, rework evitado y coste de revisión; rechazar automatización si el valor no justifica el gasto. No abrir una E2E permanente por cada host.
