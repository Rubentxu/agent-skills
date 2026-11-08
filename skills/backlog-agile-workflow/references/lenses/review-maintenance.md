# Review & Maintenance — eliminar fricción, terminar trabajo

1. Consultar tareas activas y bloqueadas en Backlog.md. **Detectar falta de avance real**, no solo cambios de estado: pruebas relevantes sin mejorar, errores repetidos, incrementos que no aparecen o espera externa. Identificar qué entrega puede cerrarse y qué dependencia real desbloquea otra. No inferir estancamiento a partir de fechas que no se conocen.
2. WIP y antigüedad son **indicadores de foco**, no cupos, gates o permisos. Aconsejar terminar antes de empezar más, sin ceremonias.
3. **Cuando se observe estancamiento, priorizar [flow-recovery](flow-recovery.md):** formular una hipótesis comprobable, elegir una alternativa y actuar en el mismo ciclo. Si el corte vertical es demasiado grande, dividir por valor realmente entregable; si hay impedimento técnico independiente, considerar una tarea desbloqueante; si hay espera externa, registrar reanudación y repriorizar. No celebrar otra reunión ni continuar por inercia.
4. Detectar gates, documentos, reportes y dependencias redundantes que retrasan la entrega; simplificarlos o eliminarlos, no sustituirlos por otros.
4. Priorizar defectos, seguridad, pruebas relevantes y contratos públicos por encima de comentarios cosméticos. No abrir un ticket por cada aviso si puede arreglarse dentro del slice.
5. Gestionar cambios, decisiones y prioridades por CLI de Backlog.md. No generar o mantener ROADMAP.md, CHANGELOG.md de progreso ni informes de seguimiento.
6. `backlog doctor --fix`, borrados y operaciones destructivas necesitan revisión por su efecto real. `backlog board export` es opcional y nunca requisito de cierre.

**Salida:** próxima entrega valiosa y **decisión de recuperación ejecutable**, no un informe sobre la inactividad.
