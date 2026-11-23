# Credenciales y seguridad

## Principio

Los secretos deben entrar como capacidades/bindings, no como literales, argumentos visibles o texto de logs.

## Store local

La CLI actual soporta:

```text
pipelinek credentials add [--kind <kind>] <id>
pipelinek credentials list
pipelinek credentials remove <id>
pipelinek credentials rotate [--kind <kind>] <id>
```

La entrada de valores es interactiva/segura según el kind. No automatices pegando secretos en la línea de comandos.

Si el proyecto usa store alternativo, respeta `PIPELINE_CREDENTIALS_STORE` según su gobernanza.

## Binding en pipeline

Ejemplo secret text:

```kotlin
withCredentials(
    StepSpec.CredentialsBinding.string("registry-token", "REGISTRY_TOKEN")
) {
    sh("./scripts/publish-using-env.sh")
}
```

El script debe leer `REGISTRY_TOKEN` desde entorno y **no imprimirlo**.

Otros bindings existen para username/password, SSH key, secret file, certificate, zip y username-colon-password; usa sólo el kind requerido.

## Anti-patrones

- `sh("tool --token=SECRET")`;
- `echo("token=$TOKEN")`;
- persistir variables secretas en artifacts;
- escribir el store dentro del repo;
- desactivar redacción para depurar;
- convertir fallo de credencial en `|| true`.

## Revisión agentic

Ante un fallo de credencial, el agente puede reportar id/kind/binding/evento, pero nunca valor materializado. Si necesita comprobar presencia, usa `credentials list`, no lectura directa del fichero cifrado.

## Postura estricta y límites del masking

Para automatizaciones CI, certificación y publicación que usan credenciales, ejecutar PipelineK con `PIPELINE_CREDENTIALS_MASKING=required`. En el runtime actual `SecretMaskingStrictness.STRICT` es la postura por defecto del run durable; una configuración externa `best-effort` podría rebajarla, por lo que debe rechazarse en estas automatizaciones. Un secreto de menos de `SecretPatternRegistry.MIN_MASKABLE_LENGTH` (8 actualmente) no se puede enmascarar mediante el registro de patrones y el modo estricto rechaza el binding antes del step. El modo advisory puede exponerlo: no aceptarlo como CI seguro.

- `validate` evalúa el cuerpo de la DSL; usar `validate --compile-only` para código no confiable. Tratar scripts Kotlin y plugins como código con capacidad de ejecutar, no como datos.
- Nunca construir `sh(...)` con el secreto interpolado en una String Kotlin, ni introducirlo en argv, parámetros de pipeline, nombres de archivos, paths de control o telemetría.
- Preferir los bindings de archivos o descriptores frente a variables de entorno cuando el consumidor lo soporta; cerrar scope y limpiar materializaciones. Restricción de permisos de ficheros/volúmenes y herencia de entorno.
- Redactar antes de persistir, incluidos stdout/stderr, eventos, errores, salida capturada, readbacks, artifacts e informes. Los logs de depuración, `set -x`, coredumps y herramientas hijas son superficies adicionales.
- El redactor sólo conoce ciertos patrones/fragmentos y codificaciones: un proceso que transforma/exfiltra un secreto no puede quedar neutralizado universalmente por masking. Para software no confiable, usar sandbox/aislamiento OS real, egress denegado y privilegios mínimos; `--isolated` solo separa workspaces y NO constituye sandbox de seguridad.
- En tests de seguridad usar credenciales sintéticas; incluir negativo de secreto corto, divisiones de stream, registro tardío, consola, persistencia, archivo y fallo de salida. Ante garantía incumplible: FAIL/BLOCKED, nunca PASS.

Consulta los componentes reales `SecretMaskingPolicy.kt`, `BoundSecretRegistration.kt` y `StreamingRedactor.kt` del runtime; no implementar un segundo enmascarador en la skill.
