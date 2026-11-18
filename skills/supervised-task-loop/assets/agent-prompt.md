# Prompt de una sesión del bucle

> Una sesión = **una tarea** = **contexto en cero**. Este fichero es la plantilla que el pipeline
> renderiza en cada iteración; sus marcadores los sustituye `agent-handoff.sh`.

## OBJETIVO

Objetivo: cerrar UNA tarea del backlog.md —la siguiente que este lista— y dejarla verificable y
publicada, usando las skills backlog-agile-workflow, software-knowledge y goldfish-review. El
objetivo de fondo es vaciar el backlog, pero en esta sesion el objetivo es exactamente una tarea:
si dudas entre dos, elige la de mas valor, cierrala y sal. El bucle repite el ciclo en la
siguiente sesion, con el handoff al dia.

La entrega de valor funcional y verificable tiene prioridad sobre cualquier procedimiento
administrativo. Backlog.md es la unica autoridad para gestionar tareas, planes, prioridades,
dependencias, decisiones y seguimiento. Ningun gate burocratico puede impedir desarrollar,
verificar o completar trabajo de calidad. Ningun agente debe consumir horas trabajando sin
producir avances verificables, cerrar entregas o tomar decisiones efectivas para desbloquear el
desarrollo. Si el enfoque actual no funciona, se investiga, se decide y se cambia de estrategia.
No te olvides que es muy importante gestionar y transicionar bien los estados de las tareas del
backlog. Entre tareas y tareas hacemos un handoff.md a pasar a la siguiente sesion alojado en
backlog.md con un resumen de lo que se hizo anteriormente, luego hacemos un clear de la sesion.
Has que me sienta orgulloso de tus implementaciones en las tareas.

## WORKFLOW BASICO

- leemos backlog y elegimos UNA tarea
- creamos rama para esa tarea a partir de main
- **Sin duplicar responsabilidades**: Antes de empezar evaluamos las especificaciones y que no
  colisiona, ni se duplicaria responsabilidades que ya estan en el codigo. Aqui aplica
  goldfish-review: revision independiente del DISENO de la tarea, antes de escribir codigo.
- trabajamos en esa rama la implementacion de la tarea hasta completar con TDD y test de
  integracion solo sobre el codigo afectado.
- Corregimos cualquier problema y deuda tecnica detectada en el proceso.
- Integramos todos los cambios con un merge a main a traves de PRs, tienes autorizacion implicita.
- Hacemos limpieza de ramas en local y remoto creados para la tarea.
- **Liberamos los recursos que la tarea creo: worktrees de git, ramas locales y remotas, pods de
  Kubernetes, contenedores, clusters kind y procesos auxiliares.** Lo que se usa, se libera, el
  mismo dia que la tarea deja de necesitarlo; no se acumula para una limpieza futura.
- Cada diez tareas completadas lanzamos los gates de validaciones.
- Volvemos a empezar el ciclo desde el primer punto (en la siguiente sesion, con el handoff al
  dia).

## SKILLS

Lee y aplica estas tres, por esta ruta exacta (no dependas de que se carguen solas):

{{SKILLS}}

goldfish-review: revision independiente que no hereda tu conversacion, con un presupuesto de
subagentes real. Mide lo que te cuesta; si la tarea es trivial, no lo fuerces.

## DONDE ESTA EL CONTEXTO

- Tu **WORKSPACE AGENTICO** (donde trabajas y ves tus repos): `{{WORKSPACE_DIR}}`.
- El **HOME REPO** (el repo del proyecto: lleva el tablero y el runtime): `{{HOME_DIR}}`.
  Puede ser tu workspace mismo, o un repositorio hermano dentro de el. Tu sesion corre con el
  workspace agentico como directorio actual: si es un padre de repos, veras a todos.
- Tablero (la unica autoridad): `{{BOARD_DIR}}` — usa la CLI `backlog` desde
  `{{HOME_DIR}}`. NO edites el markdown de las tareas a mano.
- Handoff (lo que dejo la sesion anterior): `{{HANDOFF_PATH}}` en `{{HOME_DIR}}`.
- Steering del workspace: `{{WORKSPACE_DIR}}/AGENTS.md`.
- Steering del home: `{{HOME_DIR}}/AGENTS.md`.
- El repositorio de producto: lo eliges tu, entre los que cuelgan de `{{WORKSPACE_DIR}}`; antes
  de tocarlo, lee su `AGENTS.md` y su `README.md`.

## OPERACION EN ESTA SESION

- UNA sola tarea. Al cerrarla, sales. No elijas otra. No amplies el alcance.
- Contexto en cero: no busques sesiones anteriores ni leas transcripts. Tienes el handoff, el
  tablero y git.
- LECTURA: fichero >30 KB -> `ctx outline|symbol|usages|section`; <=30 KB -> `Read`. NO uses
  `sed -n` ni `grep` para leer codigo: eso llena el contexto y te hace peor. Usa
  `software-knowledge` para localizar lo que no conoces.
- TRABAJO LARGO (>2 min): lanzalo en background, DENTRO DE SU SLICE, y espera a SU FICHERO DE
  VEREDICTO con timeout holgado, con `python3 {{RUNTIME_DIR}}/await_verdict.py`. NUNCA un timeout corto
  que expire antes de que el trabajo termine. NUNCA bucles `until ... sleep` para sondear.
  - dentro de la slice, y con su propio grupo de procesos, para que el vigilante de la maquina no
    lo mate por estar fuera de su sitio y para que no se lleve por delante nada de lo de mas
    alrededor:
    `setsid systemd-run --user --scope --slice=dev-jvm.slice --quiet bash -c 'la-puerta > /tmp/x.log 2>&1; rc=$?; echo "PASS rc=$rc" > /tmp/x.verdict' >/dev/null 2>&1 </dev/null & disown`
  - un trabajo fuera de su slice lo mata el `build-guard` de la maquina: la puerta no acaba, y la
    tarea se queda sin veredicto.
- PRs: tienes autorizacion implicita para push, PR y merge. Aun asi:
  - titulo y cuerpo del PR en el estilo del repo, y SIN mencionar herramientas ni agentes (la
    politica del repo lo bloquea; ver `.github/scripts/policy-guard.sh` del repo).
  - un PR por tarea, sobre su rama, con la puerta local pagada antes de abrirlo.
- RONDA:
{{RONDA}}
  - si alguno dice "toca", esa es tu tarea y va antes que cualquier otra.
- Si te bloqueas: deja la tarea con evidencia y sal. Es honesto y la siguiente sesion sigue.

## AL TERMINAR (obligatorio)

1. Actualiza el handoff con
   `backlog doc update {{HANDOFF_ID}} --content "<markdown completo>"`.
   `--content` REEMPLAZA el cuerpo entero: manda el documento completo, manteniendo las mismas
   secciones que ya tiene. Debe decir: que cerraste y con que evidencia y SHA; que queda a medias;
   que aprendiste.
2. Libera lo que la tarea creo, y anotalo en el handoff:
   - worktree de git (`git worktree remove`) y ramas locales y remotas de la tarea;
   - pods y namespaces de Kubernetes que levantaste (`kubectl delete pod|ns`, en el cluster
     correcto: mira el contexto activo antes de borrar);
   - contenedores (`podman stop`/`podman rm`) y clusters kind (`kind delete cluster --name ...`,
     que tambien quita su contexto del kubeconfig);
   - procesos auxiliares que dejaste en marcha (servidores, daemons, watchers) y directorios de
     estado desechables.
   Lo que NO liberes porque la siguiente sesion lo va a usar, dejalo escrito con el motivo.
3. Sal. La sesion termina aqui; la siguiente arranca con contexto en cero. Si no escribes el
   handoff, esta sesion se pierde.
