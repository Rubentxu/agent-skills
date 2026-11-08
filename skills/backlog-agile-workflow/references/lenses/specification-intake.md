# Importación de planificación heredada — solo bajo solicitud expresa

**No es el flujo habitual.** Backlog.md es la única fuente de tracking; no crear, buscar ni sincronizar ROADMAP.md, CHANGELOG.md, listas Markdown, ADR o SPEC administrativos para desarrollar.

1. Si el usuario **aporta archivos heredados y pide migrarlos**, inspeccionarlos como contexto histórico, no como autoridad permanente.
2. Extraer solo resultados pendientes de valor y buscar duplicados en tareas/decisiones nativas de Backlog.md.
3. Registrar decisiones y conocimiento vigente con las capacidades nativas de Backlog.md, sin conservar la fuente original como dependencia viva.
4. Ignorar gates y recibos administrativos antiguos salvo condiciones técnicas o regulatorias reales todavía aplicables.
5. El proyector `spec_projection.py` y sus snapshots efímeros son optativos si el volumen justifica su coste, nunca un gate de trabajo.

**Salida:** tareas/decisiones nativas o KEEP_AS_IS, sin segundo tracking.
