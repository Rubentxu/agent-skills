# Kanban — transiciones reales, sin autorizaciones administrativas extra

1. Consultar estados configurados y `backlog task view <id> --json` antes de escribir, revalidando ante concurrencia real.
2. **Iniciar:** con permiso de edición, estado válido y dependencias funcionales satisfechas. No exigir cupo WIP ni un `task list` global como precondición de esta skill.
3. **WIP:** aconsejar terminar antes de abrir más. El preflight estricto de `board_crud.py` se usa **solo por petición expresa del proyecto**; su `BLOCKED` no es un bloqueo técnico de Backlog.md.
4. **Progresar:** cambiar estados y notas cuando reflejen trabajo real, sin inventar bloqueos para ajustar métricas.
5. **Finalizar:** verificar AC/DoD pertinentes con evidencia, registrar resumen breve y mover al estado final. No exigir gates de gestión ni referencias externas.
6. **Reabrir:** cuando el resultado deje de satisfacer realmente el contrato, preservando historia e inspeccionando dependencias técnicas.
7. Revisar callbacks `onStatusChange`, efectos Git y permisos según riesgos reales de cada operación; releer el estado después de mutar.

`board_crud.py` propone argumentos; sus simulaciones optativas de WIP o evidencia no sustituyen la CLI ni el juicio técnico.
