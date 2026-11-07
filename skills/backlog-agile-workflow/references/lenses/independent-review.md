# Revisión independiente (Goldfish)

**Pregunta:** ¿puede un nuevo lector refutar el diseño sin conversaciones heredadas?

1. Recuperar por CLI de Backlog, Git, documentos, glosario y Groma opcional únicamente el contexto autorizado. Fijar SHA completo, hash del diseño, pregunta y fuentes.
2. KEEP_AS_IS para cambios triviales. Para contratos y arquitectura seleccionar lite/focused; deep requiere riesgo y presupuesto. No activar automáticamente por lectura de archivo ni hook.
3. Si está instalada goldfish-review y el host dispone de subagente de contexto NUEVO, pasar solo target, rúbrica y fuentes; nunca conversación ni preferencias privadas del Elephant.
4. Comprobar controles reales de solo lectura, fuentes, symlinks e instrucciones heredadas. Sin aislamiento suficiente NOT_RUN o INCONCLUSIVE; jamás simular un Goldfish en el contexto principal.
5. Contrastar hallazgos por [resolución](review-resolution.md). No declarar PASS de tests ni añadir tickets por cada nota.

**Salida:** propuesta y hallazgos rastreables o limitación explícita.
