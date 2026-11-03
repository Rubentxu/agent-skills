# Evals

Casos donde la skill debe cambiar la decisión del agente, no sólo producir texto.

| # | Situación | Comportamiento correcto | Falla si |
|---|---|---|---|
| 1 | El agente "compacta y no avanza" en un repo | Empieza por `diagnose`: cuenta compactaciones y comprueba si el contexto **baja** tras compactar | Propone recortar el `AGENTS.md` sin medir |
| 2 | Tras compactar el contexto baja de 300K a 60K | Diagnostica historial largo, no carga fija; recomienda partir sesión | Persigue MCP y ficheros de instrucciones |
| 3 | Un servidor MCP está en el global **y** en el `.mcp.json` del repo | Busca los tres scopes y avisa de que quitar uno no basta | Quita el global y da el caso por cerrado |
| 4 | El harness lanza con un `--settings` de perfil | Comprueba el bloque `env` del perfil antes de concluir que un ajuste global "no hace efecto" | Cambia el global otra vez sin mirar el perfil |
| 5 | `input_tokens` de la primera petición es 295K y el umbral es 300K | Concluye que el presupuesto está consumido por carga fija y va a los adjuntos | Sube el umbral y lo llama ahorro |
| 6 | El harness difiere los esquemas (`deferred_tools_delta`) | Dice que el coste del servidor es nombres + instrucciones, no esquemas | Reporta los esquemas completos como coste por turno |
| 7 | Un `AGENTS.md` de 2.500 líneas pero denso y normativo | Señala el tamaño, propone separar regla de historia y **pregunta** antes de recortar | Lo reescribe sin criterio y pierde una norma |
| 8 | Una skill de 600 líneas que casi nunca se invoca | Dice que **no** es bloat: sólo su descripción carga siempre | La marca como coste de contexto |
| 9 | Un índice de memoria con 100 entradas | Propone convertirlo en catálogo de una línea por lección, sin borrar los ficheros de tema | Borra los ficheros de tema |
| 10 | El harness tiene una versión anterior que ya difiere los esquemas | Recomienda actualizar primero: es el recorte de mejor rendimiento y no exige criterio | Recorta esquemas a mano |
| 11 | Un hook en el evento de compactación, en un bucle de compactación | Lo señala como multiplicador del bucle y propone retirarlo de ese evento | Lo cuenta como un hook más |
| 12 | El usuario pide "optimiza el contexto" sin más | Empieza midiendo, y explica always-on vs on-demand antes de proponer nada | Empieza a editar ficheros |
| 13 | El agente recorre el repo y vuelve con rutas de `target/` | Propone el flag `CLAUDE_CODE_GLOB_NO_IGNORE=false` y reglas `Read` deny | Crea un `.claudeignore` (no existe: no produce ningún efecto) |
| 14 | Un proyecto tiene un `pkg/` que es la salida canónica del build | No lo excluye: excluye lo generado, no lo autoritativo | Añade `Read(pkg/**)` y rompe la verificación del artefacto |

## Casos negativos

| # | Situación | Comportamiento correcto |
|---|---|---|
| 13 | El problema real es que el modelo no entiende la tarea | Tratarlo como calidad de contenido, no de presupuesto |
| 14 | El agente va lento por latencia del proveedor | Medir latencia; no tocar configuración de contexto |
| 15 | Un único `tool_result` de 40MB | Es el resultado, no la carga fija: paginar o delegar a un subagente |
| 16 | Un fichero de instrucciones universal de 150 líneas y denso | Dejarlo: está bajo el umbral y es sano |
| 17 | Hay un `AGENTS.md` gigante en un repo dormido que nadie toca | Anotarlo como deuda futura, no reescribir la política de un repo inactivo |
