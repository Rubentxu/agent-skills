# Consistencia semántica y grafo derivado

**Objetivo:** detectar términos desconocidos, enlaces rotos y contradicciones sin alterar registros.

1. Construir un snapshot knowledge-corpus v1 de lecturas reales de CLI; documentar alcance y advertir si está incompleto.
2. Ejecutar scripts/knowledge_graph.py en validate o graph: no usa red, Backlog ni Groma. El grafo es una vista derivada, no persistencia independiente.
3. Validar IDs canónicos, nombres duplicados dentro de un contexto, tags sin términos existentes, falta de ctx, tipos y estados, relaciones sin semántica y destinos desconocidos.
4. Una relación contradicts declara conflicto, no prueba que una hipótesis sea falsa. No cerrar riesgos, aprobar términos ni sustituir decisiones por inferencia.
5. Recuperar primero referencias directas de tarea y documentos; expandir a vecinos relevantes sólo cuando cambien una decisión.
6. Ante conocimiento obsoleto, enlazar fuentes y proponer revisión en Backlog; conservar historial de decisiones. UNKNOWN, UNVERIFIED, CONFLICTED y STALE no son estados de Backlog.

**Salida:** errores localizados, grafo reproducible y acción concreta para verificar.
