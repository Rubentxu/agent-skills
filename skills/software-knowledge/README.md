# Software Knowledge

Skill independiente, Python 3.11+, biblioteca estándar. Inspirada en [Zettelkasten](https://zettelkasten.de/posts/building-a-second-brain-and-zettelkasten/), [NapMem](https://arxiv.org/abs/2607.05794) y [OKF](https://github.com/GoogleCloudPlatform/open-knowledge-format). No implementa entrenamiento RL ni afirma reproducir las métricas del artículo.

El [contrato](references/contract.md) desacopla almacenamiento y navegación. Conserva el v1 de backlog-agile-workflow y permite importar sus snapshots explícitos, además de notas Markdown autónomas. No modifica Backlog, ni ejecuta herramientas externas, ni añade paquetes o servidores.

Ejecutar pruebas desde este directorio:

    python3 -m unittest discover -s tests -p 'test_*.py' -v

