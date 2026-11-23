# DSL Jenkins-familiar: uso actual y objetivo de paridad

PipelineK busca una experiencia local familiar para usuarios de Jenkins Groovy Pipeline, pero **la paridad se acepta feature a feature**. Esta tabla es snapshot orientativo; `pipelinek validate` y la versión instalada son autoridad.

## Superficie preferible hoy

| Patrón | Estado orientativo | Uso |
|---|---|---|
| `pipeline / stages / stage` | estable | estructura |
| `echo`, `sh`, `error`, `sleep` | estable | pasos básicos |
| `writeFile`, `readFile`, `fileExists`, `deleteDir`, `cleanWs` | estable | workspace |
| `dir {}` | estable | cwd scoped |
| `withEnv {}` | estable | env scoped |
| `withCredentials {}` | estable | secretos tipados |
| `timeout {}` | estable | deadline block |
| `retry {}` | estable | reintentos |
| `waitUntil {}` | estable | polling body |
| `parallel { branch {} }` | estable | branches concurrentes |
| `archiveArtifacts` | estable | retención |
| `stash/unstash` | estable | transferencia intra-run |
| `milestone` | estable | coordinación ordinal |
| `timestamps` | estable | output decorator |
| `environment {}` | estable | declarative env |
| `options { timeout(...) }` | estable | stage-wide shell deadline |
| `catchError/warnError/unstable` | comportamiento estable, compatibilidad deprecada | no elegir para diseños nuevos sin necesidad Jenkins-compat |

## Usar con cautela

| Patrón | Estado |
|---|---|
| `checkout(scmGit(...))` | parcial; verificar plugin/versión |
| `publishHTML` | parcial; `keepAll=true` falla cerrado |
| `directives { directive(...) }` | experimental mientras evoluciona kernel |
| `registryStep/registryBlock` | experimental/plugin author surface |
| `pwd()/isUnix()` | runtime calls; verificar contexto |

## Comprobar en la composición instalada

| Jenkins-familiar | Situación |
|---|---|
| `post {}` | Implementado en stage y pipeline (7 condiciones). Confirmar versión instalada y probar finalizadores. |
| `whenGate`, `whenEnvIs`, `whenEnvPresent`, `whenAll/whenAny/whenNot` | Gates tipados de runtime existentes. `whenCondition(String)` sigue rechazado. Declarar fuera de `steps/script`. |
| `agent` | fail-closed; no allocator remoto |
| `node` | fail-closed en perfil actual |
| `git(...)` shortcut | Existe constructor/consumidor en la DSL actual; confirmar provider de SCM, credenciales, política de red y versión antes de ejecutar. |
| `load` | sin handler |
| `ansiColor` | No anunciar como soportado por mera presencia de `StepSpec.AnsiColor`: requiere superficie DSL y handler real en runtime. |

## Patrones de composición

### Scope

```kotlin
dir("backend") {
    withEnv(listOf("CI=true")) {
        sh("./gradlew check")
    }
}
```

### Budget + retry

```kotlin
timeout(time = 15, unit = "MINUTES") {
    retry(count = 2) {
        sh("./mvnw -B -ntp verify")
    }
}
```

### Parallel

```kotlin
stage("checks") {
    parallel {
        branch("lint") { sh("npm run lint") }
        branch("test") { sh("npm test") }
    }
}
```

### Artifacts

```kotlin
stage("package") {
    sh("./gradlew assemble")
    stash(name = "jars", includes = "build/libs/*.jar")
    archiveArtifacts("build/libs/*.jar", allowEmptyArchive = false)
}
```

## Regla de migración

Si un Jenkinsfile depende de una feature no soportada, no la emules de modo que el pipeline parezca verde. Mantén esa responsabilidad externa o rediseña el flujo hasta que exista un carrier/interpreter real.

## Introspección obligatoria

La tabla es orientativa y se queda obsoleta al evolucionar PipelineK. Para cada proyecto invocar `pipelinek version`, `pipelinek capabilities`, `pipelinek steps --json` y `pipelinek describe <runtime-key>`, con los mismos plugins/trust que tendrá el run. Un runtime key no es una firma Kotlin: documentar receptor, overload, valores por defecto y semántica PLAN_TIME/RUN_TIME. Consultar [descubrimiento DSL](10-dsl-discovery.md). No inferir firma exacta del nombre de un step. `validate --compile-only` sirve para compilar código no confiable sin evaluar su cuerpo; no sustituye una ejecución real.
