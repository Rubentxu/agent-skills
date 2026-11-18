# Índice externo opcional

SQLite FTS5 pertenece a una proyección desechable local. No es autoridad, servicio, memoria de conversaciones ni requisito de instalación. No se crea ningún fichero SQLite dentro del proyecto o repositorio. El destino por defecto es ~/.cache/software-knowledge/index-v1 o el XDG_CACHE_HOME absoluto del usuario; se rehúsa si cae dentro de cualquier checkout Git o la raíz Markdown seleccionada. Las carpetas propias son privadas (0700) y las bases 0600 en sistemas POSIX; se rechazan enlaces simbólicos finales. Usar un home/cache confiable: estas comprobaciones no aíslan procesos maliciosos del mismo usuario. Los datos son texto local derivado, no cifrado. No indexar secretos; conservar y borrar según política del equipo.

## Uso

    python3 scripts/knowledge.py --corpus /tmp/knowledge.json --project my-project --cache index-status
    python3 scripts/knowledge.py --corpus /tmp/knowledge.json --project my-project --cache search "run lifecycle"
    python3 scripts/knowledge.py --corpus /tmp/knowledge.json --project my-project --cache context --anchor task:TASK-1
    python3 scripts/knowledge.py --markdown /repo/knowledge --project my-project --cache search "invariant"

El identificador explícito del proyecto, tipo de proveedor, ruta canónica y versión de índice determinan el espacio de caché. Cada consulta valida la disponibilidad de la fuente y su hash SHA-256 (snapshot bytes completos o corpus Markdown normalizado); nunca usa únicamente mtime. Un hit de snapshot evita decodificar y reconstruir el corpus. Para Markdown aún se leen/parsean las notas para calcular el fingerprint; solo cambia lo indexado. En refresh la transacción actualiza nodos y aristas con hashes distintos y retira los ausentes de la proyección, no de la fuente. Un snapshot parcial sigue partial y no implica borrado autoritativo. Consultas comparten transacción con refresh; escrituras concurrentes esperan como máximo el límite SQLite. Un input inválido no entrega resultados obsoletos. Un índice corrupto o FTS5 ausente requiere borrar/reconstruir explícitamente o usar el modo sin --cache. No cambiar configuración del repositorio. index-status informa ruta, recuentos y reutilización; borrar esa base cerrada libera su contenido. No se ejecuta limpieza automática.

La búsqueda usa BM25 de FTS5 con pesos de campos e intent ranking RRF. Puede diferir de BM25 Python (normalización y puntuación distintas), mantiene prioridad de ID/alias y filtros exactos. Los candidatos y tokens de consulta se acotan (512 nodos, 64 términos únicos); candidate_cut indica truncamiento, no respuesta exhaustiva. La navegación carga aristas y nodos consultados desde tablas indexadas y conserva el mismo contrato y presupuestos que el modo en memoria. El modo puro sigue disponible y es predeterminado. Las operaciones de mantenimiento y snapshots completos leen fuentes originales sin caché; para overlays Backlog primero genera snapshot explícito.

## Secciones exactas

    python3 scripts/knowledge.py --corpus /tmp/knowledge.json --project my-project --cache sections doc:doc-1 --query "recovery"
    python3 scripts/knowledge.py --corpus /tmp/knowledge.json --project my-project --cache section doc:doc-1 SECTION_ID

sections devuelve índice, títulos, offsets e identificadores de secciones, no el contenido completo. Las secciones se agrupan por encabezados y párrafos; mantienen bloques cercados completos. section recupera el fragmento exacto y referencias de la nota. ID depende de offsets y texto: si cambia, volver a listar. Los offsets son puntos de código Unicode en el cuerpo del corpus (no bytes del fichero). Un párrafo/bloque indivisible demasiado grande puede quedar omitido bajo presupuesto; no se trunca ni pretende ser un resumen. La búsqueda de secciones es lexical local a una nota. Los nodos metadata-only devuelven capture-doc, no contenido ficticio.

## Medición

    python3 scripts/benchmark_index.py --size 1000 --repeat 3

Mide tiempo real (con tracemalloc) y pico de asignaciones Python, tamaño de índice y trabajo de refresh. Compara carga en memoria, índice frío, hit caliente y cambio de un átomo. No compara memoria nativa SQLite ni representa corpus o tareas reales. No hay umbral temporal arbitrario en CI: se confrontan recuentos y resultados. Para demostrar valor en proyectos reales, usar corpus y preguntas etiquetadas, medir latencia, calidad de recuperación, consultas y consumo real de contexto.
