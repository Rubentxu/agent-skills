# goldfish-review

Revisión adversarial de diseños desde un contexto de agente nuevo, con fuentes, coste y autoridad acotados. **Funciona como skill propia**: no requiere instalar el plugin Elephant-Goldfish Model.

1. Preparar un \`ReviewRequest\` con SHA Git, SHA-256 del documento y fuentes relativas permitidas, tras leer Backlog/Git reales cuando existan.
2. Verificar la herramienta nativa del host que **sí cree un agente nuevo**; el ejecutor debe proporcionar permisos reales de solo lectura. No hay aislamiento fiable por un prompt.
3. Enviar exclusivamente la pregunta, el target y la rúbrica elegida a cada subagente. Los lectores desconocen el historial del Elephant.
4. Recoger informes; consolidar con \`scripts/review_contract.py\`. Cualquier aislamiento no comprobado se indica como **HOST_REPORTED** o parcial; nunca como certificación externa.
5. Contrastar hallazgos contra código/tests con las skills existentes. Persistir progreso solo por Backlog.md CLI y con autoridad apropiada.

## Perfiles

- lite: comprensión o arquitectura, 1 ronda.
- focused: dos o tres revisores, máximo 2 rondas, coste explícito.
- deep: revisión adicional de fallos, seguridad y readiness; aprobación del coste.

## Protocolo de uso

\`\`\`bash
python3 scripts/review_contract.py validate-request examples/request.json
python3 scripts/review_contract.py aggregate examples/request.json examples/reports.json
python3 scripts/review_contract.py drift examples/baseline.json examples/current.json
python3 -m unittest discover -s tests -p 'test_*.py'
\`\`\`

El comando \`aggregate\` no ejecuta Goldfish: valida **resultados aportados** y genera una vista derivada. \`drift\` detecta **cambios de fingerprints**, no divergencia semántica demostrada.

Ver [contratos](references/contracts.md), [aislamiento](references/isolation.md), [guía de hosts](references/host-capabilities.md) y [resolución](references/resolution.md).

## Pilotos y estado de garantías

Ver [matriz de pilotos](references/pilots.md). Los tests verifican contratos, deduplicación, rechazo de reportes obsoletos y diferencias de SHA/digest. No se ha ejecutado un smoke con agentes de contexto nuevo en este cambio: su estatus es **NOT_RUN** hasta aportar evidencia del host. El hook Claude Code (plugin independiente) puede mostrar una sugerencia opt-in, pero nunca lanza revisores.

Los reportes requieren evidencia anclada por rango de líneas o sección del documento; una ruta sin ubicación no es suficiente. La deduplicación conserva todas las referencias originales de distintos revisores.
