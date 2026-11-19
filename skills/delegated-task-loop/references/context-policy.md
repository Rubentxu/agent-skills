# Contexto mínimo bidireccional

Presupuestos iniciales experimentales de transferencia (tokens estimados, no ventana total): estado del supervisor 3000, brief worker 4000, resultado 700, checkpoint 1000, solicitud Goldfish 2000, summary de revisión 500. Si el host no mide tokens, usar bytes observados y declarar la unidad; no convertir bytes a tokens exactos. Límites blandos: nunca omitir políticas, AC o evidencia indispensable para cumplirlos.

- Supervisor: objetivo, binding, tarea/attempt activos, revisión, presupuesto, referencias de decisiones, próximo paso. No importar transcripts, código completo, logs ni todo el tablero.
- Worker: objetivo y AC efectivos, DoD, alcance, políticas por repo, revisión completa, referencias del handoff y pack. Recuperar just-in-time a partir de anclas; usar quick/normal/deep del proveedor. Sin permisos implícitos.
- Goldfish: solicitud independiente según su contrato; target, digest, revisión, rúbrica y fuentes autorizadas, sin razonamiento del autor.
- En respuesta: campos estructurados y referencias a evidencia recuperable; no repetir el brief.

Al finalizar cada tarea: sustituir la proyección operativa del supervisor (rolling checkpoint), no concatenar resúmenes. Si hay presión de contexto, guardar checkpoint antes de usar compactación/reanudación del host. Un fichero no reduce por sí solo el contexto ya cargado. No cargar métricas por defecto ni prometer control de tokens si el host no lo ofrece.

Aprendizaje durable solo mediante software-knowledge: contrastar fuente, aplicabilidad y duplicados antes de persistir. No registrar cada evento como nota.
