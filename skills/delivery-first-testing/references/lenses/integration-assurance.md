# Lente: integración posterior a merge

**Pregunta:** ¿la composición del sistema permanece estable? Ejecutar suite amplia por versiones/componentes, integración entre módulos, E2E de recorridos críticos y escenarios de incompatibilidad reales. No duplicar todos los UAT efímeros ya cubiertos en niveles más bajos. Si la suite de frontera (p. ej. E2E de UI) corre contra dobles, aquí corre al menos un recorrido crítico contra el proveedor real, o un control de paridad doble↔proveedor; un E2E verde sobre mocks que divergen del servidor es falso verde de integración. Distribuir/parallelizar cuando no rompe aislamiento; usar caché válida y trazabilidad de artefactos.

Un rojo posterior a merge exige arreglar o revertir antes de liberar; no se ignora como advisory cuando la garantía es obligatoria. Distinguir fallos de entorno de fallos de producto. Recalcular el mínimo de pruebas de smoke que deben permanecer en merge si una regresión escapa sistemáticamente.

**Cierre:** versión, módulos cubiertos, skips, rojo/verde honesto y acción de recuperación.
