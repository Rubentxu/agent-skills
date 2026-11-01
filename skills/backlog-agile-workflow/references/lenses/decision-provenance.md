# Lente: decisiones nativas de Backlog y cadena de autoridad

**Pregunta:** ¿qué decidió realmente la persona, en qué mensaje, y sigue vigente?

1. Leer `backlog instructions overview`, `backlog decision list --json` (todas las páginas), y el detalle de los candidatos con `backlog decision view <id> --json`. Consultar primero `backlog --help` y `backlog decision --help` reales. Búsqueda por tarea/refs antes de crear.
2. Para una nueva decisión, comprobar que existe manifestación humana **explícita**. Si solo hay hipótesis del agente, presentar propuesta y usar estado `proposed`, nunca `accepted` automático.
3. Usar `backlog decision create "Título" --context "Motivo; Origin: provider/session/message/timestamp/digest" --decision "..." --consequences "..." --alternatives "..."` solo con autorización. La CLI es dueña del archivo; no escribir frontmatter.
4. Guardar puntero privado, fecha y digest, no una transcripción. No crear ID de mensaje si el host no lo proporciona. Recoger mensaje original por canal autorizado y adaptador independiente para comparar con `authority_context.py`.
5. En una decisión sustituida, revisar `backlog decision edit <id> -s superseded --superseded-by <otro-id>` (flags reales según versión) **solo** tras permiso humano. Verificar que el sucesor existe. Nunca borrar ni archivar por inercia.
6. Si dos decisiones o fuentes son contradictorias, `CONFLICTED`; si falta el original, `UNVERIFIED`; si está sustituida, `STALE`. Ninguna se ejecuta como autoridad humana.

**Criterio de cierre:** fuente original consultable + identidad constatada + decisión Backlog + alcance + estado o incertidumbre explícita. El proyector verifica consistencia de snapshots, **no** identidad criptográfica del actor, autenticidad del host ni permiso de ejecución.
