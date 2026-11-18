# Knowledge corpus v2

Un corpus explícito JSON tiene schemaVersion 2, kind knowledge-corpus, project (ID estable explícito), coverage partial o declared-complete, arrays nodes y edges. La cobertura declarada no es una prueba de exhaustividad.

Cada nodo tiene id único dentro del proyecto, level L0/L1/L2/L3, kind, title, summary, body opcional, aliases, contexts, tags, claim_state y sources. La identidad global es el par (project, id), no el título ni la ruta. No se asignan equivalencias entre proyectos. L0 fuentes y evidencias, L1 afirmaciones atómicas (invariantes, términos, contratos, decisiones, algoritmos, normas, riesgos, casos de uso), L2 tracks o notas de estructura y L3 perfil orientador. Una tarea nativa se proyecta como L0; no se inventa su resultado ni se modifica su autoridad.

Sources contienen provider y locator, y opcionalmente revision y digest observados. Un pin es una referencia, no una certificación. Claim_state diferencia unknown, proposed, observed, inferred, verified, contradicted, stale, superseded; verified exige fuente pero el validador no comprueba su veracidad. Backlog accepted no equivale a aprobación humana corroborada.

Edges contienen from, to, predicate y reason opcional. Contains desciende de nivel; las aristas semánticas admiten ciclos. Depends_on proyecta exclusivamente dependencias nativas explícitas y no convierte enlaces de conocimiento en dependencias de trabajo. Las relaciones no resueltas fallan en un corpus local; una fuente externa se mantiene como locator, no como nodo inventado.

## Backlog

El adaptador acepta knowledge-corpus v1 normalizado (contrato anterior) y envelopes task-list, decision-list, task-view, decision-view y search schemaVersion 1 observados. Documentos se obtienen por CLI/MCP autorizado y se normalizan; doc list/view no se presupone JSON. Nunca editar Markdown nativo. Las proyecciones son parciales, no se infiere ausencia. Search aporta metadatos, no cuerpo de documentos. Las vistas enriquecen snapshots compatibles; conflictos de título/campos se rechazan y requieren recaptura. Se enlazan rutas documentation exactamente iguales a path de un documento observado y dependencias directas resueltas. Las referencias sin resolver permanecen como datos nativos, no aristas inventadas. IDs de documentos se conservan como doc:ID y términos como term:ID. Los datos nativos no se convierten en aprobación. Los campos y relaciones no soportados requieren reconciliación explícita.

## Markdown autónomo

Seleccionar una raíz dedicada, no el checkout entero. Cada nota usa front matter OKF con valores JSON por línea (subconjunto YAML 1.2), type/title/tags y extensión x_knowledge con id, level, summary, sources, contexts, aliases, claim_state y relations (predicate/to/reason). No se pretende parsear YAML arbitrario. Los enlaces Markdown relativos permiten navegación humana; las relaciones explícitas son las únicas aristas semánticas. No seguir enlaces simbólicos. No publicar automáticamente.


## Ubicación autoritativa

Aplicar el [Knowledge Home privado](knowledge-home.md): proveedor y ubicación son independientes del corpus. Backlog en Home Repo existente prevalece; no crear Markdown paralelo. Markdown autónomo se conserva en raíz privada elegida, XDG por defecto sin Home Repo. JSON derivado y SQLite nunca son autoridad ni se publican en Git del producto.
