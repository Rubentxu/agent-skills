# Lente: recuperar memoria del propietario sin vacuuming

**Pregunta:** ¿qué decisiones aprobadas afectan a este trabajo?

1. Obtener `backlog decision list --json` completo y `task view --json`; identificar referencias a decisiones y, si Groma está disponible, el propietario del archivo vía `groma view <ruta>` en modo lectura.
2. Obtener snapshots de mensaje verificables desde el anfitrión. Si faltan, devolver `UNVERIFIED` y pedir comprobación, no inventar una decisión.
3. `authority_context.py claims.json messages.json decisions.json` valida coherencia. `owner_memory.py recall claims.json messages.json decisions.json --scope <id-del-componente> --decision-id <id>` devuelve **máximo cinco** referencias útiles, sin transcripciones ni Markdown propietario.
4. No recopilar automáticamente todas las conversaciones: guardar y referenciar solo decisiones aceptadas; los agentes acceden al mensaje privado original cuando sea imprescindible.
5. La similitud de títulos no acredita identidad; un owner de Groma es una pista de alcance, no autoriza modificaciones.
6. Los agentes pueden producir votos `useful|misleading|stale`; `owner_memory.py feedback assessment.json votes.json` devuelve propuestas de revisión. Los votos no cambian decisiones, política ni permisos.

**Degradación:** sin CLI/snapshot verificado no afirmar que la memoria cubre todo el historial; sin Groma usar IDs explícitos de tarea/decisión. Sin índices el agente aún puede operar, sin suponer aprobaciones.

### Adaptador Claude Code: vínculos documentales, no autoridad

El plugin `backlog-context` puede consultar automáticamente tareas y decisiones **nativas** de Backlog.md al leer un archivo. Solo conecta referencias exactas de tareas con IDs de decisiones y muestra el estado documental, sin mostrar contenido. Esto **no ejecuta** `owner_memory.py` ni eleva una decisión a `VERIFIED`, porque el hook no recibe un origen humano autenticado. Para aplicar una decisión, recuperar y comprobar el mensaje original usando `decision-provenance`; si falta, mantener `UNVERIFIED`. La búsqueda automática se puede desactivar mediante `BACKLOG_CONTEXT_DECISIONS=off`.
