# Correspondencia con el plan de integración (GFR)

Las claves son referencias de planificación, no IDs nativos creados en Backlog.md.

| Clave | Entrega |
| --- | --- |
| GFR-01 | Fronteras descritas en SKILL.md, contracts.md y resolución |
| GFR-02 | Request/report/snapshot v1 y validador puro `review_contract.py` |
| GFR-03 | `goldfish-review` y rúbricas independientes |
| GFR-04 | Protocolo fail-closed y canaries de aislamiento (pruebas del host pendientes) |
| GFR-05 | Lentes/routing opt-in en `backlog-agile-workflow` |
| GFR-06 | Reconciliación por CLI y límites de autoridad y WIP |
| GFR-07 | Integración semántica declarativa con glosarios, investigación y arquitectura emergente |
| GFR-08 | Unit tests adversariales y fixtures sin red ni Backlog |
| GFR-09 | Matriz de tres pilotos; evidencia con agentes reales pendiente |
| GFR-10 | Detector puro de cambios de fingerprints, sin afirmación de drift semántico |
| GFR-11 | Recomendación `BACKLOG_CONTEXT_GOLDFISH=hint` del plugin opcional, sin spawn |

No marcar GFR-04/GFR-09 completamente validadas hasta ejecutar pruebas de aislamiento en el host. El sistema sigue siendo funcional sin EGM oficial, y no incorpora librerías de terceros.
