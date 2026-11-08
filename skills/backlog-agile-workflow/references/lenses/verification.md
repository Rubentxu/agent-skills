# Verification y cierre — demostrar calidad con implementación real

1. Leer tarea y AC/DoD mediante la CLI oficial; verificar **comportamientos entregados**, invariantes, seguridad y compatibilidad afectados con pruebas proporcionadas al riesgo.
2. Actualizar documentación técnica de API/contratos cuando el código los modifique. No exigir README, ROADMAP, CHANGELOG, ADR, informes ni recibos de gates como criterio de cierre.
3. Registrar solo evidencia real: `PASS/FAIL/NOT_RUN`, pruebas, revisión o demostración concreta. Una prueba no ejecutada no es PASS; un fallo pertinente requiere corrección o alcance claramente acotado.
4. Marcar AC/DoD verdaderos con `--check-ac` y `--check-dod` utilizando índices observados. Escribir un `--final-summary` breve sobre valor entregado y limitaciones técnicas.
5. Pasar al estado final configurado **tan pronto como se satisfagan aceptación y calidad pertinentes**. Nunca esperar certificaciones administrativas, documentos de tracking, reuniones, snapshots o gates ajenos a la entrega.
6. La publicación o despliegue puede exigir verificaciones técnicas/regulatorias obligatorias; no falsearlas ni saltarlas. Si son una entrega distinta, gestionarlas aparte sin retener artificialmente una tarea de implementación ya verificada.
7. No archivar automáticamente y no borrar sin autorización.

**Resultado:** tarea terminada con evidencia o problema técnico pendiente descrito. Nunca declarar DONE sin garantía suficiente ni BLOCKED solo por burocracia.
