# Contratos de revisión v1

Un objeto request tiene: \`schemaVersion=1\`, \`kind=goldfish-review-request\`, \`target={path,gitRevision,sha256}\`, \`scope={question,allowedSources,mode}\`, \`reviewers\` (IDs únicos de rúbricas) y \`limits.maxRounds\` (1..5). \`taskId\` es opcional y solo se acepta si es un identificador sintácticamente válido, no acredita que exista.

Cada ruta es relativa a la raíz declarada del repositorio; prohibidos escapes léxicos, URLs, rutas absolutas y separadores Windows. El host **debe** resolver enlaces simbólicos, permisos, revisiones y SHA-256 antes de delegar. Un path terminado en / representa un subárbol autorizado. El documento objetivo debe incluirse entre las fuentes autorizadas.

Un informe tiene \`schemaVersion=1\`, \`kind=goldfish-review-report\`, \`reviewer\`, \`target={gitRevision,sha256}\`, \`execution={status,conversationFresh,toolsReadOnly,sourcesRestricted,hostReported}\` y \`findings\`. Los cuatro últimos campos son declaraciones del host o del caller, NO pruebas criptográficas; comprobar el origen en el entorno. \`status\` es completed o not_run. Ante no ejecución, el array findings es vacío.

Cada finding contiene \`scope\`, \`claim\`, \`severity\` (Blocker, Major, Nit), \`evidence\` (lista de fuentes permitidas) y \`verification\` (forma de comprobar/refutar). Los resultados agregados son **candidatos**, no defectos automáticamente confirmados. Los hallazgos repetidos se agrupan por normalización exacta de scope/claim, nunca por similitud semántica opaca.

La agregación es una **proyección pura**:
- \`REVIEWED_WITH_FINDINGS\`: todos los revisores esperados respondieron, contexto nuevo y read-only declarados, sin limitaciones declaradas de fuentes, y hay hallazgos.
- \`REVIEWED\`: las mismas condiciones y cero hallazgos; esto no significa aprobado.
- \`INCONCLUSIVE\`: informe ausente, not_run, incompleto, mismatch de revisión/digest o aislamiento no afirmado; incoherencias de esquema/revisión se rechazan antes de agregar.

El resultado señala \`assurance=HOST_REPORTED_ONLY\`. No tiene efecto ejecutivo ni conserva autoridad. No convertir su estado en un gate de publicación sin comprobación externa.

La entrada de drift es un snapshot \`{schemaVersion:1,kind:"goldfish-source-snapshot",gitRevision:"SHA",sources:{"ruta":"sha256"}}\`. El detector compara identificadores/fingerprints y no inspecciona contenido. \`changed\` y \`missing\` exigen investigación posterior: cambio de hash no significa drift semántico.

### Evidencias ancladas

Cada elemento de `findings[].evidence` es un objeto `{path, lineStart, lineEnd}` con rango inclusivo máximo 201 líneas, o `{path, section}` para documentos sin numeración estable. La ruta debe estar en `allowedSources`; una ruta aislada sin rango o sección no valida un hallazgo. Las fuentes se deduplican por objeto exacto; el host revalida que su contenido corresponde al SHA/digest indicado. La similitud de reclamos no fusiona problemas diferentes.
