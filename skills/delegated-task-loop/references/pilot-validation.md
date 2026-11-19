# Piloto operacional: pequeño, reproducible y sin contaminación

El [inventario fijado](../examples/pilot-workloads.json) contiene tres cambios pequeños sobre el código real de agent-skills en 3769b8164186611a590468dad39f923c2b292409. No son tareas del tablero del usuario ni autorización para editar el producto publicado. Son workloads de evaluación desechables. El controlador queda fuera del worktree: usar clones independientes de la revisión fijada, cada tratamiento instala su versión en un directorio privado aparte; prohibir acceso a oráculos y resultados de otros tratamientos, publicación y credenciales de producción. Los oráculos son públicos para reproducibilidad, por tanto su aislamiento depende del host; no afirmar evaluación ciega si están accesibles. No resolver los casos en el repositorio principal antes de recoger ensayos comparables.

Primero comprobar controles positivos y defecto discriminante de la base (CI ejecuta esta fase, no agentes). En el checkout reproducible de la base:

```bash
python3 /ruta/controlador/skills/delegated-task-loop/scripts/pilot.py baseline-check --checkout /ruta/base
python3 /ruta/controlador/skills/delegated-task-loop/scripts/pilot.py plan
```

Guardar plan/observaciones en XDG privado, no en Git. Tier A: en el host actual ejecutar fresh/notify, handoff-amendment (resultado viejo rechazado), steward-isolation (intentos prohibidos en workspace desechable) y resource-adoption (operación real de prueba con identidad y recibo) según capacidades. Si faltan permisos efectivos o herramientas nativas, NOT_RUN y capacidades desactivadas. No lanzar binario como sustitución. Los checks Linux y Git locales validan infraestructura separadamente.

Tier B: seleccionar una tarea piloto, cuatro variantes (agente único, bucle externo, delegado anterior y delegado evolucionado); empezar por un par exploratorio, luego cuatro rotaciones por caso (48 ejecuciones planificadas, no ejecutarlas todas por defecto). Fijar mismo modelo/versión, límites, acceso, condiciones de caché, recursos y AC. Usar exactamente la tarea y rutas del manifiesto, ninguna instrucción adicional de solución. Instalar las revisiones de skill fijadas; agente único sin estas skills. El bucle externo solo si el host y el usuario autorizan su modo original; si no, NOT_RUN. No simularlo ni comparar modelos distintos como si fueran equivalentes. Preparar un worktree aislado y tablero temporal por trial, sin publicar. La diferencia de modelo por rol se evalúa en otra campaña, no en esta comparación controlada. Cada variante debe terminar con commit local y checkout limpio.

El evaluador independiente ejecuta desde controlador externo:
```bash
python3 /ruta/controlador/skills/delegated-task-loop/scripts/pilot.py verify --checkout /ruta/trial --case PILOT-01
```
Verifica revisión descendiente, diff acotado, oráculo y controles; además inspeccionar higiene, política, prueba enfocada indicada por caso y ausencia de publicación antes de aceptación. No ejecutar código de cambios no confiables fuera de sandbox; el script no sustituye aislamiento del host. Un PASS puntual no mide calidad de todo el workflow. Conservar revisiones, evidencia y ventana de reopens iguales; establecer environmentDigest común a treatments comparables, incluyendo versión de host/modelo y base. No cambiar workload/criterios a mitad de pares. El manifest fija oracle digest del controlador.

role_cost.py toma role-cost-input v1 por stdin: runId, usageBasis (misma normalización, semántica cache explícita), inventoryRef, inventoryComplete, sessions [{id,role}], observations [{id,usageBasis,totalTokens,outputTokens,evidenceRef}], elapsedMs nullable observado de inicio a aceptación/fallo. Una sesión se cuenta una vez, incluidos reintentos, roles auxiliares y supervisor. Si un handle acumula intentos, entregar un total no solapado para ese handle; si se usa resume, no sumar snapshots acumulativos. No mezclar contadores de API con transcripciones parciales; unknown se conserva. El helper no autentica inventario. No sumar latencias de roles que se solapan. Transferir metrics completos al evaluate_runs.py; si faltan tokens de algún actor, omitir totalTokens. Registrar también tiempo de brief, preguntas, firstUsefulChange, pruebas redundantes, gestión/Steward y defectos/reopens con fuentes observadas.

El plan v2 fija cases/pairs/variants/candidate; la falta de observación no es cero ni éxito. Guardar resultados parciales y fallos. Comparar contra cada baseline y exigir calidad comparable, no solo menor latencia. Primer objetivo: demostrar un caso end-to-end en el host, sin duplicar recursos ni publicar. Ampliar solo si hay utilidad; 48 es diseño máximo de esta ronda, no un requerimiento de ejecución automática.
