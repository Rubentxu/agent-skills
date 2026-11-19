# Contratos mínimos de intento

El envelope transporta identidad de proyecto/run/intento/tarea, criterios AC y DoD efectivos, repositorios y revisión base completa, paths relativos orientativos, políticas observadas y referencias a handoff y context-pack. No reemplaza contratos de autoridad ni implementa permisos. El host revalida política, revisión, rutas reales (incluidos symlinks) y capabilities; los paths son alcance declarado, no sandbox. El envelope no contiene secretos, transcripts ni el contenido del corpus. Si no hay knowledge pack, null con limitación explícita en el informe del supervisor.

```bash
python3 scripts/delegation_contract.py envelope examples/envelope.json
python3 scripts/delegation_contract.py result examples/envelope.json examples/result.json
```

El resultado incluye todos los criterios, incluso not-run/unknown, referencias de evidencia por criterio que declara pass, todas las revisiones de repos asignados y pendientes. READY_FOR_REVIEW no equivale a Done ni PASS. Una entrega parcial puede tener criterios pendientes. El checkpoint particiona criterios y enlaza estado recuperable; una referencia no garantiza que el artefacto exista.

Ver [envelope](../examples/envelope.json) y [resultado](../examples/result.json). El validador comprueba estructura, atribución y tamaño UTF-8 compacto; no inspecciona Git, Backlog, permisos, evidencia ni resultados de herramientas. No acepta SHA abreviados ni resultados de otro intento. El receptor contrasta fuentes reales. Los presupuestos por bytes son orientativos y se informa overBudget; no se cercena evidencia para satisfacer una cifra. El límite técnico de entrada es 256 KiB por documento.

Usar estos contratos únicamente como sobres operativos. Mantener Ghost Context, context-pack y review_contract en sus proveedores originales. No copiar los payloads completos entre agentes; enviar solo campos indispensables y referencias permitidas.
