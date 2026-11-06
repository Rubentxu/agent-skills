# Lenguaje ubicuo — glosario por bounded context

**Objetivo:** un significado por identidad de concepto y contexto, no un diccionario global ambiguo.

1. Leer glosarios existentes con backlog doc search y backlog doc view, además de decisiones y tareas relacionadas. No generar entradas por similitud de palabras.
2. Cada término es un documento Backlog, tipo nativo other, en glossary/<context>, etiquetado con kind:term, ctx:<context> y term:<context.concept>. El ID documental doc-N y el ID de negocio context.concept son distintos.
3. Documentar definición, límites, ejemplos, contraejemplos, alias, nombres rechazados, fuentes y estado proposed / validated / deprecated.
4. Un término sugerido por el agente permanece propuesto; validated necesita evidencia o confirmación del responsable del dominio. Nunca confundir ese estado con permisos.
5. El mismo vocablo puede tener semánticas distintas entre contextos. Establecer mapeos explícitos, no equivalencias automáticas. SKOS sirve de inspiración para labels y relaciones.
6. Cuando cambie el significado, localizar consumidores, tareas y decisiones; proponer migración, no renombrar código a ciegas.

**Salida:** término estable o incertidumbre explícita, fuente, contexto y siguientes verificaciones.
