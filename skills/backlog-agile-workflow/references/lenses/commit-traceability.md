# Trazabilidad de commits — mínima y útil

1. Leer la tarea real en Backlog.md y consultar código/historia Git para resolver incertidumbres o evitar trabajo repetido.
2. Escribir un commit claro y, cuando aporte valor, `Backlog-Task: <ID-real>` respetando la convención del proyecto.
3. No exigir `Roadmap-Block`, `ADR-Ref`, `Spec-Ref`, recibos ni Markdown de seguimiento.
4. Registrar resultados y evidencia técnica real en Backlog.md, sin convertir `NOT_RUN` en `PASS`.
5. El índice auxiliar `commit_trace.py` solo sirve a migraciones explícitas del legado, nunca es un gate de commit o cierre.

**Salida:** código rastreable en Git y trabajo en Backlog.md, sin segunda autoridad.
