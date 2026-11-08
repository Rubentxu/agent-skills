# Higiene del repositorio sin gates documentales

**Regla:** Backlog.md es el único sistema de seguimiento de tareas, hitos, estados, planes, dependencias, decisiones y trabajo pendiente. No generar ni solicitar `ROADMAP.md`, `CHANGELOG.md` de progreso, tareas en Markdown, informes de gates ni recibos como soporte del workflow. Una aplicación sí puede tener guías de producto, documentación de API y diseños técnicos que aporten valor propio.

El almacenamiento y versionado **nativos de Backlog.md** siguen la configuración del proyecto. No imponer `--no-git`, `.gitignore` ni retirar sus tareas de Git: Backlog.md admite colaboración basada en Git. Esta skill no crea una segunda fuente de tracking.

## Detector heredado, solo diagnóstico solicitado

`scripts/git_artifact_guard.py --repo . --check` clasifica patrones heredados; **no es un gate de commit o publicación**. La coincidencia por nombre/ruta no prueba un defecto. No ejecutar automáticamente `git rm --cached`, modificar `.gitignore` ni bloquear commits por contener ADR, ROADMAP o documentos nativos de Backlog.md.

Solo frenar operaciones por un riesgo técnico real (secretos expuestos, información sensible publicada sin permiso o artefactos inseguros). Las limpiezas de índice y políticas de Git requieren autorización y preservar colaboración y recuperación.

## Responsabilidades

- **Backlog.md:** tracking, planes, decisiones, aceptación, evidencia y vínculos con commits.
- **Git:** código e historia de cambios; no exige trailers por cada documento.
- **Documentación de producto:** contratos y guías técnicas útiles para consumidores.
- **Groma (opcional):** mapa arquitectónico; no es un gestor adicional de tareas ni requisito para implementar.

Las referencias de esta skill distribuida son parte de su propio producto, no una recomendación de crear archivos administrativos en aplicaciones consumidoras.
