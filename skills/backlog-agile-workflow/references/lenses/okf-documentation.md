# Google Open Knowledge Format 0.2 — documentos interoperables

**Objetivo:** intercambiar conocimiento sin sustituir la autoridad de Backlog.md.

1. Consultar la especificación canónica https://github.com/GoogleCloudPlatform/open-knowledge-format/blob/main/SPEC.md. OKF requiere type en YAML, admite tags, sources, verified, generated, status, extensiones y enlaces Markdown bundle-relativos.
2. Crear y editar documentos únicamente por Backlog CLI/MCP; los tipos nativos no son extensibles. Usar tags kind:* y contenido. No editar su frontmatter fuera de la CLI.
3. Obtener una instantánea efímera normalizada a partir de documentos, glosarios, tareas y decisiones observadas. Véase knowledge-contract.md.
4. Validar: python3 scripts/knowledge_graph.py examples/knowledge-corpus.json
5. Proyectar el grafo sin escribir: python3 scripts/knowledge_graph.py examples/knowledge-corpus.json --mode graph
6. Exportar solo cuando se solicite: python3 scripts/knowledge_graph.py examples/knowledge-corpus.json --mode export --output /tmp/new-okf-bundle
7. La exportación escribe un directorio nuevo y crea index.md y conceptos vinculados; no sobreescribe. No inventar generated, verified, fuente, actor ni fecha. No compartir información privada automáticamente.
8. Groma OKF describe arquitectura real; el bundle semántico es un derivado separado.

**Salida:** bundle OKF v0.2 con glosario y enlaces, sin duplicar gobernanza.
