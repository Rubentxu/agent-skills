# Dependencias reales y desbloqueo continuo

1. Leer `backlog task view <id> --json` y el grafo cuando haya dependencias; determinar qué capacidad concreta falta.
2. **Dependencia válida:** sin el resultado de otra tarea no se puede implementar o comprobar el comportamiento. Orden deseado, WIP, ADR, ROADMAP, recibos o gates burocráticos **no son dependencias**.
3. Retirar por CLI, con permiso, aristas ficticias; conservar las que realmente protegen contratos, integraciones o seguridad.
4. Evitar ciclos e IDs ambiguos. Una tarea archivada sin completar no satisface una dependencia técnica auténtica.
5. Si el trabajo está bloqueado de verdad, investigar la causa con [flow-recovery](flow-recovery.md) y decidir **sin prolongar el bloqueo**: corregir dentro de la tarea, crear un desbloqueante técnico independiente verificable, acotar el slice o repriorizar. Registrar relación y reanudación en Backlog.md. No simular Done.

**Salida:** desbloqueo técnico o eliminación de dependencia artificial registrada solo en Backlog.md.
