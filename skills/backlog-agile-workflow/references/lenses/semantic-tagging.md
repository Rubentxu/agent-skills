# Etiquetado semántico y relaciones

**Objetivo:** vincular conocimiento al lenguaje del dominio de manera verificable.

1. Comprobar que cada término existe en glosario; buscar términos por CLI antes de proponer tags.
2. Todo documento de conocimiento **nuevo** incluido en el corpus semántico debe tener al menos un tag term:<context.concept> y su ctx:<context>. Añadir opcionalmente kind:research, kind:invariant, kind:algorithm, kind:risk, kind:note o kind:term.
3. Backlog --type admite solo readme, guide, specification y other; la clase semántica no debe inventarse como tipo CLI.
4. Relaciones tipadas: supports, contradicts, investigates, threatens, constrains, motivates, supersedes, implements, affects, validates, maps_to, related. Cada relación anota términos presentes también en los tags del documento fuente.
5. Persistir las relaciones en el cuerpo gestionado por backlog doc update --content, no escribir campos de frontmatter manualmente. Durante el export, una normalización produce x_domain.relations y enlaces OKF.
6. backlog doc update --tags reemplaza el conjunto; leer, fusionar, aplicar y volver a leer. --content reemplaza el cuerpo. backlog task edit --add-doc recibe exactamente la ruta devuelta por CLI.
7. No forzar migración de documentos históricos, ni convertir toda mención textual en etiqueta.

**Salida:** tags semánticos trazables y relaciones validadas, o un término pendiente de revisión.
