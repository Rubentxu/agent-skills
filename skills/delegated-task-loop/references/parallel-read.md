# Paralelismo prudente, primero sin escritores

Por defecto, ejecutar una sola tarea escritora. El journal protege únicamente un escritor local cooperativo. No iniciar varios implementadores que modifiquen código o recursos compartidos: la elección de paths distintos no prueba independencia (build, cachés, contratos, ramas, servicios). El paralelismo de escritura queda deshabilitado hasta demostrar aislamiento y reservas por ámbito que no colisionen.

Se admite fan-out pequeño de preguntas independientes de solo lectura cuando exista valor concreto: localizar una API, contrastar un contrato, investigar dos hipótesis. Primero probar recuperación directa con software-knowledge; no convertir cada consulta en otro agente. Goldfish sigue su propia rúbrica y perfiles, no este fan-out.

Obtener tareas listas mediante backlog-agile-workflow si se trata de distintas tareas, no inventar prioridades ni calcular un segundo grafo. Para subtareas de investigación en la tarea actual, usar IDs de petición operativa, nunca falsos IDs Backlog. Preparar una fuente inmutable y referenciada (revision Git/digest de snapshot); verificar permisos efectivos del rol de exploración y lectura de esa fuente. Si hay un escritor activo, no leer su workspace mutable como si fuera una revisión estable. Usar la política de fuentes de CogniCode/Groma si aplica.

```bash
python3 scripts/parallel_read.py < examples/read-only-fanout.json
```

Entrada observada: runId, capabilities fresh/background/notify/explorationReadOnly, maxAgents 1–3 (presupuesto total de slots del host, descontar cualquier agente activo), activeRequests (IDs realmente activos), remainingContextBytes, candidates en orden del proveedor. Cada candidato: id, taskId, ready, readOnly, unresolvedDependencies, question, snapshotRef y snapshotDigest SHA-256 de fuente inmutable observada, contextBytes del brief. El helper omite preguntas repetidas, escrituras, dependencias pendientes y capacidades o fuentes no confirmadas. No adquiere reservas ni inicia ningún agente; la salida es solo candidata.

El supervisor contrasta la salida, comprueba slots y permisos una vez más, prepara briefs acotados y usa exclusivamente delegación nativa fresh (sin fork). Recibe resultados compactos por notificación, reconcilia cada handle antes de reutilizar slots. No permitir publicación, cambios de estados, escrituras de código, ejecución con efectos ni delegación recursiva. No cancelar por inferencia de timeout: comprobar fin real, igual que en el bucle normal. La aceptación y persistencia quedan centralizadas en el supervisor mediante los proveedores existentes.

Si las capacidades faltan, continuar en serie; no instalar infraestructura. Canaries reales de lectura e aislamiento siguen pendientes hasta ejecutarse en el host objetivo. El helper no prueba que el snapshot o permiso declarado sean reales.

La excepción administrativa es un único [Steward](steward.md) en dominio separado realmente observado. Readers siguen estrictamente read-only; no pasar al plan de fan-out una escritura de gestión.
