# Arquitectura emergente basada en código y decisiones

**Objetivo:** evolucionar responsabilidades y contratos con el menor cambio seguro.

1. Leer código real, revisión Git y tareas. Groma es opcional para ownership C4, pero un scan no acredita el comportamiento.
2. Recuperar por términos ubicuos las decisiones, invariantes, algoritmos, investigaciones y riesgos del componente. Separar estructura observada, intención propuesta y resultado ejecutado.
3. Analizar seams, dependencias, connascence, límites de confianza y escenarios de fallo. Comparar KEEP_AS_IS con cambio reversible; no imponer refactor de estilo sin beneficio.
4. Definir invariantes, contratos afectados y fitness checks verificables. Usar pruebas de garantías con coste proporcional y señales de observabilidad existentes.
5. Persistir descubrimientos reutilizables vía documentos Backlog; decisiones por comando nativo solo con aprobación humana. Vincular tareas y archivos observados sin inventar IDs.
6. Verificar código y pruebas tras el cambio; no confundir diseño futuro, documento OKF y arquitectura implementada.

**Salida:** seam verificado, cambio mínimo, invariantes, alternativas, costes y evidencia de cierre.
