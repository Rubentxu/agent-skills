# Presupuestos según riesgo

- **none / KEEP_AS_IS**: modificación trivial, actualización localizada sin impacto de contrato. No iniciar revisores.
- **lite**: incertidumbre de comprensión; un revisor, una ronda, no más de un reporte persistido si es reutilizable.
- **focused**: cambios de contrato, ownership o API; elegir dos o tres rúbricas relevantes, máximo dos rondas. No imponer todas.
- **deep**: seguridad, estado durable, breaking change o migración irreversible. Incluir crítico de fallos y readiness; hasta cinco rondas solo si la evidencia justifica el coste y hay aprobación humana del presupuesto.

Priorizar defectos falsables. Parar en KEEP_AS_IS, REMEDY, EXPERIMENT, NEED_EVIDENCE o BLOCKED. Los nits no abren rondas. Una ronda limpia no certifica seguridad, y una ronda ausente nunca es limpia.

Registrar costo medido (segundos/tokens cuando el host los facilita), número de revisores terminados, defectos confirmados, falsos positivos y retrabajo evitado. No extrapolar desde fixtures.
