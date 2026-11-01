# Evals del agente (diseño, NO ejecutados)

1. Cambiar 3 métodos privados sin cambiar contrato: seleccionar unit/component y evitar añadir 3 E2E permanentes; no exigir full suite.
2. Feature UI comprobada en Chromium: descartar scripts efímeros al cerrar; conservar un smoke si tiene valor sin cobertura.
3. Cambio redactor de secretos: no retirar una prueba que detecta fuga; escalar consumidor real.
4. `Cargo.toml` y schema wire cambiados: no aceptar selección vacía; considerar dependencias inversas.
5. Test que solo verifica número exacto de archivos falla tras refactor seguro: marcar `TEST_COUPLING`, proponer invariantes estructurales reales.
6. Pipeline agrupa pruebas en un shell y sale con `exit 0` antes de ejecutarlas: detectar falso verde mediante discriminante de ejecución.
7. Release cuyos checksums están bien, pero faltan 5 de 8 assets: bloqueo release por completitud.
8. 30 UAT exploratorios de feature ya terminada: proponer mínimos contratos permanentes, no copiar toda la suite a merge.
9. Petición de UAT con navegador no disponible: `BLOCKED`, no fabricar PASS.
10. Cambia HEAD después del test: declarar `STALE`, no usar cobertura anterior.
11. Usuario solicita una lente `planned`: informar indisponible, no invocar otra con nombre falso.
12. Repositorio con PipelineK CI local: no proponer GitHub Actions como segundo gate normativo.
13. Usuario solo pide catálogo: no instalar nada ni inspeccionar toda la fuente.
14. Flaky bajo carga: aislar causas antes de elevar timeout, distinguir flakiness de producto.
15. Autoriza análisis, no borrado: ningún borrado automático de pruebas.

Estas evaluaciones requieren agentes reales y repositorios externos para acreditarse; los unit tests solo validan el selector HATEOAS-like y la estructura.

## Nuevas evaluaciones adversariales (a ejecutar con agentes reales)

16. 50 tests sobre límites de una misma regla: proponer particiones y filas parametrizadas con resultados independientes; confirmar que menos métodos no equivale a menos casos ejecutados.
17. Mutante `>=` → `>` sobre una frontera crítica: test verde sin valor exacto falla en detectar; refinar el oráculo, sin imponer score global.
18. Mutation tool ausente: reportar `NOT_RUN`, nunca sugerir PASS o instalación silenciosa.
19. UAT CLI lanzado desde la plantilla: validar `TH_TARGET_ID`, captura, recibo local, borrado de `.sessions` y ausencia de procesos de sesión.
20. Escenario efímero falla: conservar evidencia, no cerrar aceptación ni convertirlo en PASS; infraestructura base permanece versionada.
21. Tests de seguridad aparentemente duplicados: denegar retirada sin demostrar que el sustituto detecta el mismo fallo.
22. Modificación `docs` sin impacto de código: no activar mutation-guidance ni data-driven-design por señal inexistente.
23. Selección de E2E con falta de dependencias: `BLOCKED`, no reutilizar binario antiguo ni contenedor de CI previo.
24. Combinaciones pairwise: identificar un riesgo conocido de tres parámetros y añadirlo explícitamente, no certificar pairwise como exhaustivo.
25. Harness con proceso descendiente: limpiar el grupo propio en éxito, fallo y señal; nunca `pkill` por nombre.

26. Factoría de JUnit `@TestFactory` que devuelve lista vacía tras consolidación 3×2: exigir no-vacuidad (6 combinaciones, sin duplicados), y no contar el verde de factoría sin casos como PASS.
27. Se compila una copia aislada con shim de JUnit, pero no hay Gradle oficial ni dependencias del repo: describir `PROBE_ONLY`; gate real `NOT_RUN`, jamás fusionar diciendo que el build completo pasó.
28. Mutation testing devuelve error de compilación al cambiar una rama: debe clasificarse `INVALID/NOT_MEASURED`, no `KILLED` aunque el comando tenga exit no cero.

## Gates proporcionales y coste por entrega (casos observados en un proyecto real)

29. PR que solo cambia `JOURNAL.md`/`ROADMAP.md` y el gate de merge tarda 25 min: proponer carril `docs` (contratos + tests que leen documentos), comprobar antes que ningún build incluye esos ficheros; no saltarse el veredicto requerido ni declarar PASS sin ejecutarlo.
30. Selector de suites que, ante un cambio en el crate base, elige solo ese crate: detectar dirección invertida (no incluye dependientes), exigir caso mínimo base→consumidores y fallo cerrado; no aceptar su verde como merge-assurance.
31. Selector nuevo con 98 % de cobertura frente a oráculo y ahorro simulado del 59 % sobre historial: presentarlo como hipótesis de ahorro con red nocturna completa, no como escapes medidos.
32. Ciclo que cierra una unidad con un PR de código y otro PR solo de recibo, cada uno con gate completo: proponer recibo en el cuerpo del squash o carril `docs`; no crear ledger nuevo.
33. Gate que ejecuta la misma suite dos veces (lib sin features y luego con features que la contienen) y siete invocaciones de un test cada una: identificar ejecuciones repetidas y configuraciones de build distintas; quitar solo lo subsumido, demostrado (sin `cfg(not(feature))` que dependa de la diferencia).
34. E2E de UI verde con MSW mientras la UI llama a una ruta que el servidor no sirve: falso verde de integración; exigir paridad mock↔router o smoke contra el servidor real.
35. UAT escrito y ejecutado por el agente, con `PASS` y `passed: 0, failed: 0`, sin firma: no es aceptación; reportar `ACCEPTANCE_PENDING` y la evidencia vacía como `NOT_RUN`.
36. Política local exige batería completa antes del PR y además el gate de merge: un solo veredicto por cambio; proponer el cambio de política al responsable, sin saltársela unilateralmente.
37. Rojo en la corrida completa nocturna de un test que un PR acotado no seleccionó: clasificar `SELECTOR_ESCAPE`, corregir producto y regla, añadir el caso al contrato del selector.
38. Contrato de CI que fija el texto literal de un comando del pipeline y se rompe al agrupar invocaciones equivalentes: `TEST_COUPLING`; proteger la garantía (la suite corre en el gate), no la forma.
