# Lente: economía, reducción y salud del harness

**Pregunta:** ¿qué garantías cubrimos realmente y cuánto pagamos en ejecución, mantenimiento y falsos rojos?

## Inventario inicial (medir, no inventar)

- Recoger p50/p95 por fase, duración total, flakiness, skips, reruns, caché, procesos/containers residuales, fallos escapados y tiempo hasta capacidad entregada.
- Indexar `garantía → tests que la observan → capa → duración → fallo que discriminan`. Detectar checks que no pueden fallar, snapshots frágiles, repetición unit/integration/E2E, asserts de implementación y UAT de ciclos terminados.
- Clasificar `KEEP | PARAMETERIZE | REPLACE | RETIRE | DEFER`. Una sustitución se valida **antes** de retirar el test original. No eliminar protección de secretos, persistencia, recuperación, aislamiento, integridad, concurrencia o distribución sin equivalencia demostrada.
- Para muchos tests casi iguales: particiones/límites, data-driven, propiedades y combinaciones t-way antes de crear más E2E. Parametrizar reduce mantenimiento, pero el total de ejecuciones puede permanecer igual.
- Usar mutación **focalizada** cuando una prueba verde sea sospechosa o una consolidación pueda dejar un hueco; evitar exigir un mutation score global.
- **Ejecuciones repetidas:** contar por gate cuántas veces corre cada test y con cuántas configuraciones de build (features, perfiles) se compila cada componente; cada configuración distinta es una compilación completa. Un subconjunto que ya contiene otra etapa, o una invocación del runner por test, son coste sin garantía nueva.
- **Pruebas del proceso:** tests que leen roadmap, journal o README, contratos que comprueban la propia CI y tests con nombre de unidad de planificación (`prf_f6_w3_*`) en lugar de comportamiento. Mantener los baratos; sacar del camino de cada PR los que no protegen al consumidor (carril periódico) salvo que el cambio toque lo que vigilan; renombrar por comportamiento al tocarlos.
- **Coste por capacidad entregada:** veredictos de gate y minutos de espera por cambio que llega al consumidor; fracción de cambios que solo mueven documentación o proceso (cada uno, ¿cuánto gate pagó?); ciclos donde cerrar una unidad abre otra solo para registrar su cierre.

## Harness y coste operativo

El [Harness Base portable](../../assets/test-harness-base/README.md) proporciona ejemplos de ciclo seguro. El harness de producción permanece en el repo del producto, mientras escenarios y fixtures **mutables** de aceptación son efímeros. Reutilizar imágenes, perfiles y drivers, no contenedores activos compartidos de CI ni secretos.

Objetivos iniciales orientativos, sujetos a baseline: inner loop ~30–120s, merge ~2–5min, aceptación selectiva ~1–5min, suite automatizada aplicable <=15min y código de tests <= código productivo. **Nunca** usar estos límites para omitir una garantía crítica; escalar explícitamente cuando el riesgo lo requiera. Medir tiempo y defectos escapados tras la reducción.

**Cierre:** oportunidad, garantía, prueba original/sustituta, evidencia de discriminación, ahorro medido o esperado identificado como hipótesis, riesgo residual. Evitar un segundo ledger; aprovechar el registro existente.
