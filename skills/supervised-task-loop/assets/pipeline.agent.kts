// =============================================================================
// El bucle que cierra una tarea del tablero por sesion, en local con PipelineK.
// =============================================================================
//
// **Por que existe este fichero.** Una sesion que cierra muchas tareas seguidas acumula
// contexto hasta que tiene que compactar, y despues de compactar ya no sabe que habia
// hecho: vuelve a leer el repositorio, vuelve a derivar el plan y vuelve a lanzar la misma
// medicion. Las mediciones del 18 de noviembre lo dicen en numeros: 28 y 76 compactaciones en
// dos sesiones, una mediana de 160 mil tokens de contexto por turno, y alrededor del sesenta
// por ciento del tiempo de shell dedicado a esperar en vez de trabajar.
//
// **Que es este fichero.** Un driver, y solo eso. Abre una sesion por tarea, cada una con el
// contexto en cero, y mide lo que cada una entrego. No juzga codigo, no concede a una tarea
// su estado terminal, y no reimplementa ninguna puerta: el pull request paga
// `tools/ci-pr.sh`, el bloque de diez paga `./gradlew check`, y el tablero es la unica
// autoridad sobre lo que esta hecho.
//
// **Que cruza el limite entre sesiones.** Exactamente dos cosas: el tablero, que dice que esta
// hecho, y el documento de handoff, que dice como fue la anterior. El handoff vive en el
// tablero, se escribe con la CLI de Backlog.md, y es el unico estado que hereda la sesion
// siguiente.
//
// **No se pasan rutas.** PipelineK ya corre cada etapa en su workspace: el cwd del shell ES
// el workspace, y los scripts viven junto a este fichero en `scripts/`. El runtime resuelve
// solo el tablero, el directorio de estado y su propia situacion, y este fichero solo tiene
// que saber cuantas sesiones abrir y cuanto puede durar cada una.
//
// Para ejecutarlo:
//
//   # desde la raiz del run, donde viven este fichero y scripts/
//   python3 scripts/agent_run.py
//
// O a mano:
//
//   state="${XDG_STATE_HOME:-$HOME/.local/state}/pipelinek/$(basename "$PWD")"
//   mkdir -p "$state"
//   pipelinek run --workspace "$PWD" --db "$state/run.sqlite" \
//     --control-root "$state/control" ./pipeline.agent.kts
//
// Entorno (esto es comportamiento, no rutas):
//
//   AGENT_MAX_TASKS          cuantas sesiones abre este run (por defecto 3)
//   AGENT_TASK_TIMEOUT_MIN   el techo de una sesion (por defecto 90)
//   AGENT_PROFILE            el perfil de agente que usa cada sesion (por defecto cuenta-6)
//   AGENT_BARE               1 abre la sesion sin los hooks de plugin (por defecto 0: el flag
//                            apaga tambien el login de claude.ai con el que se autentican estos
//                            perfiles, y una sesion nueva no hereda ninguna mision de continuum)
//   AGENT_RUNTIME            donde estan los scripts, relativo al workspace (por defecto
//                            ./scripts). Solo hace falta si el runtime no vive al lado.

// La configuracion llega por el entorno (el lanzador `agent_run.py` la carga) o, si alguien
// lanza la pipeline a mano, por `agent-loop.env`. El entorno gana al fichero.
fun leerConfig(): Map<String, String> {
    val casa = System.getenv("HOME") ?: ""
    val candidatos = listOfNotNull(
        System.getenv("AGENT_LOOP_ENV"),
        "./agent-loop.env",
        if (casa.isEmpty()) null else "$casa/.config/agent-skills/supervised-task-loop.env",
    )
    val fichero = candidatos.firstOrNull { java.io.File(it).isFile } ?: return emptyMap()
    return java.nio.file.Files.readAllLines(java.nio.file.Path.of(fichero)).mapNotNull { linea ->
        val limpia = linea.trim()
        if (limpia.isEmpty() || limpia.startsWith("#")) return@mapNotNull null
        val corte = limpia.indexOf('=')
        if (corte <= 0) return@mapNotNull null
        val clave = limpia.substring(0, corte).trim()
        val valor = limpia.substring(corte + 1).trim().trim('"', '\'')
        if (clave.isEmpty()) null else clave to valor
    }.toMap()
}

val config = leerConfig()
fun valor(clave: String, defecto: String): String = System.getenv(clave) ?: config[clave] ?: defecto

val maxTasks = valor("AGENT_MAX_TASKS", "3").toIntOrNull() ?: 3
val taskTimeoutMin = valor("AGENT_TASK_TIMEOUT_MIN", "90").toLongOrNull() ?: 90L
// Donde viven los scripts del runtime. Relativo al workspace de la pipeline.
val runtime = valor("AGENT_RUNTIME", "./scripts")

pipeline {
    stages {
        stage("preflight") {
            // **No se gasta nada hasta que la maquina puede responder.** Una sesion es un
            // recurso caro, y enterarse de que `gh` no esta autenticado despues de la primera
            // tarea es enterarse tarde.
            sh("""python3 "$runtime/agent_preflight.py"""")
        }

        stage("handoff") {
            // **El estado que cruza sesiones se escribe antes de que empiece la sesion.** El
            // documento se crea la primera vez con su esqueleto, se lee el estado de la ronda y
            // se renderiza el prompt desde la plantilla.
            sh("""python3 "$runtime/agent_handoff.py"""")
        }

        for (iteration in 1..maxTasks) {
            stage("task-$iteration") {
                // **Una sesion, una tarea, contexto en cero.** La sesion es un proceso nuevo:
                // no hay contexto que compactar ni nada que olvidar. Lo que entrega se mide
                // contra el tablero, y la medida es el veredicto de la etapa.
                //
                // Aqui NO hay `retry` a proposito. Un reintento abriria una SEGUNDA sesion
                // sobre la misma tarea mientras la primera puede seguir viva, y dos agentes
                // sobre un mismo worktree es peor que una etapa fallida. La iteracion es
                // idempotente, asi que relanzar la etapa es seguro y no repite el trabajo.
                timeout(time = taskTimeoutMin, unit = "MINUTES") {
                    sh("""python3 "$runtime/agent_iteration.py" $iteration""")
                }
            }
        }

        stage("evidence") {
            // **Los recibos del run se quedan con el run.** El informe de cada iteracion vive
            // en el directorio de build, que git ignora, y archivarlo es lo que permite leer
            // el veredicto sin la terminal que lo produjo.
            archiveArtifacts(
                artifacts = "build/reports/agent-loop",
                allowEmptyArchive = true,
            )
        }
    }
}
