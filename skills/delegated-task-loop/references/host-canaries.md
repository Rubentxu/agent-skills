# Canaries nativos: observar antes de afirmar

Ejecutar dentro del anfitrión que el usuario está utilizando, en un workspace desechable autorizado. Nunca lanzar un binario de agente para probar la delegación. No instalar herramientas. Los ejemplos son sintéticos.

1. Registrar versión y handle de la sesión actual; descubrir herramientas de delegación efectivamente expuestas. Si no existen, devolver NOT_RUN sin probar por shell.
2. Fresh: el supervisor guarda una etiqueta aleatoria no secreta en su conversación; delegar un prompt pequeño sin esa etiqueta, sin fork del historial. Comprobar configuración efectiva de contexto y resultado (conocimiento de la etiqueta invalida aislamiento; no conocerla no lo demuestra por sí solo). No copiar el transcript.
3. Background y notificación: pedir una actividad breve inocua y comprobar si el lanzamiento retorna antes del resultado y si llega notificación nativa atribuida.
4. Progress y steering: pedir dos hitos distintos, recibir el primero antes de finalizar, cambiar el segundo con mensajería nativa; constatar que la directiva fue recibida durante ejecución. No confundir mensajes al terminar con progreso en vivo.
5. Cancel: solo en el canary desechable; comprobar fin del worker y de operaciones que podían escribir. Un acuse de cancelación no es confirmación de parada.
6. Resume: continuar el mismo handle nativo solo después de comprobar parada; verificar continuidad de una etiqueta de trabajo, no reutilizar autorización.
7. Read-only-review: comprobar restricciones efectivas del revisor según goldfish-review y su aislamiento; una instrucción de no editar no basta. Isolated-writer: comprobar separación real de workspaces y permisos. No ensayar escrituras fuera de un entorno desechable.
8. Supervisor-compaction: guardar checkpoint, utilizar la recuperación/compactación del host si la expone, verificar que puede continuar y medir contexto antes/después solo si existe contador real.

Guardar únicamente referencias a evidencia local y estado PASS/FAIL/NOT_RUN por caso; no secretos ni logs. El helper proyecta afirmaciones observadas, no verifica las fuentes ni certifica el host.

```bash
python3 scripts/host_probe.py < examples/host-observations.json
```

El resultado se usa en el router como capabilities, junto con limitaciones y el resto de estado observado. No importar capacidades de otro host, versión o sesión sin revalidarlas. Si no se ejecuta un canary, su capacidad queda sin confirmar.

## Cómo delegar según el host

- [Claude Code](https://code.claude.com/docs/en/sub-agents): utilizar la herramienta Agent con instrucciones nuevas; enviar correcciones por SendMessage si existe y comprobar la identidad. Los hooks [SubagentStart/SubagentStop](https://code.claude.com/docs/en/hooks) son observaciones de ciclo de vida, no prueba de limpieza ni garantía de que despierten el supervisor. Usar notificaciones nativas.
- [Codex](https://developers.openai.com/codex/subagents): utilizar la herramienta spawn_agent anunciada. Según versión, elegir fork_context=false o fork_turns=none cuando el esquema lo permita; nunca aceptar por defecto un fork completo. Esperar con wait_agent o notificación real; mensajería/cancelación varían por versión. No asumir que close_agent existe. Ver la [referencia de herramientas de Superpowers](https://github.com/openai/plugins/blob/main/plugins/superpowers/skills/using-superpowers/references/codex-tools.md).
- [OpenCode](https://opencode.ai/docs/agents/): utilizar Task/subagent nativo según la versión, conservar sessionID y usar el mecanismo de continuación anunciado. Las versiones con background devuelven mensajes de subagente; idle no equivale a fin de todas las operaciones. [Changelog](https://opencode.ai/changelog/v2.3.0).

No ejecutar comandos de estos ejemplos como sustitutos de herramientas nativas. No instalar hooks globales automáticamente. Las herramientas concretas y el esquema anunciado por el host prevalecen sobre esta guía.
