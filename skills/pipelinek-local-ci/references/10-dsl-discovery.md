# Descubrimiento de DSL, step, directivas y plugins (sin alucinaciones)

## Autoridad y niveles de inspección

1. Resolver el ejecutable real y su versión: `command -v pipelinek`, `readlink -f`, `pipelinek version`, `pipelinek doctor`.
2. Inspeccionar `pipelinek capabilities`, `pipelinek steps --json` y `pipelinek describe <key>`, usando las mismas opciones `--plugin-jar` y `--plugin-trust` del run. No cargar un plugin no confiable solo para buscar firmas.
3. Si existe el índice de firmas Kotlin generado por la herramienta de producto, consultar allí `signature`, `owner/receiver`, overloads y KDoc; el catálogo `pipelinek.steps/11` enumera *claves runtime*, no overloads Kotlin ni todos los constructores.
4. Antes de editar un `.pipeline.kts`, consultar los métodos de la versión instalada. Si el índice no está presente, inspeccionar API/ejemplos incluidos y compilar una muestra mínima. Nunca inventar API.
5. Compilar con `pipelinek validate --compile-only <archivo>`. El `validate` sin esa opción EVALÚA el cuerpo del script: ejecutarlo solo si el código es confiable, en un contexto autorizado. La compilación no certifica semántica runtime.
6. Para confirmar efectos, validar con run positivo y un negativo discriminante en workspace desechable, sin credenciales reales, respetando el presupuesto del proyecto.

## Índice fuente implementado en PipelineK

La rama de PipelineK incluye `scripts/pipelinek-dsl-index.py`: genera JSON `pipelinek.dsl-signatures/v1` desde las fuentes Kotlin, sus receptores y resúmenes KDoc. Se puede filtrar con `--name sh` y combinar `--runtime-json` con la salida de `pipelinek steps --json`. La relación por nombre se marca como candidata, NO equivalente a un binding de Kotlin probado. Es una herramienta de checkout, **no un comando disponible en cada instalación binaria**; comprobar su presencia antes de usarla. La verificación final sigue en `validate --compile-only` y el runtime.

## Contratos que deben leerse junto a cada firma

- **Contexto**: `pipeline`, `stage`, `steps`, `script`, `post`, `branch`, `plugin body`. Una directiva de stage dentro de `steps`/un wrapper no tiene autoridad y se rechaza.
- **Tiempo**: Kotlin del cuerpo DSL (`if`, getters `env`) se evalúa construyendo el PLAN. Los steps son declaraciones; `whenGate/whenEnvIs/whenEnvPresent` se evalúan en el runtime. `param(name)` declara un step que devuelve un valor tipado de runtime, no una String Kotlin.
- **Propiedad del resultado**: `sh(script, returnStdout = true)` registra resultado de step, NO devuelve stdout como String en el DSL declarativo. `pwd` puede devolver marcador de construcción de plan.
- **Semántica específica**: `waitUntil` observa el outcome de los steps del body, no el booleano de un lambda. `retry(count, delaySeconds)` de política anterior se rechaza. `publishHTML(keepAll = true)` se rechaza.
- **Diferencias**: `timestamps` delimita eventos pero no decora cada línea; `milestone` coordina ordinal del run, no builds globales; `input.submitter` no es autenticación; `--isolated` divide workspaces, no un sandbox OS.
- **Directivas**: no escribir `whenCondition(String)` ni `agent`/ `node` de Jenkins por analogía. La declaración/registro real manda.
- **Código generado**: si la instalación tiene un catálogo de *firmas* separado, la reconciliación con runtime keys debe mostrar relaciones desconocidas en vez de adivinar una equivalencia 1:1.

## Descubrimiento barato para agentes

Leer índice primero, descripción de un solo símbolo después, código únicamente si todavía existe una incertidumbre concreta. No cargar todos los ejemplos al contexto. Ejecutar `pipelinek --help` si la instalación no reconoce una opción; no fabricar comandos nuevos. La función `pipelinek dsl describe` es una **propuesta futura** hasta estar publicada y verificada en la instalación usada.
