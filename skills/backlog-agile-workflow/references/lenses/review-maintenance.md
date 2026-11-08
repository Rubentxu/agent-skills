# Review & Maintenance — eliminar fricción, terminar trabajo

1. Consultar tareas activas y bloqueadas en Backlog.md. Identificar qué entrega se puede cerrar y qué dependencia real desbloquea otra.
2. WIP y antigüedad son **indicadores de foco**, no cupos, gates o permisos. Aconsejar terminar antes de empezar más, sin ceremonias.
3. Detectar gates, documentos, reportes y dependencias redundantes que retrasan la entrega; simplificarlos o eliminarlos, no sustituirlos por otros.
4. Priorizar defectos, seguridad, pruebas relevantes y contratos públicos por encima de comentarios cosméticos. No abrir un ticket por cada aviso si puede arreglarse dentro del slice.
5. Gestionar cambios, decisiones y prioridades por CLI de Backlog.md. No generar o mantener ROADMAP.md, CHANGELOG.md de progreso ni informes de seguimiento.
6. `backlog doctor --fix`, borrados y operaciones destructivas necesitan revisión por su efecto real. `backlog board export` es opcional y nunca requisito de cierre.

**Salida:** próxima entrega valiosa y una mejora del flujo que reduzca fricción.
