# Bridge portable de harnesses y publicación protegida

[Volver al navegador](navigation.md) · [Claims](lenses/multi-agent-coordination.md) · [Recuperación](lenses/stalled-work-recovery.md) · [Cesión](lenses/yield-negotiation.md)

## Propiedad e integración

`harness_bridge.py` normaliza eventos **estructurados** de Claude Code, Qwen Code, Codex y wrappers ACP hacia `harness-observation-v1`, y los clasifica con `harness_signal.py`. Rechaza eventos desconocidos y descarta texto libre, prompts, transcripciones, argumentos de herramientas y credenciales. Solo acepta eventos de ciclo de vida observables; **nunca certifica la parada del proceso**. `--request-yield` es opcional: publica un `YIELD_REQUESTED` idempotente usando `multi_agent_cli.py`, exclusivamente ante errores estructurados persistentes de cuota/autenticación/facturación. No libera recursos.

| Host | Evento observable | Garantía / límite |
|---|---|---|
| Claude Code | `StopFailure` (tipo `error`), `SessionEnd` | Rate limit, auth y billing clasificados; `SessionEnd` no acredita recursos libres |
| Qwen Code | `PostToolUseFailure`, `SessionEnd` | Fallo de herramienta no implica cuota agotada; observar el error de API por envoltorio externo |
| Codex | `agent-turn-complete` del `notify` clásico | Solo fin de turno, **no** cuota, parada ni progreso material; usar señales estructuradas del host o hook compatible adicional |
| ACP | Wrapper `provider_error` tipado, `turn_complete`, `session_ending` | El host traduce eventos reales; no asumir contrato universal de error en ACP |

Ejemplo de entrada Claude Code en hook `StopFailure` por stdin:

```bash
python3 /path/skills/backlog-agile-workflow/scripts/harness_bridge.py \
  --provider claude-code --task TASK-42 --agent agent-a --claim-id claim-7 \
  --evidence-ref host:session-17
```

Qwen usa el mismo patrón con `--provider qwen-code` para `PostToolUseFailure` o `SessionEnd`. Los hooks se configuran desde la aplicación anfitriona con su mecanismo documentado, fuera de este repositorio. No instalar hooks automáticamente. Para Codex el ajuste de `config.toml` `notify` invoca el script con `--provider codex` y `--json-argument` como último argumento de configuración: Codex añade el JSON de notificación como argumento posterior. No convertir `last-assistant-message` en código de error.

Para un harness externo ACP, emitir `{"event":"provider_error","error":{"code":"quota_exhausted"}}` con `--provider acp` únicamente cuando el host realmente observa ese código. La estructura es del **wrapper**, no del protocolo ACP general.

`--request-yield --remote <home-remote> --generation N` publica una petición cooperativa; fallo de red significa resultado indeterminado y exige revisión del evento/claim en la autoridad. Para proteger el hook de latencias, mejor ejecutar la publicación desde el supervisor/host y no en el evento síncrono. El `evidenceRef` debe apuntar a una observación recuperable **sin secretos**.

## Publicación: última frontera de autoridad

Antes de publicar resultados o cerrar una tarea, el escritor debe invocar `multi_agent_cli.py verify --remote ... --task ... --actor ... --claim-id ... --generation ... --resource repo://...` y comprobar salida correcta. La comprobación es de un **instante**: GitHub/GitLab, la rama protegida o el receptor de despliegues deben imponer nuevamente la autorización en el momento efectivo de la publicación, sin que el agente pueda omitirla. Si se permite `git push` directo o credenciales de Kubernetes amplias, ningún script cliente puede garantizar fencing distribuido. Instalar como required check solo después de proteger la rama, limitar quien puede cambiar la configuración y vincular la verificación al commit/actor/ámbitos exactos.

No hay commit atómico multi-repositorio entre el Home Repo y el código: el gate del destino debe tratar la pérdida de lease, cambios de generación y particiones como denegación y solicitar revalidación. Para operaciones externas, descubrir la skill `delegated-task-loop` (si aparece en `available_skills`) y navegar a `references/resource-adoption.md` desde su propio router; usar siempre identidades nativas del proveedor.

## Rendimiento y descubrimiento

Claim nuevo: leer la vista completa de las reservas para detectar conflictos de scope; ninguna proyección vieja puede autorizar una nueva escritura. Renovar, ceder y cerrar: basta una vista del ID objetivo antes de escribir por CAS Git, sin leer 20.000 tareas. `triage` sí lee el estado completo. Para tableros personalizados pasar `--claimable-status 'Pendiente'` y el `--working-status` del proyecto; el claim recuerda su columna original y `release/recover` la restaura con protección ante cambios externos.

Todo lo anterior es *opt-in*, sin daemon, segunda BBDD ni LLM en el bucle de observación. Los eventos y etiquetas se almacenan en el Backlog.md seleccionado como autoridad; los checkpoints de ejecución permanecen fuera del árbol de código.
