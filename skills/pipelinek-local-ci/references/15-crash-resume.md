# Reanudar una pipeline local tras caída del equipo o del proceso

## Autoridad: el motor, nunca la skill

`pipelinek run --resume` reutiliza el `runId`, el journal durable, el cursor, los steps completados y las garantías de replay del runtime, si su estado permite hacerlo. `pipelinek runs recover` es **otra operación**: reconcilia un terminal perdido cuando el trabajo ya terminó, sin ejecutar de nuevo los efectos. `runs cancel` cierra un run muerto con autorización. No tratar estas operaciones como equivalentes.

La distribución de PipelineK incluye en `tools/` el ejecutor opcional `pipelinek-run-with-metrics.py` y su helper `pipelinek-resume-state.py`. Son portables a cualquier proyecto que contenga scripts `.pipeline.kts`, no dependen de fuentes de PipelineK ni de Actions/servicios remotos. No generar un segundo framework de checkpoints en cada repositorio consumidor.

## Procedimiento recomendado para agentes

1. Resolver identidad real del producto con `command -v pipelinek`, `readlink -f` y `pipelinek version --json`. Si la instalación no dispone del helper, usar CLI nativa con los paths originales de journal/control y diagnosticar manualmente.
2. Usar el **mismo** proyecto, script, `--workflow`, argumentos y proveedor de credenciales. La sesión privada está bajo `$XDG_STATE_HOME/pipelinek/projects/<hash-worktree>/reports/executions/<session-uuid>`. Nunca copiar `--db`/control a otro contexto sin autorización.
3. Consultar `python3 <distribution>/tools/pipelinek-run-with-metrics.py --project . --script <archivo> --workflow <id> --status`. Resolver un run ambiguo con el UUID concreto.
4. Cuando haya una sola sesión elegible e inputs verificados, usar `--resume` para exigir continuidad o `--resume-or-new` en un supervisor local que solo debe iniciar uno nuevo si no hay pendiente. No usar `--new` para esquivar un run activo/incierto.
5. Ante la caída antes de recibir el LaunchReceipt, el helper consulta `last-run` del control root: solo admite un run id inequívoco. El lock del wrapper es advisory local y el lease/fencing del motor conserva la exclusión durable; no asumir que un child vivo murió solo porque murió su parent.
6. Si `inspect --state` devuelve terminal, la sesión ya terminó y no es candidata a `--resume`; si es `unobservable`, bloquear y diagnosticar. Si el journal tiene un terminal de operación pero falta el terminal de run, ejecutar `pipelinek runs recover <runId> --db <journal> --control-root <control> --dry-run` y autorizar la reconciliación real **solo** tras inspección del resultado.
7. Valorar efectos: lectura pura y build cache seguro pueden reusarse; archivos/artefactos deben confirmarse con digest; publicación, despliegue, pago, borrado, creación remota, locks y sagas necesitan idempotency keys, consultas de estado o un bloqueo manual de efectos inciertos. No prometer exactamente una ejecución de un efecto externo que no lo soporta.
8. Las credenciales persistentes **no** se guardan en el manifiesto: al reanudar se reobtienen por provider, con permisos y scopes actuales y `PIPELINE_CREDENTIALS_MASKING=required`. Nunca registrar secretos ni la línea de comandos completa en los reportes.
9. Tras recuperar, verificar outcomes terminales de steps/runs, coverage y artefactos. Una reanudación no convierte SUBSET en FULL ni certifica por sí sola el producto instalado.
10. Si hubo apagado entre dos eventos, el wall-time puede incluir downtime. Consultar métricas por intento y no atribuir todo el tiempo al CPU del workflow.

## Compatibilidad y limitaciones explícitas

- Solo hay recuperación duradera para ejecuciones que se iniciaron con `--db` y control root persistentes. Un run volátil no puede reconstruirse después de un reinicio.
- Los scripts cambiados, versiones/argumentos distintos o dos sesiones candidatas se rechazan sin selección silenciosa. Con Git se comprueba HEAD, diff y untracked visibles; **los archivos ignorados, dependencias y servicios externos no son verificables por ese fingerprint**.
- En repositorios sin Git se requiere consentimiento explícito `--accept-unverified-inputs`. No es una certificación; registrar la limitación.
- El helper usa locks POSIX para el control local; no es un HA scheduler multipuesto. Para coordinación distribuida, usar las autoridades de lease existentes de PipelineK/Fabric.
- Un plugin no confiable no puede considerarse seguro por haber pasado `validate --compile-only`. Debe tener trust, capabilities y políticas efectivas.
- Las tareas de Backlog quedan en progreso hasta que la evidencia demuestra los criterios técnicos; un run interrumpido se representa `BLOCKED/INCOMPLETE`, nunca PASS. No imponer un informe administrativo por tarea.

## Pruebas adversariales

Caída justo antes/después de LaunchReceipt; journal con último step en progreso; run con terminal pero manifiesto stale; versiones o script modificados; dos candidatos; lock ocupado; falta de journal; reintento con publicación de efecto incierto; cambios de credenciales; `--resume-or-new` iniciando uno nuevo solo cuando no hay uno pendiente. No aprobar cambios de recuperación solo con mocks: los escenarios críticos requieren kill -9, reboot simulado en proceso independiente y persistencia real SQLite/Output Plane.
