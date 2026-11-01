# Lente: decisiones nativas de Backlog y cadena de autoridad

**Pregunta:** ¿qué decidió realmente la persona, en qué mensaje, y sigue vigente?

1. Leer `backlog instructions overview` y `backlog decision list --json` (todas las páginas). Usar `backlog decision view <id> --json` **solo** si `backlog decision --help` realmente anuncia `view`; Backlog.md 1.55.3 no lo tiene. Consultar ayuda local antes de operar y buscar duplicados por tarea/refs.
2. Para una nueva decisión, comprobar que existe manifestación humana **explícita**. Si solo hay hipótesis del agente, presentar propuesta y usar estado `proposed`, nunca `accepted` automático.
3. Verificar `backlog decision create --help` **en la versión instalada**. Como mínimo, usar `backlog decision create "Título"` si está disponible. Añadir `--context`, `--decision`, `--consequences`, `--alternatives` o `-s` únicamente si la ayuda real los publica; Backlog.md 1.55.3 no acepta `--context` aunque aparezca en la documentación de main. Si no se puede registrar el pin mediante CLI, mantener la decisión como propuesta no acreditada y pedir actualización/autorización; nunca editar el Markdown manualmente.
4. Guardar puntero privado, fecha y digest, no una transcripción. No crear ID de mensaje si el host no lo proporciona. Recoger mensaje original por canal autorizado y adaptador independiente para comparar con `authority_context.py`.
5. En una decisión sustituida, revisar `backlog decision edit <id> -s superseded --superseded-by <otro-id>` (flags reales según versión) **solo** tras permiso humano. Verificar que el sucesor existe. Nunca borrar ni archivar por inercia.
6. Si dos decisiones o fuentes son contradictorias, `CONFLICTED`; si falta el original, `UNVERIFIED`; si está sustituida, `STALE`. Ninguna se ejecuta como autoridad humana.

**Criterio de cierre:** fuente original consultable + identidad constatada + decisión Backlog + alcance + estado o incertidumbre explícita. El proyector verifica consistencia de snapshots, **no** identidad criptográfica del actor, autenticidad del host ni permiso de ejecución.
