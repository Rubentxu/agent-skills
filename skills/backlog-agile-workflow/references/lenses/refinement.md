# Refinement — de necesidad a valor observable

1. Elegir una capacidad usable y un slice vertical pequeño; no crear tareas por capas, comités, informes ni gates.
2. Escribir AC que demuestren comportamiento; contemplar fallos, compatibilidad y seguridad según impacto.
3. Usar la Definition of Done nativa del proyecto **sin ampliarla con trámites** o documentación de seguimiento. Actualizar documentación de API cuando cambie su contrato.
4. Registrar decisiones duraderas en objetos nativos de Backlog.md; no exigir ROADMAP, CHANGELOG o ADR paralelos. `--plan` es opcional y justo a tiempo.
5. Dependencias solo si el entregable de otra tarea se necesita para implementar/verificar la actual; no encadenar por orden, review o gate.
6. Investigar incertidumbres técnicas solo lo suficiente para avanzar o crear un spike con resultado verificable, sin esperar documentos.

**Salida:** resultado, AC concisos, primer incremento y dependencias auténticas.
