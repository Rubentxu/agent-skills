# Documentación nativa por lenguaje — referencia bajo demanda

**Principio común:** documentar el contrato soportado y las decisiones no evidentes, no convertir la historia de implementación en comentarios. Detectar lenguaje, build, convenciones, visibilidad real y herramientas presentes **antes** de elegir una fila. Herramientas mencionadas son opciones, nunca instalaciones automáticas.

| Lenguaje/ecosistema | Formato habitual | Herramientas de lectura/generación o revisión (según instalación) | Nota de contrato |
|---|---|---|---|
| Kotlin / Kotlin Multiplatform | KDoc | Dokka, Detekt, IDE/Kotlin compiler | Documentar API de bibliotecas/DSL, semántica de `suspend`, errores y concurrencia; no duplicar anotaciones |
| Java | Javadoc | `javadoc`, Checkstyle/DocLint según build | `@throws`, `@since`, comportamiento nulo y compatibilidad cuando proceda |
| Python | docstrings (PEP 257; estilo local Google/NumPy/reST) | `pydoc`, Sphinx, pydocstyle/Ruff si presentes | Tipos del código, excepciones, efectos y ejemplos reales; no fingir que type hints documentan semántica |
| Rust | `///` y `//!` rustdoc | `cargo doc`, doctests, Clippy | `# Safety` para `unsafe` público, `# Panics`/ `# Errors` si relevantes; no inventar invariantes |
| Go | Doc Comments | `go doc`, `go vet`, pkg.go.dev | Comentar símbolos exportados y paquetes; garantías de concurrencia y valor cero |
| JavaScript / TypeScript | JSDoc / TSDoc | TypeDoc, API Extractor, `tsc` si usados | Contratos de tipos expuestos, efectos async, errores y compatibilidad; evitar narrativas de PR |
| C# / .NET | XML documentation comments | compilador C#, DocFX si presente | `summary`, `exception`, `remarks` donde ayuden; documentar nulabilidad y `async` |
| Swift | Markdown Doc Comments / Swift-DocC | Xcode, DocC | `Parameters`, `Returns`, `Throws`, actores/concurrencia y disponibilidad |
| Dart / Flutter | `///` dartdoc | `dart doc`, `dart analyze` | API pública, lifecycle de widgets, errores y nulos |
| C / C++ | Comentarios de interfaz; Doxygen si elegido | Doxygen, clang-tidy/compilador según build | Ownership de memoria, ABI, hilos, errores, unidades y comportamiento indefinido |
| PHP | PHPDoc | phpDocumentor, PHPStan/Psalm si presentes | Forma de valores, excepciones y restricciones no capturadas por tipos |
| Ruby | Comentarios y YARD cuando proceda | YARD, RDoc | Bloques, errores, side effects, contratos de módulos |
| Scala | Scaladoc | sbt doc/Scaladoc según versión | Efectos, concurrencia, implicits/givens y garantías de APIs |
| Shell / CLI | Comentarios breves + `--help`/man pages | ShellCheck, help/completions existentes | Flags, exit codes, efectos destructivos, variables de entorno, permisos |
| OpenAPI / protobuf / GraphQL | Schema y descripciones canónicas | Generador/validador del contrato existente | Mantener una única fuente del wire y sus campos, no duplicarla en cada implementación |
| Terraform / Helm / Kubernetes YAML | Variables, schema, CRD/OpenAPI, `--help`, ejemplos | `terraform-docs`, `helm lint`, schema validator si presentes | Priorizar contrato declarativo, defaults, permisos y semántica de reconciliación |

## Preguntas antes de activar una herramienta

1. ¿La API está publicada o es interna? ¿Quién la consume realmente?
2. ¿Existe ya un generador, linter o convención de comentarios en el build?
3. ¿Qué propiedades no transmite la firma (errores, lifecycle, null/empty, idempotencia, side effects, seguridad, orden, compatibilidad)?
4. ¿Se puede validar el ejemplo con el test/compilación **existente** y coste acotado?
5. ¿Es documentación de producto que puede versionarse, o metadata de proyecto privada?
6. ¿El cambio es solo documental o altera una garantía observable? No inventar E2E para comentarios.

## Fuentes de estándares, consultar cuando apliquen

- Kotlin KDoc: https://kotlinlang.org/docs/kotlin-doc.html
- Guía de API Kotlin: https://kotlinlang.org/docs/api-guidelines-informative-documentation.html
- Dokka: https://kotlinlang.org/docs/dokka-gradle.html
- Java Javadoc: https://docs.oracle.com/en/java/javase/25/javadoc/javadoc.html
- Python PEP 257: https://peps.python.org/pep-0257/
- Rust rustdoc: https://doc.rust-lang.org/rustdoc/how-to-write-documentation.html
- Go doc comments: https://go.dev/doc/comment
- TSDoc: https://tsdoc.org/
- TypeDoc: https://typedoc.org/
- C# XML comments: https://learn.microsoft.com/dotnet/csharp/language-reference/xmldoc/
- Swift DocC: https://www.swift.org/documentation/docc/
- Dart dartdoc: https://dart.dev/tools/dart-doc
- Doxygen: https://www.doxygen.nl/manual/docblocks.html

La tabla no es un catálogo exhaustivo. Ante otro lenguaje, aplicar el principio universal con su documentación oficial y sus herramientas existentes, sin forzar un formato ajeno.
