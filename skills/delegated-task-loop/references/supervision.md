# Supervisión reactiva

Usar notificaciones y eventos disponibles, no sondeos del agente. Diferenciar liveness, progreso verificable, alineación y coste. Si no hay eventos de progreso, solo declarar supervisión al retorno; si no hay steering no prometer redirección en vivo.

Señales útiles: pregunta del worker, nuevo criterio satisfecho, resultado, error repetido, cambio fuera de alcance, presión de contexto, agotamiento de presupuesto. Lecturas individuales, salida rutinaria de herramientas y logs no se incorporan a la conversación del supervisor. Una operación larga saludable no es un bloqueo.

Aplicar flow-recovery ante dos intentos estériles o 20–30 minutos de trabajo activo sin progreso conocido (no inventar tiempos). Formular una hipótesis falsable, experimento acotado, decisión y siguiente acción. Reanudar al worker si conoce el problema; sustituirlo solo tras parada confirmada y checkpoint recuperable. Evitar tormentas de reintentos; máximo inicial dos intentos por tarea, reajustable por autorización.

Goldfish por riesgo: none/lite/focused/deep según la skill proveedora. Solicitar antes de implementar cuando la incertidumbre arquitectónica sea alta; revisar resultado cuando el impacto lo exija. El revisor no escribe código ni estados.

Self-check del supervisor al finalizar cada tarea: objetivo, evidencias, repeticiones, contexto, presupuesto, bloqueos. La única respuesta normal a un evento rutinario es no intervenir. El host conserva los límites reales y cualquier permiso de cancelación.

Si hay eventos nativos, aplicar el [reductor](event-supervision.md) antes de enviar nuevas señales al LLM; conservar solo la proyección y referencias. No afirmar que el helper despierta por sí mismo a un agente inactivo.

Usar [telemetría y liveness](telemetry.md) para observar sin incorporar transcript al LLM. Silencio prolongado dispara steer/reconciliación, no muerte; mantener PENDING y esperar operación atribuida. Preparar solo la siguiente candidata y revalidarla al delegar; no invertir en lotes de briefs obsoletos. Medir deuda de contexto y coste de intervención.
