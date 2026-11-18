# Federación explícita multiproyecto

Cada corpus conserva su project y autoridad. La identidad global es el par {project,node}; los IDs locales pueden colisionar sin fusionarse. Un manifest knowledge-federation v1 enumera hasta 32 identidades de proyecto y 500 relaciones explícitas. No contiene rutas, credenciales, permisos ni descubrimiento de servicios. Tipos: uses-contract, reuses-pattern, depends-on-project, references, supersedes-reference. Son referencias declaradas, no dependencias validadas.

    python3 scripts/federation.py examples/federation.json \
      --source example-runtime=examples/corpus.json \
      --project example-runtime --node execution.terminal

El destino ausente devuelve explicit-source-required. Para resolverlo, aportar otro --source PROJECT=PATH y --follow. Se leen exclusivamente snapshots explícitos, cuya identidad debe coincidir con el manifest. Sin --follow no se proyectan datos de destinos; la consulta se ejecuta solo en el proyecto seleccionado. Con --follow se resuelve un salto entrante/saliente, conservando claim_state y cobertura del destino; si no aparece en un corpus parcial devuelve not-observed-in-snapshot, nunca inexistente. No se fusionan estados, se transfieren permisos ni se reescriben notas. No hay red, índice global, servicio o base compartida. Si el origen es Backlog/Markdown, generar previamente snapshots mediante las herramientas existentes. Mantener los manifests junto a la autoridad que decide los enlaces; contenido privado según política local.
