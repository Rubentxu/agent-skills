# Drift diferencial

1. Construir snapshots con SHA Git y fingerprints de documentos/código observados. Si son incompletos, INCONCLUSIVE.
2. Comparar hashes mediante validador de goldfish-review (si está instalada). No añadir índice ni grafo: `knowledge_graph.py` conserva la proyección semántica.
3. Un cambio o desaparición del hash es candidato, **nunca prueba de divergencia semántica**. Contrastar contrato, consumidores, código y tests.
4. Persistir solo un hallazgo útil por CLI con tarea o doc existente, sin crear tickets automáticamente ni sustituir decisiones.

**Salida:** fuentes cambiadas, faltantes e incertidumbres.
