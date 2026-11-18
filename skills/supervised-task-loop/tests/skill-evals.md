# Evals

Casos donde la skill debe cambiar la decisión del agente, no sólo producir texto.

## Casos positivos

| # | Situación | Comportamiento correcto | Falla si |
|---|---|---|---|
| 1 | El usuario pide "que el agente siga trabajando solo en el backlog, sin que yo supervise" | Propone el bucle supervisado: una sesión por tarea, contexto en cero, tablero + handoff como único estado | Repite la tarea en un bucle `/goal` sin tope |
| 2 | Una sesión de agente se cuelga tres días y al reanudar hay dos agentes sobre la misma tarea | Explica la sesión huérfana y la guarda de PID: se espera a la anterior y se mide la suya, nunca se abre otra encima | Relanza la tarea creyendo que no había nada |
| 3 | El agente cierra la tarea, pero no escribe el handoff | Lo marca como `FAIL` aunque el PR esté fusionado: la siguiente sesión no puede continuar | Lo cuenta como PASS porque "la tarea está cerrada" |
| 4 | El trabajo del agente tarda 40 minutos y el `timeout 600` expira | Señala el timeout corto como la causa y manda esperar al fichero de veredicto con timeout holgado | Relanza el trabajo y lo remide |
| 5 | El agente abre el prompt con `sed -n` sobre un fichero de 400 KB | Le dice que use `ctx outline|symbol|usages|section`, y explica el coste en contexto | Le dice "usa grep" |
| 6 | Hay un `while ... sleep` en el script de la puerta | Lo cuenta como sondeo y explica la diferencia con una espera suelta | Lo cuenta como espera normal |
| 7 | El tablero está en `home-repo/backlog/` y los repos de producto son sus hermanos | Propone el patrón home repo: workspace agéntico = el padre, home repo = el hijo del tablero | Confunde el tablero con el workspace y hace que el agente busque las tareas en el sitio equivocado |
| 8 | El proyecto es único: el tablero está en la raíz y no hay repos hermanos | Deixa el workspace agéntico = el propio proyecto y no inventa un padre | Pide un `AGENT_WORKSPACE` que no hace falta |
| 9 | Hay dos tableros bajo el workspace | Se niega a elegir y pide el `AGENT_BOARD` explícito | Adivina uno y abre las sesiones contra la autoridad equivocada |
| 10 | El usuario pregunta "cuánto me ha costado el bucle" | Mide y da números: compactaciones, contexto por turno, ratio `Read`:shell, sondeos | Responde "bien" sin medir |
| 11 | Una iteración murió por fuera después de que la sesión acabara | Reutiliza el informe o mide la sesión que hay; no vuelve a gastar la tarea | Relanza la sesión y repite el trabajo |
| 12 | El agente propone abrir la sesión con `--bare` | Avisa de que ese flag apaga también el login de `claude.ai` con el que se autentican estos perfiles | Lo recomienda sin más |
| 13 | El `.env` del proyecto no existe | Lo crea desde la plantilla y rellena lo que se puede deducir; pregunta solo lo que no | Pregunta por el tablero, el home repo y el perfil uno por uno |
| 14 | La pipeline died y el estado del run está en el repo | Mueve el estado a `${XDG_STATE_HOME}/pipelinek/<home-repo>` y lo dice | Escribe el `.sqlite` del run dentro del árbol del proyecto |

## Casos negativos

| # | Situación | Comportamiento correcto |
|---|---|---|
| 15 | El problema real es que el modelo no entiende la tarea | Tratarlo como calidad de contenido, no de contexto: el bucle no lo arregla |
| 16 | El agente va lento por latencia del proveedor | Medir la latencia; el bucle no cambia nada de eso |
| 17 | Un único `tool_result` de 40 MB | Es el resultado, no la carga fija: paginar o delegar |
| 18 | El trabajo pesado es una suite de integración de dos horas | Medir el coste en la slice, no el número de sesiones |
| 19 | El repo tiene una convención de tablero propia que no es Backlog.md | Respetarla: la skill propone el mecanismo, no el formato |
| 20 | El usuario pide "un agente que siga hasta vaciar el backlog" sin más | Preguntar el ritmo y el techo antes de abrir sesiones: el objetivo sin tope es un bucle infinito |

## Casos ambiguos

| # | Situación | Comportamiento correcto |
|---|---|---|
| 21 | "Quiero que el agente no se quede dormido a media tarea" | Pregunta si lo que quiere es un bucle de sesiones o un watchdog de una sesión: son dos cosas distintas |
| 22 | "Pon un agente a trabajar en el repo mientras yo duermo" | Señala el coste (sesiones de horas) y propone el bucle con su tope, y su medida para poder compararlo mañana |
| 23 | "Los agentes están molestos, cierran la tarea y no dejan nada escrito" | Es el handoff: lo convierte en el contrato de la sesión y en la guarda del veredicto |
| 24 | "Haz un script que vigile que el agente no se cuelgue" | Diferencia el guard de proceso (se cuelga) del guard de sesión (no avanza): el segundo es un bucle, y lleva sus topes |

## Lo que la skill no debe proponer nunca

- Re-ejecutar trabajo ya hecho para volver a medirlo.
- Un bucle con objetivo infinito y sin techo.
- Elegir el tablero por adivinanza cuando hay más de uno.
- Escribir el estado del run dentro del repositorio.
- Dos sesiones simultáneas sobre la misma tarea.
- Contar como entrega una tarea cerrada sin handoff.
