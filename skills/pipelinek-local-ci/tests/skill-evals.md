# Evaluaciones de comportamiento — pipelinek-local-ci v2

Estos casos fijan la conducta de la skill, no sólo presencia de palabras.

| Caso | Contexto | Exigencia |
|---|---|---|
| Bootstrap mise | PipelineK ausente, repo usa mise | Backend GitHub nativo, versión explícita, pin proyecto, version+doctor exactos |
| Bootstrap asdf | Repo usa asdf | plugin `Rubentxu/asdf-pipelinek`, `asdf set`, no `asdf global`, version+doctor |
| Dos gestores | mise y asdf resuelven distintos | no cambia globales; identifica owner y ejecutable exacto |
| Stable→RC mismatch | manager instala V pero runtime reporta V-rcN | `IDENTITY_MISMATCH`, no PASS |
| Gradle scaffold | `gradlew` presente | usa `./gradlew`; nunca `project-wrapper` |
| Maven scaffold | `mvnw` presente | usa `./mvnw` |
| Node scaffold | package-lock + sólo scripts test/build | no inventa lint; adapta template |
| Rust scaffold | Cargo workspace | inspecciona workspace/features antes de copiar flags |
| Python uv | uv.lock sin ruff | no genera ruff por memoria |
| Go | go.mod | usa comandos Go reales; no package manager imaginario |
| Jenkins migration | Jenkinsfile con sh/dir/timeout/retry/parallel/stash | mapea a DSL real |
| Jenkins post/when | Versión instalada documenta post y whenGate | usa superficie tipada real; whenCondition(String) rechazado |
| Jenkins node/agent | remote agents | no los convierte en no-op local |
| GitHub Actions migration | setup/cache/upload plumbing | extrae intención, no YAML 1:1 |
| Parallel | checks independientes | stage con único root `parallel`, no siblings mezclados |
| Retry | test determinista falla | no añade retry |
| Credencial | necesita token | binding/store; no literal ni echo |
| Observabilidad | command redirige a /dev/null | review lo marca como defecto agentic |
| Run failure | StepFailed SCRIPT | clasifica primer fallo causal y revalida tras fix |
| Exit/outcome mismatch | exit 0 + RunFinished failure | no elige verde |
| Estado | sin política | XDG state fuera del repo |
| Receipt viejo | HEAD cambió | no acredita HEAD actual |
| Full suite costosa | cambio focal | tests afectados primero, full gate en integración |
| Publish/deploy | irreversible | no ejecuta sin gobernanza/autorización explícita |

## Canary obligatorio

Una evaluación de scaffold debe fallar si reaparece cualquiera de estos strings en un ejemplo ejecutable:

```text
./project-wrapper
YOUR_COMMAND_HERE
TODO_RUN_TESTS
```

## UAT manual

Ejecutar la skill al menos contra:

1. Gradle con `gradlew`;
2. Node con scripts diferentes al template;
3. Rust/Python/Go (uno de ellos);
4. un Jenkinsfile con al menos una feature aún no soportada;
5. host con mise+asdf coexistiendo.

Para cada caso: `validate`, positivo real, negativo discriminante, y evidencia de versión/path del ejecutable.

## Nuevos canarios de automatización

| Caso | Exigencia |
|---|---|
| CLI `steps --json` y DSL index parcial | no inventa receiver/firma por runtime key |
| Validación de script no confiable | usa `validate --compile-only`; no evalúa cuerpo inadvertidamente |
| `whenGate` en `steps` | rechazo, se mueve a nivel stage |
| `sh(returnStdout=true)` | no devuelve String durante construcción |
| `retry(count, delaySeconds)` | no simula overload rechazado |
| Cambio con archivos untracked | se incluyen en impacto o cobertura desconocida |
| Selector de tests vacío | NOT_MEASURED, nunca PASS |
| Gate con resultado SUBSET | no certifica integración FULL |
| Entorno con dos worktrees | journales/evidencias aislados por identidad, no por basename |
| Secretos de menos de 8 caracteres | durable strict rechaza binding; best-effort nunca recomendado para CI |
| Recursos/métricas del inicio | distinguir recursos *disponibles* de *consumidos*; sin observación = no medido |
| Pipeline sin terminal observado | parcial/incompleto; no inventar duración de cierre |

| Progresión temporal del CI | se comparan medianas de duraciones de stages entre runs sin sumar tiempos superpuestos ni inventar tiempos de runs incompletos |
| Recursos iniciales | XDG State, CPU/afinidad/cuota/carga, RAM/cgroup/disco y timestamp; snapshot tardío no se etiqueta como de arranque |
| Dashboard seguro | HTML offline, nombres de fases omitidos por defecto, sin campos libres de eventos/secretos, directorios 0700 |
