# Capacidades del host, no adaptadores ficticios

Consultar las herramientas efectivamente anunciadas por el host y sus restricciones. No inferir que una API está disponible solo por el producto instalado.

| Capacidad | Evidencia requerida | Degradación |
| --- | --- | --- |
| fresh | herramienta real que crea conversación independiente | NOT_RUN |
| background | ejecución no bloqueante real | delegación síncrona |
| notify | notificación nativa de resultado | esperar retorno nativo |
| progress | eventos de avance accesibles | checkpoints al retorno |
| steer | canal de mensajes al worker activo | corrección posterior |
| cancel | interrupción real confirmable | no abrir sustituto hasta reconciliar |
| resume | continuación de identidad existente | fresh tras reconciliar |

Claude Code, Codex y OpenCode exponen distintas capacidades según versión, configuración e interfaz. Consultar [Claude Code](https://code.claude.com/docs/en/sub-agents), [Codex](https://developers.openai.com/codex/subagents), [OpenCode](https://opencode.ai/docs/agents/). No usar CLI headless como fallback ni sesiones nuevas lanzadas por scripts. Solo recibir resultados reales del host.

Canary: comprobar aislamiento conversacional y permisos; registrar trazas y limitaciones. Un prompt de solo lectura no impone permisos; para Goldfish exigir restricciones efectivas según su contrato. Si no hay aislamiento suficiente, registrar NOT_RUN o limitación expresa según la skill.

No instalar plugin, daemon, SDK ni adaptador ACP por defecto. Cualquier instrumentación futura será opcional y dependiente del host.
