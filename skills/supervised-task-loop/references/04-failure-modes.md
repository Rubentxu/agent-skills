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

## Cómo se escribe esto en el código

Cada eventualidad de arriba tiene su sitio: el runtime la resuelve, y el **test** la
comprueba. Si una eventualidad vuelve, el test que la cubría tiene que haber cambiado.

## Rerun sin sesiones fantasma

El resultado completo exige session_id, num_turns positivo e is_error boolean. Un error con cero turnos no se mide como entrega. Informe válido se devuelve inmediatamente sin recapturar tablero. Para un intento incompleto, el supervisor confirma identidad/fin del proceso, estado real del código/tablero y operaciones desprendidas; si estaban vivas, adoptar antes de repetir. No borrar iter-*; ejecutar `AGENT_RECOVERY_ITERATION=1 AGENT_RECOVERY_REF=private:reconciliation python3 scripts/agent_run.py --rerun` únicamente con evidencia real para esa iteración. El runtime no valida esa attestation, nunca autoriza saltar un PID todavía vivo. Archiva artefactos en iter-N/attempts/ con identificación nueva y refresca baseline. Popen fallido confirmado (never-launched) permite archivar sin intervención. Para sesión anterior sin identidad verificable o sin baseline, reconciliación explícita. Crear nuevo run en AGENT_STATE distinto, no limpiar a ciegas.

## Proxy y límite

AGENT_MODEL_CHECK=auto comprueba catálogo /v1/models de ANTHROPIC_BASE_URL explícito (HTTPS o loopback) con ID concreto de modelo; alias sin resolver o endpoint no compatible se declaran, no se presentan como verde. required falla cerrado, off desactiva. AGENT_MODEL_CHECK_MODEL permite ID concreto para catálogo, no impone modelo efectivo. Comprobar al preflight y antes de abrir cada intento; HTTP 401/403, modelo ausente o proveedor caído impiden lanzar. No pasar tokens por argumentos, no seguir redirects ni imprimir respuestas. El timeout de conexión/lectura es 3 s, no garantía de latencia total.

GNU timeout independiente (TERM + 15s KILL) limita el grupo de sesión aunque muera el wrapper; margen de 45s dentro del presupuesto exterior para medir. Soft/hard deadline UTC en prompt de cada intento, incluidos prompts personalizados. No promete detener procesos que llamen setsid/servicios remotos o sobrevivan fuera del grupo: reconciliar y adoptar. PID + boot ID + start ticks cuando Linux los exponga. Diagnóstico estructurado es hipótesis, extracto final corto con redacción best effort; informes siguen privados y revisar antes de publicar.

## Endurance Relay externo

El proceso de sesión no supera 60 minutos (el watchdog conserva su gracia dentro del margen exterior); el defecto de configuración cambia a 60. Para continuación de un intento parcial, el supervisor confirma parada atribuida y recursos, handoff/checkpoint vigente y tarea In Progress del baseline original. Ejecutar con `AGENT_RELAY_TASK=<id> AGENT_RECOVERY_ITERATION=1 AGENT_RECOVERY_REF=private:reconciliation python3 scripts/agent_run.py --rerun`. No usar estas variables como configuración persistente. Ledger relay-state.json fuera de Git conserva plazo de tarea desde primera sesión (120 min) y contador máximo 2; archivar intento anterior sin borrar ledger. Si falta baseline, parada, presupuesto o tarea inequívoca, no lanzar. El encargo fija taskId incluso con prompt personalizado y el informe rechaza PASS si otra tarea fue cerrada. No es reintento automático, ni certifica la attestation; si no se puede observar el host o los recursos, mantener bloqueo/reconciliar. Rerun de intento que ya pasó nunca relanza. Para legacy sin ledger, reconciliación manual, no inventar plazos. Un servicio externo puede sobrevivir al watchdog; revalidar identidad y adoptar antes de continuar.
