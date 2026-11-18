# 04 — Las eventualidades

Las que se encontraron de verdad, con su síntoma, su causa y su arreglo. Todas están
resueltas en el runtime; esta lista es para que no se vuelvan a buscar.

## 1. `--bare` apaga el login

**Síntoma**: la sesión responde "Not logged in" y no arranca.

**Causa**: `--bare` apaga los hooks de plugin, pero también apaga el login de `claude.ai`, y
los perfiles de esta máquina se autentican con `CLAUDE_CODE_OAUTH_TOKEN`.

**Arreglo**: `--bare` es un parámetro (`AGENT_BARE`), y por defecto **no** se usa. El
contexto en cero lo garantiza el **proceso nuevo**, no el flag: una sesión nueva se registra
con `active: false, mode: manual` y no hereda ninguna misión de continuum, así que su Stop
hook no re-pregunta a nadie.

## 2. La sesión sobrevive a su supervisor

**Síntoma**: la pipeline muere por fuera (SIGTERM) y, al reintentar, **dos** agentes trabajan
sobre la misma tarea y en el mismo worktree. El segundo acaba sin cerrar nada.

**Causa**: el SIGTERM no alcanza a la sesión: es un hijo de otra sesión de procesos.

**Arreglo**: tres cosas, todas en `agent_iteration.py`:

1. la sesión se abre con su **propio grupo de procesos** (`start_new_session`, o `setsid`),
   de modo que una señal que llegue al grupo de la pipeline no se la lleva por delante;
2. el PID de la sesión se guarda, y antes de abrir nada se comprueba si la anterior sigue
   viva: si lo está, se **espera** a que termine (con `pidfd`, sin sondear) y se mide la suya;
3. la iteración es **idempotente**: si ya hay informe, se reutiliza; si hay sesión sin
   informe, se mide la que hay.

## 3. El vigilante de la máquina mata el trabajo largo

**Síntoma**: la puerta o la suite no acaba nunca, y la tarea se queda sin veredicto.

**Causa**: el trabajo largo corre fuera de su slice de recursos, y el `build-guard` de la
máquina lo mata.

**Arreglo**: el trabajo largo se lanza **dentro de su slice** y con su propio grupo de
procesos, y se espera a su **fichero de veredicto** con timeout holgado
(`await_verdict.py`). Nunca un timeout corto que expire antes de que el trabajo termine.

## 4. Los subagentes en vuelo se pierden

**Síntoma**: una sesión termina y parte del trabajo no está.

**Causa**: la CLI **no espera a los subagentes**. Una sesión que termina con un subagente
vivo pierde ese trabajo.

**Arreglo**: en el prompt, el subagente se usa solo para lo que cabe en la sesión, y el
trabajo que depende de él se hace en la sesión principal. Si el subagente tenía que
sobrevivir, la sesión no puede terminar sin él.

## 5. El prompt se queda viejo entre iteraciones

**Síntoma**: la iteración 2 arranca con la foto de antes de la iteración 1, y el "aprendido"
del handoff no llega a la siguiente.

**Causa**: el prompt se renderiza una vez al principio del run.

**Arreglo**: renderizarlo **en cada iteración**. Y al reanudar una iteración, **no**
renderizarlo: el renderizado volvería a capturar la marca del handoff *después* de que la
sesión la cambiara, y la guarda diría que el handoff no se tocó cuando sí se tocó.

## 6. `--resume` no reintenta

**Síntoma**: la pipeline se reanuda y la etapa fallida vuelve a fallar sin relanzarse.

**Causa**: `--resume` **reporta** el step fallido; no lo re-ejecuta.

**Arreglo**: para re-ejecutar, `--rerun`. Es seguro porque la iteración es idempotente: la
iteración ya medida reutiliza su informe y no consume una tarea.

## 7. LaMeasurement cuenta de más

**Síntoma**: el informe dice 2.032 sondeos; en realidad son 131.

**Causa**: contar `sleep` a secas cuenta esperas sueltas.

**Arreglo**: el sondeo se define **por forma** (bucle + espera). Ver
[`03-measurement.md`](03-measurement.md).

## 8. LaMeasurement cuenta de menos

**Síntoma**: el informe dice "0 ficheros" en una entrega real.

**Causa**: el `main` local está desfasado (el agente fusiona por la API), y el informe miraba
el clon en vez del PR.

**Arreglo**: medir por el PR (`gh pr view --json files`), y elegir **el PR de la tarea** por
su id, no el primero de la ventana.

## 9. Un verde falso después de reanudar

**Síntoma**: la tarea se cerró pero el handoff no se actualizó, y el informe lo cuenta como
un fallo cuando el trabajo estaba hecho.

**Causa**: la marca del handoff se recalculó al reanudar, y para entonces ya valía "después".

**Arreglo**: la marca **antes** se guarda la primera vez (`handoff-antes.txt`) y no se vuelve
a tocar. Es la línea base de la guarda.

## 10. Ruido de la máquina

**Síntoma**: procesos que aparecen y desaparecen, o un trabajo que parece bloqueado, sin que
sea culpa de la sesión.

**Causa**: otros agentes y otros procesos de la máquina conviven en el mismo host.

**Arreglo**: el informe **mide**, no **conjetura**: si el tablero no cambió y el handoff no,
el veredicto es `FAIL` con el motivo, no una explicación. Y los recursos que la sesión dejó
vivos se sueltan al terminar, antes de que se acumulen.

## 11. El vigilante de la máquina mata al supervisor

**Síntoma**: el log de la pipeline se corta en mitad de una etapa, sin mensaje de error ni
`finished`; la sesión de agente sigue viva y **termina el trabajo igualmente**. En el
journal queda la firma: `build-guard: TERMINADO (build fuera de slice, Ns): pid=… java …`.
Medido el 18-nov-2026: el JVM de la pipeline muerto a los 828 s con 454 M de RSS; la sesión
huérfana cerró su tarea, y el re-run (`--rerun`) midió la que había en vez de abrir otra.

**Causa**: el supervisor ES trabajo largo — un proceso Java de minutos — y la máquina que
vigila recursos por slices lo mata como un build fuera de su sitio.

**Arreglo**: lanzar el supervisor dentro de su slice, desacoplado del shell:

```bash
systemd-run --user --unit=<nombre> --slice=dev-jvm.slice \
  --working-directory=<home repo> --setenv=PATH="$PATH" \
  bash -c 'python3 <runtime>/agent_run.py'
```

El `--working-directory` y el `--setenv=PATH` no son opcionales: una unidad de usuario no
hereda ni el directorio actual ni el PATH del shell, y sin ellos el runtime no encuentra la
config o el binario `pipelinek`. Además `agent_run.py` **se niega a arrancar** si la
configuración declara `AGENT_SLICE` y su propio cgroup no cuelga de ella.

## Cómo se escribe esto en el código

Cada eventualidad de arriba tiene su sitio: el runtime la resuelve, y el **test** la
comprueba. Si una eventualidad vuelve, el test que la cubría tiene que haber cambiado.
