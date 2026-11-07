# Resolución: del informe al trabajo existente

1. Contrastar cada finding con código, contrato y revisión Git actual. Distinguir \`OBSERVED\`, \`INFERRED\`, \`UNKNOWN\`, \`STALE\` y \`REFUTED\`. Si se requieren pruebas, delegar a la skill de testing instalada. Un reporte de agente no es evidencia de ejecución.
2. Agrupar por cambio subyacente y coste de mitigación. Comparar KEEP_AS_IS con la corrección mínima, seguridad, rendimiento, blast radius y tiempo de pruebas.
3. Los hallazgos de la tarea actual se resuelven en esa tarea; propuestas de investigación futura permanecen como conocimiento reutilizable o borrador **solo si está autorizado**. Crear tarea independiente únicamente tras deduplicar y demostrar valor separado.
4. Registrar por **Backlog.md CLI/MCP oficial**: \`task view\`, \`search\`, \`doc search\`, \`task edit --append-notes\` para progreso y \`--add-doc\` con ruta observada para conocimiento duradero. Leer help de la CLI instalada. Nunca modificar frontmatter a mano; \`--notes\` y \`--tags\` pueden reemplazar valores.
5. Decisiones arquitectónicas materiales pertenecen a \`backlog decision\`; una propuesta Goldfish no equivale a autorización del propietario. Respetar decision-provenance y WIP. Los revisores no cambian ninguna tarea ni estado.
6. Revisar el SHA y los fingerprints del objetivo antes de aplicar una corrección. Ejecutar comprobación focal, registrar NOT_RUN distinto de PASS, y devolver \`KEEP_AS_IS / PROPOSE_CHANGE / EXPERIMENT / NEED_EVIDENCE / BLOCKED\`.
7. No hacer un loop automático hasta eliminar todos los hallazgos; la siguiente ronda se justifica por defectos mayores sin resolver y presupuesto. Informes privados efímeros, no históricos públicos por defecto.
