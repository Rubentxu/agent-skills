# Code documentation — contratos profesionales, cualquier lenguaje

**Activación:** petición explícita de documentar/auditar comentarios, docstrings, API o normas `AGENTS.md`; también como referencia puntual al refinar, ejecutar, verificar o mantener un contrato de código. **No exige Backlog.md, Groma ni otra skill.** Esta lente orienta: no edita por sí sola.

> El código explica cómo funciona; la documentación explica el contrato vigente y las decisiones técnicas que no resultan evidentes. La historia del trabajo pertenece a Git y Backlog.md, no a los comentarios del producto.

## Flujo mínimo: observar → clasificar → documentar → contrastar

1. **Delimitar superficie.** Leer el código y el diff reales, interfaces usadas por consumidores, tests, esquemas y reglas del repositorio. Identificar lenguaje(s) y qué API está **soportada**, no equiparar todo símbolo `public` con una promesa externa. No deducir funcionalidades de documentación antigua.
2. **Clasificar antes de editar.**
   - **Código/identificadores:** intención y flujo comprensibles mediante buenos nombres, tipos y composición.
   - **Documentación pública de API:** propósito y garantías, pre/postcondiciones, resultados/refusals, efectos, concurrencia/cancelación, restricciones de seguridad, versionado y ejemplos donde reduzcan ambigüedad.
   - **Comentario interno:** solo un invariante o decisión de implementación actual no evidente (durabilidad, orden de efectos, sincronización, seguridad, performance o workaround vigente).
   - **Guía del usuario/operación:** uso de producto, instalación, configuración, ejemplos, errores, CLI y protocolos; puede ser producto versionado.
   - **Historia/gestión:** tickets, issues, personas, autoría, PR, commits, campañas, razones del refactor anterior, roadmap/ADR como puntero exclusivo; conservar en Git/Backlog/registro autorizado, no en comentarios del producto.
3. **Aplicar el mínimo.** Corregir documentación falsa; eliminar comentarios obsoletos, tautológicos, código comentado, narraciones del tipo «antes hacíamos...» y duplicación de información ya expresada por el tipo. Mantener **la explicación de una invariante vigente** aunque la historia que motivó su creación no pertenezca ahí. Priorizar superficie pública, seguridad, fallos y contratos entre módulos.
4. **Elegir formato nativo después de detectar stack.** Leer [recetas por lenguaje](../code-documentation-languages.md) solo para los lenguajes observados. Reutilizar documentación, analizadores y generadores ya presentes. Si faltan, proponer alternativas; nunca instalar ni introducir una dependencia sin autorización y valor.
5. **Revisar calidad, no volumen.** El docstring debe responder una pregunta real del consumidor; comprobar nombres, enlaces, excepciones, unidades, defaults, invariantes y ejemplos **contra el código actual**. La generación de documentación o linter en verde demuestra formato, no veracidad. No exigir KDoc/Javadoc por cada helper privado ni crear un porcentaje objetivo arbitrario.
6. **Unir con Backlog cuando exista trabajo real.** En `refine`, añadir AC de documentación únicamente si un contrato se ve afectado; en `execute`, actualizar documentación junto al código; en `verify`, revisar exactitud y herramienta nativa económica; en `close`, enlazar SHA y evidencia real. Documentación meramente cosmética no crea tareas por archivo. Si se pide implantar una política, proponer una mejora de `AGENTS.md` específica y revisable, **sin sobreescribir reglas existentes**.
7. **Separar autoridad y seguridad.** Los tickets, decisiones, IDs de gestión y procedencia van en Backlog y trailers Git, no en comentarios de código. Excepción explícita: identificadores funcionales, nombres de APIs, `RunId`, `traceparent`, códigos de estado, CVE, RFC, estándares, unidades y URLs técnicas legítimas. No trasladar secretos, nombres de usuarios, handles, correos ni tokens a ejemplos o informes.

## Resultado recomendado

**Si se pide una auditoría:** `archivo:símbolo → problema comprobado o hipótesis → contrato afectado → acción mínima → método de contraste`. Separar `VERIFICADO` de `NO_VERIFICADO`; si no existe el código, decirlo.

**Si se piden tareas:** una mejora por garantía observable, no por función/documentación aislada; reconciliar con la CLI y las tareas existentes antes de escribir.

**Si se pide la política:** ofrecer reglas adaptadas a `AGENTS.md` y las herramientas reales del proyecto, sin imponer una receta Kotlin en otros lenguajes.

**No hacer:** nuevo scanner global de comentarios, framework de pruebas de documentación, reescritura masiva sin revisar ABI/compatibilidad, commits automáticos, efectos de Groma por una lectura o referencias a tickets dentro del código de la aplicación.
