# Hechos con procedencia y reutilización selectiva

El supervisor entrega hechos ya contrastados, evidencia y pins de todas las fuentes relevantes. No volver a investigar mientras el ámbito y los pins vigentes coincidan y no exista contradicción; la coincidencia es solo candidata a reutilización. El agente verifica permisos, seguridad y runtime en el momento de actuar. No promover un resumen a verdad ni utilizar un digest como autoridad. Si aparece un consumidor no contemplado, revalidar la selección.

verified_facts.py toma fact-reuse-input v1 por stdin: project, facts {id,claim,scope,sourcePins:[{ref,digest}],evidenceRef,kind static/runtime/permission/security}, currentSources [{ref,digest}], contradictedIds. Digests SHA-256 calculados desde fuentes reales autorizadas, nunca desde el propio resumen. Salida REUSE_CANDIDATE, REVALIDATE, CONTRADICTED o RECHECK_ON_USE. No ejecuta proveedores, no copia corpus. Seleccionar hechos estáticos mínimos para el brief y reportar contradicciones concretas.

El worker devuelve solo nuevas observaciones, decisiones candidatas y referencias, no redacta memoria. Un Steward autorizado usa checkpoint/reconcile con el contrato existente y aplica STORE/REFINE/LINK/CONFLICT/SUPERSEDE/SKIP; no crear otra base, duplicar Backlog ni promover hipótesis a verified. Persistir aprendizaje durable en el Knowledge Home seleccionado, no en el producto.
