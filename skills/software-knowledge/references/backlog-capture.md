# Captura nativa Backlog.md

capture_backlog.py es el único adaptador que inicia procesos externos. Es opt-in: raíz y proyecto explícitos, CLI instalada y --confirm-cli-read tras autorización real del host. Este flag no concede permisos. Comprueba marcador de configuración de raíz, remoteOperations=false o filesystemOnly=true; no modifica configuración ni instala herramientas. La CLI puede tener comportamiento propio (migraciones, enlaces simbólicos, etc.); seleccionar una raíz confiable y usar controles del host si es necesario. Si se necesita remoto, el anfitrión puede proporcionar snapshots autorizados al modo existente; este capturador no lo habilita.

## Captura enfocada

    python3 scripts/capture_backlog.py --root /repo --project my-project \
      --confirm-cli-read --task TASK-1 --query "event ordering" > /tmp/knowledge.json

    python3 scripts/knowledge.py --corpus /tmp/knowledge.json context --anchor task:TASK-1

La lista de documentos CLI se contrasta con search --type document --json sin consulta. No se infiere un documento de un nombre de archivo ni se leen directamente registros. La vista de tarea aporta documentación por ruta observada; --query selecciona candidatos por búsqueda nativa incluyendo cuerpo. --doc permite ID explícito, --all-docs solicita cuerpos de todos los documentos activos, --include-board añade resúmenes de tareas, --decision solicita decisión completa por decision view --json cuando la versión lo admite. Se conserva el listado de decisiones sin elevar status a aprobación. No se enumeran documentos archivados.

--max-docs (32 por defecto, hasta 256) prioriza IDs explícitos y documentos de tareas; si estos no caben, se rehúsa, no se omiten silenciosamente. --max-commands y --timeout limitan procesos (80 y 120 s por defecto; máximo 30 s por proceso). Captura stdout/stderr en temporales, rechaza salidas grandes, errores y diagnósticos no vacíos; no trunca cuerpos. El stdout final es un corpus v2 de hasta 16 MiB, no un paquete de contexto para pegar en la conversación. Se conserva el contenido observado y digest SHA-256 del stdout de doc view (no el hash certificado del archivo). El resumen es un extracto exacto corto o el título, no una nueva afirmación. El corpus sigue partial, lista cuerpos omitidos y metadata-only. El inventario se contrasta de nuevo tras hidratar; no es captura atómica. Una fuente del CLI no prueba la garantía que describe.

## Relaciones y pirámide

Tags nativos kind:track y kind:profile proyectan L2 y L3; kind:term, term:context.concept único resuelve el alias y permite enlaces about por etiqueta explícita. Las identidades siguen siendo doc:doc-N. No se infieren bounded contexts ni se fusionan términos ambiguos.

Para relaciones explícitas, el agente puede proponer un bloque en el cuerpo gestionado por CLI:

    <!-- knowledge-links:v1 -->
    [{"predicate":"contains","to":"doc:doc-2","reason":"Garantía de ejecución"}]
    <!-- /knowledge-links:v1 -->

IDs deben ser observados; enlaces a nodos ausentes se registran como no resueltos. El bloque es JSON sin ejecución, se ignoran ejemplos cercados por backticks o tildes, no se permite depends_on en este bloque. Las dependencias de trabajo solo provienen de Backlog.md. Documentos sin bloque no se reescriben ni se les inventan aristas. Para actualizar contenido usar únicamente CLI/MCP autorizada preservando el cuerpo existente. No hacer publicación automática de corpus privados.
