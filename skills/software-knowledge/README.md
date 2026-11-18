# Software Knowledge

Skill independiente, Python 3.11+, biblioteca estándar. Inspirada en [Zettelkasten](https://zettelkasten.de/posts/building-a-second-brain-and-zettelkasten/), [NapMem](https://arxiv.org/abs/2607.05794) y [OKF](https://github.com/GoogleCloudPlatform/open-knowledge-format). No implementa entrenamiento RL ni afirma reproducir las métricas del artículo.

El [contrato](references/contract.md) desacopla almacenamiento y navegación. Conserva el v1 de backlog-agile-workflow y permite importar sus snapshots explícitos, además de notas Markdown autónomas. No modifica Backlog ni añade paquetes o servidores. El navegador es puro; la captura nativa opt-in invoca exclusivamente lecturas CLI autorizadas.

Ejecutar pruebas desde este directorio:

    python3 -m unittest discover -s tests -p 'test_*.py' -v


## Navegación local

Desde la carpeta de la skill (opciones globales antes del subcomando):

    python3 scripts/knowledge.py --corpus examples/corpus.json overview
    python3 scripts/knowledge.py --corpus examples/corpus.json tracks
    python3 scripts/knowledge.py --corpus examples/corpus.json search "estado terminal"
    python3 scripts/knowledge.py --corpus examples/corpus.json context --anchor execution.terminal
    python3 scripts/knowledge.py --corpus examples/corpus.json --detail full get execution.terminal
    python3 scripts/knowledge.py --corpus examples/corpus.json trace execution.terminal
    python3 scripts/knowledge.py --corpus examples/corpus.json zoom-in execution

Usar --markdown ROOT --project ID para notas autónomas; --corpus V1 --project ID --backlog TASKS_JSON para importar registros observados. El comando snapshot emite todo el corpus explícitamente; el resto de consultas está acotado. Ver [política](references/navigation.md).

## Offline e incremento

    python3 scripts/knowledge.py --corpus examples/corpus.json export /tmp/new-knowledge-bundle
    python3 scripts/knowledge.py --corpus examples/corpus.json diff /tmp/previous-corpus.json

Export crea una carpeta nueva, index por nivel, notas Markdown con enlaces y backlinks, y corpus.json íntegro. El bundle es una vista de solo lectura respecto de la autoridad: para navegarlo con Python, reutilizar corpus.json, no importar sus notas como una nueva autoridad editable. Diff compara snapshots del mismo proyecto y devuelve candidatos de revisión, no elimina notas ni marca STALE automáticamente. No publicar ni exportar datos privados sin permiso.

## Capturar datos nativos Backlog

El anfitrión, tras comprobar versión, proyecto, configuración y permisos, obtiene snapshots con CLI/MCP oficial. Ejemplo (sustituir ID por uno observado):

    backlog task list --json > /tmp/tasks.json
    backlog search "execution" --json > /tmp/search.json
    backlog task view TASK-1 --json > /tmp/task.json
    python3 scripts/knowledge.py --backlog-only --project my-project --backlog /tmp/tasks.json --backlog /tmp/search.json --backlog /tmp/task.json context --anchor task:TASK-1

No usar search como sustituto del contenido completo; para documentos leer doc view por CLI y normalizar el conocimiento v1 explícito. Los archivos indicados pueden contener información privada: no copiarlos a un repositorio o compartirlos sin autorización. Los snapshots con valores contradictorios se rehúsan; repetir lectura, no elegir arbitrariamente. La herramienta no arranca Backlog ni presupone que todos los registros sean visibles.

## Evaluación reproducible

    python3 scripts/evaluate.py examples/corpus.json examples/questions.json

Compara BM25, ranking con intención y expansión activa usando las mismas preguntas/anclas y presupuesto de salida. Devuelve precision@k, recall@k, MRR, nDCG, abstenciones y bytes. El ejemplo es sintético; para calibrar usar preguntas preetiquetadas de un proyecto real, separadas de las usadas para diseñar heurísticas. No entrenar modelos, no declarar éxito de tareas a partir de métricas de recuperación. La CI existente incluye un smoke real con Backlog.md en un workspace desechable.

## Destilación y mantenimiento

    python3 scripts/knowledge.py --corpus examples/corpus.json reconcile /tmp/proposed-atom.json
    python3 scripts/knowledge.py --corpus examples/corpus.json map-candidates

El primer comando compara un corpus v2 de una única nota L1 del mismo proyecto: identidad, afirmación normalizada, ámbito y vecinos léxicos. Solo emite propuestas; el responsable compara evidencias y elige conservar, refinar, enlazar, registrar conflicto o descartar. El segundo descubre contextos etiquetados y átomos aún sin track; no inventa arquitectura ni sintetiza afirmaciones automáticamente. Estas son operaciones de mantenimiento explícitas, no consultas sujetas al presupuesto de navegación.

## Captura de contenido real

Ver [captura nativa](references/backlog-capture.md): captura focalizada por tarea, consulta o documento, y corpus completo activo bajo presupuesto. Reutiliza el JSON derivado localmente con knowledge.py.

## Índice externo y secciones

El índice opcional SQLite/FTS5 vive exclusivamente en la caché del usuario, fuera de Git. Ver [contrato operativo](references/index-cache.md) para uso, privacidad, rutas, recuperación de secciones y benchmark reproducible. Sin --cache, el navegador permanece sin persistencia.
