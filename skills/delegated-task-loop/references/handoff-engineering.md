# Handoff Engineering: supervisor responsable de contexto

El supervisor hace Resolve → Ground → Disambiguate → Plan → Project → Validate → Delegate. Lee tarea real, políticas aplicables (incluidas AGENTS.md anidadas), anclas y revisiones; comprueba que el trabajo no sea ambiguo mediante readiness técnica de backlog-agile-workflow; usa plan público de delivery-first-testing y hechos seleccionados de software-knowledge. No trasladar una discrepancia material al implementador ni retrasar el fast path con rondas. Si el trabajo es trivial, pocas consultas bastan. Obtener los digests de fuentes originales autorizadas. No copiar conversaciones ni crear autoridad. El compilador valida cierres estructurales, no semántica.

## Envelope v2

Mantiene identidad y campos v1. Añade briefRevision, taskDigest, readinessRef, effectivePolicies [{id,rule,sourceRef,sourceDigest}], verifiedFacts (proyección static de proveedor de conocimiento), liveResources, verificationPlan, criterionOwners, nonGoals, contingencies, executionPolicy y openQuestions. Las preguntas materiales deben estar resueltas; las decisiones internas reversibles corresponden al worker. Las reglas deben ser las aplicables, no solo rutas; el receptor sigue obligado a políticas originales. Un plan refiere a su digest del proveedor, proyecta workerChecks y supervisorChecks {id,repository,argv,cwd,covers}; cada criterio tiene dueño y comprobación en su etapa. Los comandos son datos, solo ejecutar tras preflight del host. No inventar selectores ni permisos. Las verificaciones administrativas/aceptación son del supervisor, no del worker.

liveResources {status reconciled,observedAt,evidenceRef,resources: [{id,kind,operationKey,originAttempt,state,identityRef,evidenceRef,verifiedAt,effects,adoption,resultRef}]} se verifica en el entorno real: running/completed/failed, observe-only/manage-existing. Sin inventario resuelto, reconciliar primero. No volver a lanzar operación viva. Nunca interpretar timestamp como liveness actual.

executionPolicy contiene modelProfile economy/balanced/deep, explorationBudgetMinutes, outputMode compact, publication forbidden/explicit-authority, administrativeWork delegated. El host confirma modelo y permisos; si no puede, explicita limitación. Contingencies: anchorMissing ask-supervisor, newRisk request-plan-amendment, backgroundWork report-pending, ambiguity ask-supervisor, stopWhen claro.

## Comunicación cerrada

Validar envelope con delegation_contract.py envelope FILE. Para trabajo complejo solicitar receipt v2 con identidad, briefRevision, briefDigest, status UNDERSTOOD/NEEDS_CONTEXT/CONFLICT/BLOCKED, firstAction (solo si entendido) y questions. No exigir ceremonia a corrección trivial. El supervisor resuelve preguntas con una respuesta precisa. Si cambia contexto, amendment v2 contiene identidad, baseRevision/baseDigest/newRevision/reason/changes. Solo permite facts, resources, plan, pack o presupuesto/modelo; no cambios de autoridad, criterio, alcance ni publicación. El nuevo digest atribuye todas las respuestas; resultados antiguos no se aceptan contra versión nueva. Cambio material requiere un brief autorizado nuevo. No repetir todo el prompt si basta un delta; mantener versión efectiva en estado privado.

PENDING no es aceptación ni fin del escritor. El worker comunica operación y pendientes, el supervisor conserva reserva y espera señal real o revalida. En READY_FOR_REVIEW solo criterios del worker deben estar pass; los del supervisor se verifican antes de Done. Contradecir hechos exige reconciliación, no falsa entrega.

Golden path: preparar anclajes y hechos → plan → envelope v2 → native fresh → resultado → comprobar revisión/evidencia/oráculo asignado → decisión → registro autorizado. No usar un revisor para cada brief. Goldfish conserva su propia solicitud de target/pregunta/fuentes aisladas, no recibe razonamiento del implementador. Steward requiere permiso acotado y decisión del supervisor; no utilizar un implementer para gestionar tablero.

El [journal](run-state.md) conserva reserva PENDING y exige reconciliación de recursos. Para trabajo auxiliar usar el contrato [Steward](steward.md), no el mismo brief de implementación. Goldfish mantiene contrato independiente.

## Ensamblado de proveedores

Usar handoff_compiler.py por stdin: implementer-handoff-input v1, draft v2 sin taskDigest/verificationPlan/verifiedFacts, authorityHandoff, authorityReceipt actualizado (incluye taskDigest/sourceRevision), readiness, plans [{ref,plan}], planBundleRef privado, factAssessment opcional (null si no disponible), budgetDecisionRef nullable. El ensamblador cruza identidad y digest de tarea, revision por repo, estado de plan y criterios; presupuesto excedido/desconocido requiere decisión explícita, no omisión. Devuelve envelope, briefDigest y verificationPlanBundle (refs y digests) para guardar fuera del checkout. No autentica documentos ni decide semántica. Si faltan capacidades del proveedor, declarar degradación y preparar manualmente el contrato con fuentes reales; nunca fabricar receipts. Una revisión global obligatoria puede incluirse sin falsa selección reducida.

Para continuidad tras relevo, aplicar [Baton](endurance-relay.md), envelope v2 con pacing y continuity, conservar todos los AC/DoD y base original. Fresh Eyes recibe primero estado/pendientes y luego experimentos; no ocultar restricciones ni hechos críticos.
