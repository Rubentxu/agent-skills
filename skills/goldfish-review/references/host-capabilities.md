# Adaptación al host (sin framework propio)

- **Claude Code**: usar la herramienta nativa Agent/Task cuando exista, lanzando un agente con contexto nuevo. Configurar tools readonly desde el host, no solo el prompt. Comprobar opciones reales de aislamiento de instrucciones, que pueden variar por versión.
- **Codex**: usar spawn/wait cuando estén expuestos. Desactivar herencia de turnos si el host lo ofrece y verificar con canary; \`fork_turns=none\` no certifica ausencia de AGENTS.md.
- **ChatGPT Work y otros**: comprobar la disponibilidad real de subagentes con contexto nuevo. Una skill instalada no otorga herramientas nuevas. Si no hay delegación, NOT_RUN.
- **OpenCode / otros**: usar capacidad de subagente documentada por el host solo tras comprobar separación de historia y permisos. No asumirla por nombre del producto.

No añadir un orquestador en Python/Node para el modelo: invocar directamente el mecanismo oficial del host. El \`review_contract.py\` trabaja exclusivamente sobre archivos JSON que el host le proporciona; no crea procesos de agente, no accede a Backlog, no abre sockets ni edita el repositorio.

**Prueba piloto**: registrar versión de host, herramienta de delegación, configuración de permisos, canary de conversación, canary de instrucciones, resultado y límites. Cualquier declaración de aislamiento es HOST_REPORTED, su calidad depende de esa evidencia.
