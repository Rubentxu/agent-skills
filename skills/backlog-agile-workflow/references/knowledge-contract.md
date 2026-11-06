# Contrato de conocimiento — Backlog CLI a OKF v0.2

## Fuente de verdad

La CLI/MCP de Backlog.md es la autoridad para tareas, documentos y decisiones. Los glosarios por bounded context son documentos Backlog en glossary/<context>, con etiquetas kind:term, ctx:<context> y term:<context.concept>. Groma es autoridad opcional sobre componentes observados. El grafo semántico y el bundle OKF son **proyecciones**, no nuevas bases de datos.

La versión actual de la CLI admite solo readme, guide, specification y other como tipos de documento. Los tipos lógicos research, invariant, risk, algorithm o term se expresan como etiquetas kind:*. Un adaptador autorizado normaliza lecturas de CLI en un JSON temporal; no se manipula directamente el frontmatter de los documentos de Backlog.

## Comandos previos (según ayuda de CLI instalada)

    backlog instructions overview
    backlog doc create --help
    backlog doc update --help
    backlog doc list --plain
    backlog doc search "execution.run"
    backlog doc view doc-12
    backlog decision list --json
    backlog task view TASK-34 --json

Tras crear un documento, usar el ID y la ruta **reales** emitidos por CLI. Para asociar el documento a una tarea: backlog task edit TASK-34 --add-doc "<ruta-observada>". Antes de actualizar --tags o --content, recuperar y conservar valores existentes: ambas opciones reemplazan su campo.

## Snapshot efímero knowledge-corpus v1

El archivo examples/knowledge-corpus.json es un corpus sintético ilustrativo. Su esquema normalizado:

- schemaVersion: 1; kind: knowledge-corpus.
- terms: objetos con id estable context.concept, context, label, definition, status opcional (proposed|validated|deprecated), aliases opcional.
- documents: objetos con id nativo doc-N, title, type nativo, content, tags, status OKF opcional (draft|stable|deprecated), relations opcional y sources opcional.
- tags: incluir por documento al menos ctx:<context> y term:<context.concept> de términos existentes. Al etiquetar documentos multicontexto, incluir ctx por cada contexto.
- relations: cada relación tiene predicate, target (ID de documento o término), terms (lista de términos que aparecen también en tags de su documento).
- predicate: supports, contradicts, investigates, threatens, constrains, motivates, supersedes, implements, affects, validates, maps_to o related.
- terms se derivan de los documentos Backlog del glosario: la instantánea temporal no supone una segunda autoridad.
- sources son referencias opcionales observadas; no inventar provenance, verified, generated ni fechas.

El validador exige términos y relaciones explícitos. Una búsqueda textual no justifica automáticamente una relación. La instantánea incompleta no demuestra ausencia de conocimiento y debe indicarse cuando se presenten conclusiones.

## Herramienta pura (Python estándar)

    python3 scripts/knowledge_graph.py examples/knowledge-corpus.json
    python3 scripts/knowledge_graph.py examples/knowledge-corpus.json --mode graph
    python3 scripts/knowledge_graph.py examples/knowledge-corpus.json --mode export --output /tmp/new-okf-bundle

La validación rechaza etiquetas sin vocabulario, relaciones huérfanas, IDs malformados y duplicados. El grafo se deriva de referencias explícitas y se ordena de modo determinista. La exportación genera un **directorio nuevo** con index.md, concepts/doc-N.md y glossary/context.concept.md. Los metadatos YAML OKF se serializan mediante valores JSON válidos en YAML 1.2; x_domain y x_backlog son **extensiones del productor**, no partes normativas de Google OKF. Links Markdown absolutos son relativos a la raíz del bundle.

El script no ejecuta CLI/Git/Groma, no escribe archivos Backlog, no abre red y no presume decisiones aceptadas. Ninguna exportación se publica automáticamente. Nunca migrar documentos privados, cambiar la política Git o reescribir un registro existente sin autorización.

## Evolución posterior

Adaptador CLI real en fixtures efímeros; evaluación de campos frontmatter extensibles upstream; recuperación de subgrafos acotada a tareas activas; reconciliación entre documentación y código observado. No añadir base de datos ni indexador hasta que la necesidad esté medida.
