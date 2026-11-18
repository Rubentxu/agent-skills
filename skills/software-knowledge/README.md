# Software Knowledge

Skill independiente, Python 3.11+, biblioteca estándar. Inspirada en [Zettelkasten](https://zettelkasten.de/posts/building-a-second-brain-and-zettelkasten/), [NapMem](https://arxiv.org/abs/2607.05794) y [OKF](https://github.com/GoogleCloudPlatform/open-knowledge-format). No implementa entrenamiento RL ni afirma reproducir las métricas del artículo.

El [contrato](references/contract.md) desacopla almacenamiento y navegación. Conserva el v1 de backlog-agile-workflow y permite importar sus snapshots explícitos, además de notas Markdown autónomas. No modifica Backlog, ni ejecuta herramientas externas, ni añade paquetes o servidores.

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
