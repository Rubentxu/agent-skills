# Arquitectura, descubrimiento y contexto adaptativo

La skill no investiga código por su cuenta. CogniCode sigue siendo autoridad del análisis estructural y Groma de sus mapas curados; Backlog sigue siendo autoridad del trabajo. Las referencias son derivadas, no prueba de runtime ni autorización. No ejecutar nuevos procesos ni abrir archivos del checkout cuando el contrato CogniCode-only está activo. Si falta un proveedor, indicar UNKNOWN o PARTIAL sin fallback prohibido.

## Fase 9: revisar impacto

    python3 scripts/architecture.py capsule-ref /tmp/capsule.json --project demo --locator handoff-7
    python3 scripts/architecture.py groma-refs /tmp/task-link-input.json --project demo --scope execution
    python3 scripts/knowledge.py --corpus /tmp/knowledge.json architecture-review /tmp/review.json

El primer comando recibe el M5 agent-handoff real de cognicode-diagrams, conserva símbolo, IDs de claims/queries, digest de cápsula, revisión declarada y limitación; no copia aristas. Groma recibe el contrato existente groma-task-link-input: confirmedElementIds son referencias confirmadas por el host, no mapa de ownership. No deduce propiedad de changedFiles. Un path opcional de cápsula debe provenir de una evidencia observada; no se resuelve contra el checkout.

Ejemplo de entrada architecture-review-input:

    {"schemaVersion":1,"kind":"architecture-review-input","project":"demo",
     "revision":"declared-current-revision","intent":"refactor",
     "changedPaths":["src/Runner.kt"],"anchors":["doc:doc-1"],
     "observations":[{"provider":"cognicode","locator":"handoff-7","project":"demo",
       "plane":"static","coverage":"partial","revision":"declared-previous-revision",
       "paths":["src/Runner.kt"]}],
     "bindings":[{"node":"doc:doc-1","provider":"cognicode","locator":"handoff-7"}],
     "findings":[{"node":"doc:doc-1","provider":"cognicode","locator":"handoff-7",
       "kind":"possible-contradiction","reason":"Revisar la garantía de cancelación"}]}

changedPaths proviene de un host autorizado (por ejemplo, Git diff de una operación de entrega separada, nunca de un fallback CogniCode). Se compara por ruta exacta con fuentes Git y modifiedFiles observados; no se infiere dueño por directorio. Incluir rutas antiguas y nuevas si hay renombres. Vincular observaciones por fuente exacta o bindings explícitos; findings requieren binding. El motor identifica candidatos directos, propaga hasta dos saltos por relaciones semánticas y prioriza contratos/invariantes/conflictos. Revisiones iguales son declaraciones, no validación viva; una diferente implica revisar, no marcar stale. El resultado no demuestra ausencia de defectos ni contradicciones. La comparación semántica entre implementación y contrato sigue en el agente con sus proveedores autorizados.

## Fase 10: aprendizaje acumulativo

    python3 scripts/knowledge.py --corpus /tmp/knowledge.json constitution --context execution
    python3 scripts/knowledge.py --corpus /tmp/knowledge.json checkpoint /tmp/checkpoint.json

constitution proyecta reglas críticas existentes y extremos de contradicciones/supersedes dentro de ámbito explícito; conserva claim_state y fuentes. No crea constitución autoritativa. checkpoint acepta knowledge-checkpoint v1, project y candidates (hasta 20 átomos L1) con sources y contexts explícitos; compara identidad y afirmación normalizada, incluye duplicados propuestos en el mismo lote. No admite promoción a verified ni escritura. failed-experiment, anti-pattern y lesson necesitan learning.attempted/outcome/applicability: por qué no funcionó aquí, no prohibición universal. Usar reconcile/map-candidates/diff para mantenimiento, sin crear tarjetas automáticamente. El agente sigue decidiendo con el usuario/proveedor si STORE, REFINE, LINK, CONFLICT, SUPERSEDE o SKIP.

## Fase 11: presupuesto agregado

    python3 scripts/knowledge.py --corpus /tmp/knowledge.json --profile normal context-pack /tmp/questions.json

Entrada:

    {"schemaVersion":1,"kind":"context-pack-input","project":"demo","maxCalls":4,
     "steps":[{"intent":"understand"},{"intent":"verify","anchors":["doc:doc-1"]},
              {"mode":"sections","anchors":["doc:doc-1"],"query":"timeout"}]}

Orientación sin consulta usa perfil y tracks; verify/security usa evidencia por defecto, consultas sin anclajes usan ranking lexical/RRF directo y pasos con anclajes usan navegación activa; mode=context solicita explícitamente expansión por el grafo y sections lista fragmentos de una nota. Deduplicación solo de la representación ya entregada al pack, no de evidencia nunca vista. Quick/normal/deep admiten 2/4/8 operaciones locales y el presupuesto total UTF-8 JSON, no tokens exactos; se declaran pasos omitidos. No hay consultas LLM ni exploración autónoma, y el host conserva límites entre invocaciones. Compatible con --cache salvo mantenimiento/review/checkpoint. evaluate.py compara BM25, RRF, activo y adaptativo con etiquetas y bytes, no rendimiento de agentes.

Evaluación reproducible con documentos existentes (no código):

    python3 skills/software-knowledge/scripts/evaluate_docs.py --root . skills/software-knowledge/examples/documentation-evaluation.json

El manifest define paths seleccionados, etiquetas de relevancia y aristas curadas. Lee únicamente Markdown explícito, no el checkout del proyecto investigado por CogniCode. Registra digest de cada documento. Las ocho preguntas son una primera evaluación de recuperación sobre documentos reales de la colección; no un benchmark de agentes LLM, ni una muestra representativa de otros repositorios.

Decisión de diseño basada en la primera evaluación de ocho documentos: la expansión indiscriminada conservó recall@5 pero penalizó MRR/nDCG y bytes frente al ranking directo. Por ello auto sin anclajes usa ranking, mientras que la navegación activa sigue disponible cuando interesa conocer relaciones, conflictos e impacto. Es una regla determinista revisable, no un algoritmo aprendido ni una afirmación de mejora generalizada.
