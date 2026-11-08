# Git-artifact hygiene — revisión optativa de riesgos reales

**Usar solo** cuando se pide inspección de higiene o existe indicio de secretos, datos sensibles o problemas concretos en artefactos publicados. No es un preflight de cada tarea ni un gate de commit.

1. Si se necesita, ejecutar en modo lectura `scripts/git_artifact_guard.py --repo . --check`.
2. Los patrones pueden dar falsos positivos: un ROADMAP, ADR, documento Backlog.md o ZIP no justifican por sí mismos bloquear un commit.
3. Respetar el versionado elegido por el proyecto; no imponer `git rm --cached`, `.gitignore` o almacenamiento privado.
4. Solo una exposición técnica real requiere detener la publicación afectada y aplicar la remediación segura con permisos apropiados.

**Salida:** riesgos demostrables y correcciones proporcionadas; no burocracia documental.
