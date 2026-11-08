# Recuperación del flujo — detectar, investigar, decidir y volver a entregar

**Mantra:** ningún agente debe consumir horas repitiendo intentos sin un avance verificable o una decisión de desbloqueo. **El objetivo no es aumentar la actividad, sino completar capacidades útiles con calidad.** Esta lente se activa en una sesión de trabajo cuando el usuario declara estancamiento o aparecen señales observables; no requiere daemon, temporizador, segundo tracker ni autorización administrativa.

## Cuándo cambiar de estrategia

- **Señales inmediatas:** el mismo error reaparece sin hipótesis nueva; dos intentos consecutivos no producen nueva información ni mejoran una prueba; una dependencia externa impide avanzar; el alcance crece sin capacidad utilizable; se investiga sin responder una pregunta concreta.
- **Punto de control orientativo:** tras **20–30 minutos de trabajo activo sin evidencia de progreso** (solo si se conoce el tiempo transcurrido), detener la repetición del enfoque y elegir una alternativa. **Antes de acumular una hora sin un incremento usable**, replantear el alcance, las dependencias o la prioridad. Estos intervalos son avisos para actuar, **nunca gates, SLAs, métricas de productividad ni excusas para cerrar en falso**.
- **Progreso real:** comportamiento nuevo comprobable, fallo reproducido y reducido, test relevante que pasa, integración operativa, riesgo técnico eliminado o dependencia resuelta. Commits vacíos, cambios de estado, textos largos, logs repetidos y tareas nuevas por sí solos **no** son progreso.
- No inventar horarios ni inferir inactividad solo porque no hubo commits: un proceso largo con señales verificables o una espera técnica explícita no es automáticamente estancamiento. Evaluar en límites naturales de ejecución, tras fallos repetidos y al retomar sesiones.

## Ciclo de rescate dentro de la misma sesión

1. **Detectar y reconocer:** consultar la tarea vigente de Backlog.md y la evidencia técnica *necesaria* (diff, resultados focalizados, errores). Describir en una frase qué entrega falta y qué no avanza. No auditar todo el backlog.
2. **Investigar de forma acotada:** formular la menor hipótesis falsable y ejecutar **un** experimento o lectura decisiva. Limitar por coste/valor y revisar el resultado; no investigar sin criterio de parada.
3. **Tomar una decisión efectiva, sin prolongar la parálisis:**
   - **Terminar ahora:** si la funcionalidad ya cumple AC/DoD técnicos, verificar y cerrar la tarea existente.
   - **Reducir el slice:** elegir el mínimo recorrido útil e independiente sin recortar garantías de seguridad o compatibilidad ni alterar compromisos de alcance sin autorización.
   - **Desbloquear dentro de la tarea:** corregir el defecto/prerrequisito inseparable y continuar, sin crear tareas cosméticas.
   - **Crear tarea desbloqueante:** solo si se ha descubierto un trabajo técnico *independiente, acotado y comprobable* cuya resolución libera la original; relacionar IDs reales por CLI y priorizarla por el valor que desbloquea.
   - **Repriorizar o cambiar de línea:** si la dependencia exige espera externa o la investigación es antieconómica, registrar la condición de reanudación en Backlog.md y ejecutar otra tarea lista de alto valor. Pausar sin falsear Done.
   - **Escalar una dependencia externa real:** pedir permiso, decisión de producto o recurso únicamente cuando sea imprescindible; mientras tanto continuar trabajo independiente seguro.
4. **Ejecutar el camino elegido de inmediato:** no convertir el rescate en una ceremonia de aprobación, informe o nueva planificación extensa. Actualizar solo tareas/decisiones nativas de Backlog.md con hechos observados y enlaces relevantes.
5. **Comprobar resultado:** debe haber un slice entregado/cerrado, un experimento que elimine incertidumbre y siguiente implementación concreta, o un bloqueo técnico explícito con alternativa activa. Si tampoco funciona el nuevo enfoque, volver a decidir: **no repetir el mismo bucle**.

## Reglas de protección

- Nunca falsear Done, degradar pruebas o saltar permisos, seguridad o requisitos regulatorios reales para cumplir un plazo orientativo.
- Una investigación no necesita una tarea nueva salvo que tenga salida independiente; no crear un `ROADMAP.md`, `CHANGELOG.md` de seguimiento, recibo, gate ni diario paralelo.
- El WIP es una señal de dispersión, no un impedimento para desbloquear trabajo.
- Las nuevas prioridades, cambios de alcance, mutaciones de Backlog.md y asignaciones deben respetar la autoridad real del agente/usuario; la investigación y el trabajo técnico ya autorizado pueden continuar.
- Esta skill no supervisa procesos en segundo plano: el agente aplica la regla durante ejecuciones y revisiones con evidencias disponibles.

**Salida mínima:** `entrega pendiente | señal observable | hipótesis probada | decisión (CONTINUAR / REDUCIR / DESBLOQUEAR / CREAR_DESBLOQUEANTE / REPRIORIZAR / ESCALAR / CERRAR) | siguiente acción técnica | evidencia`. Registrarlo en la tarea actual mediante Backlog.md, no en un fichero nuevo.
