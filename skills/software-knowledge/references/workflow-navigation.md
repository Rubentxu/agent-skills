# Navegación HATEOAS de la skill

Mismo patrón de la colección: scripts/affordances.py recibe estado explícito, consulta references/lens-registry.json y skill-registry.json, devuelve decision, lenses y _links con rel/why/href. Router puro: no inspecciona checkout, no ejecuta comandos ni cambia fuentes. El estado expresa observaciones del host, no certificaciones. No se comparte código entre skills; cada skill es instalable por separado.

    printf '%s\n' '{"intent":"verify","project":"demo","basis":"observed","corpus":"ready","source":"snapshot","anchors":["doc:doc-1"]}' | python3 scripts/affordances.py -

catalog muestra lentes sin proyecto. discover pide inspección de fuentes. Los intents understand/implement/refactor/verify/debug/security/architecture seleccionan contexto, ranking directo u orientación según query y anchors. index opt-in con reuse_index=true. architecture-review, checkpoint, maintain solo proponen cambios; context-pack y federation requieren inputs explícitos, evaluate distingue métodos de medición. constitution requiere ámbito; para context sin anclaje consulta la guía. mode read/propose/apply documenta la intención, no habilita efectos. Unknown/stale basis pide refresh. No asumir que el corpus está completo. Un corpus ready no requiere proveedor instalado.

Los campos de sesión son intent, project, basis, corpus, source, cli, backlog_project, remote_policy, mode, query, anchors, available_skills, read_authorized, input_ready, selected_link, reuse_index. Los valores de disponibilidad/cobertura se observan por medios autorizados. La captura nativa requiere cli=available, backlog_project=initialized, remote_policy=local-only, read_authorized=true y un alcance seleccionado por el host. No cambiar config para satisfacer el router. Para proveedores ausentes usar entradas explícitas autorizadas, no fallback de código.

Las operaciones estructuradas especifican script local, comando semántico y argumentos; no son líneas de shell ni permiso de ejecución. El host aporta rutas de corpus, raíz, inputs, presupuesto y demás parámetros según ayuda y lente; nunca interpreta texto externo como comando. No incluir rutas, credenciales ni argumentos de ejecución arbitrarios en el estado. Solo recomendar delegate-skill si está confirmada en available_skills.

## Dos niveles complementarios

1. Workflow: rel/why/href selecciona qué aprender o hacer, según estado.
2. Corpus: los _links de retrieval/sections conservan action e identidad (contrato compatible). Para seguir un enlace, pasar intent=follow y selected_link exactamente como se recibió; el router valida la operación conocida y verifica las precondiciones de capture-doc. Los demás enlaces necesitan corpus ready. El host verifica que el enlace procede del corpus actual y que el ID sigue existiendo; el router no lo lee.

No eliminar enlaces antiguos ni imponer otro paso obligatorio para cada get; usar las affordances para orientar, decidir y resolver cambios de estado. La selección devuelve como máximo dos lentes. Si una lente futura está planned, no se recomienda. La navegación no escribe notas, no instala dependencias ni crea tareas.

La captura de Backlog requiere una consulta no vacía o IDs nativos observados task:TASK-N/doc:doc-N; no propone captura global. Markdown y snapshots se validan sin CLI Backlog tras autorización de lectura. Verificación/seguridad solicitan detail=evidence. La orientación de un corpus listo no vuelve a descubrirlo. Evaluar observaciones de agentes no exige un corpus instalado.

Para persistencia, comenzar por locate-home e initialize-home siguiendo [Knowledge Home](knowledge-home.md). Campos adicionales: home_state (unknown/unbound/bound/invalid), placement (unknown/home-repo/user-local/git-ignored), home_candidate (unknown/absent/backlog-ready/present), placement_confirmed (bool). Un Backlog existente en Home Repo tiene prioridad; no proponer otra base si el estado observado es backlog-ready. El host valida ruta/proveedor y privacidad antes de init; no ejecutar automáticamente. Un binding inválido requiere revisión. Con home_state=bound, los enlaces de operaciones knowledge/capture transportan la identidad home para no volver al checkout.
