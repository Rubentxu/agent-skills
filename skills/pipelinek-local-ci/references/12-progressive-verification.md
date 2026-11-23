# Verificación progresiva acotada a cambios

## Objetivo

Optimizar coste sin inventar garantías. Un resultado filtrado es `SUBSET`; NUNCA convertirlo en PASS de `FULL`. La política de cada proyecto decide cuándo exige full, certificación independiente o gates adicionales.

## Procedimiento (offline, reproducible)

1. Fijar base real `BASE` y worktree; observar `git diff --name-status BASE..HEAD`, `git diff --name-status`, `git diff --cached --name-status` y `git ls-files --others --exclude-standard`. Distinguir staged, unstaged, untracked, renames, borrados y submódulos. Una base no verificada produce `UNKNOWN_BASE`.
2. Descubrir mapa de componentes del build existente (Gradle projects, Cargo workspace, Go modules/import graph, Python packages/pytest, JS workspaces, IaC objects). Herramientas externas como CogniCode/Groma pueden enriquecerlo, pero son opcionales y NO sustituyen el grafo del build.
3. Expandir dependientes inversos y puntos de contrato: API pública, serialización, compiler/runtime, build logic, lockfiles, security, infraestructura de tests, distribución. Si la relación es incierta, ampliar a componente/ci completo o devolver `COVERAGE_UNKNOWN`; nunca dejar selección vacía como verde.
4. Orden: `IMMEDIATE` (comando afectado) → `AFFECTED` (consumidores/contract tests) → `FULL` (política de integración/batch) → `CERTIFY` (artefacto publicado y consumidor). No ejecutar todos los niveles por reflejo.
5. Ejecutar con comandos descubiertos en el repo, sin generar flags no soportados. Gradle, Cargo, pytest, Go y otros tienen mecanismos propios de incrementalidad: preferirlos a duplicar caches/heurísticas en PipelineK.
6. Comparar exit + `RunFinished.outcome`, pruebas realmente medidas, skips, artefactos y fuente. Un run sin pruebas requeridas es `NOT_MEASURED`.
7. Generar evidencia de alcance y adjuntar referencia ligera en Backlog solo si es pertinente. No exigir recibo externo por tarea.

## Riesgos especiales

- Un cambio solo documental no debe disparar E2E si no altera contrato ejecutable; sí comprobar enlaces o publicación si es la garantía pedida.
- Un cambio de DSL, motor, redactor de secretos, esquema o serializer puede afectar a todos los consumidores: ampliar cobertura.
- Tests seleccionados por nombre/glob sin coincidencias NO son éxito. Verificar reportes para discriminar tests ejecutados de cache/up-to-date.
- Las suites de integración con estado externo, secretos, recursos mutables o dependencia de reloj no permiten reutilización automática por compartir SHA.
- No usar `retry` sobre fallos deterministas, ni `|| true` para lograr verde, ni suprimir STDERR.

## Ejemplo del repositorio de PipelineK (NO receta universal)

```bash
scripts/verify-all.sh --list
scripts/verify-all.sh --stage 3 --module ':pipeline-domain'
scripts/verify-all.sh            # solo en frontera de integración acordada
```

Estos flags pertenecen al script de PipelineK. Para otros repositorios descubrir wrappers reales; no inventar que cualquier `pipeline.kts` acepta `--stage`.
