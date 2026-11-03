# Inventario: qué carga, en qué scope y a qué coste

Un inventario honesto responde a tres preguntas por fuente: **qué se carga**, **en qué scope**
y **si es always-on**. El script `scripts/measure_context.py` da el inventario estático;
este documento dice cómo interpretarlo y qué no puede ver el script.

## Regla de conversión

Un único número, declarado una vez:

```text
tokens ≈ bytes / 4        (para esquema JSON, código y prosa técnica)
tokens ≈ palabras × 1.3   (para prosa en español con acentos y puntuación)
```

Usa `bytes/4` como base comparable y di siempre "≈". La diferencia entre estimadores no
justifica más precisión: lo que decide una intervención es la **magnitud**, no el decimal.

## Las ocho fuentes, en orden de probabilidad de ser el problema

### 1. Ficheros de instrucciones del proyecto — *always-on*

`AGENTS.md`, `CLAUDE.md` y compañía. Se re-adjuntan en **cada petición**.

Qué buscar:

- **Tamaño en bytes y en líneas.** Por encima de 200 líneas, el coste es real y el recorte es
  posible. Por encima de 2.000 líneas, casi seguro hay narrativa en lugar de reglas.
- **La proporción entre reglas y justificación.** Un fichero que explica *por qué* pasó cada
  bug paga la explicación en cada turno, para siempre. La justificación pertenece al historial
  de git y al registro de decisiones; la regla, al fichero.
- **Duplicación en cascada.** Si un `AGENTS.md` de proyecto copia otro global, los dos pagan.
- **Reglas por tarea dentro de un fichero universal.** Las reglas que sólo aplican a un
  subsistema (convenciones de API, pasos de despliegue, una familia de tests) deben ir a un
  fichero con `paths:` o a una skill, no al fichero que se carga siempre.

### 2. Memoria persistente — *always-on* el índice, on-demand los temas

El índice de memoria (típicamente `MEMORY.md`) se adjunta en cada petición. Los ficheros de
tema sólo se cargan al leerlos.

- El índice debe ser un **catálogo**: una línea por lección con su fichero y su gancho.
- Un índice con 100 entradas y descripciones largas es un fichero de instrucciones disfrazado.
- **Cuidado con el bucle de realimentación**: si el harness escribe memoria automáticamente y
  el agente la reescribe, el índice crece con cada sesión. Podar sin cortar la fuente es
  trabajo perdido.

### 3. Servidores MCP — *always-on* el nombre y las instrucciones

Tres sitios de declaración, y basta uno para que el servidor se cargue:

| Scope | Dónde | Se ve como |
|---|---|---|
| Usuario (global) | fichero de configuración del usuario | clave `mcpServers` |
| Proyecto | `.mcp.json` en la raíz del repo | `mcpServers` |
| Plugin | manifiesto del plugin | servidor declarado por el plugin |

**Buscar en los tres antes de declarar un servidor como eliminado.** Es el error más caro de
esta auditoría: limpiar el global y que el proyecto lo reponga parece un fix que no funciona.

Coste por servidor:

- **Esquemas**: de 0 (si el harness los difiere) a decenas de miles de tokens. Depende del
  harness y de su versión.
- **Instrucciones del servidor**: un preámbulo largo del servidor puede superar el coste de
  sus herramientas. Se lee en el adjunto `mcp_instructions_delta`.
- **Nombres**: ~10-15 tokens cada uno. 30 nombres ≈ 450 tokens: no es un hallazgo.

Un servidor con más de 50 herramientas se señala por dos motivos: coste y **carga cognitiva**
(el modelo confunde herramientas parecidas, ignora descripciones y elige mal).

### 4. Descripciones de skills, agentes y comandos — *always-on*

Sólo se carga nombre + descripción. El cuerpo, al invocarse.

- Coste por entrada: la longitud de su descripción, no la del fichero.
- Una descripción de 80 palabras en lugar de 15 cuesta en cada turno, para siempre.
- **No confundas**: una skill de 600 líneas cuyo cuerpo no se carga hasta invocarla no es
  bloat. Sólo su cuenta en el catálogo.

### 5. Hooks — coste por turno según el evento

Un hook que imprime salida en `UserPromptSubmit` mete texto en **cada turno**. Un hook que
añade `additionalContext` a una herramienta lo mete en cada llamada que coincida.

- Los hooks que sólo escriben a un log no costean contexto.
- Un hook que corre en `compact` se multiplica por cada compactación: en un bucle de
  compactación, se ejecuta decenas de veces.
- Un hook por evento × muchos eventos × muchas herramientas = una suma que nadie ha medido.

### 6. Configuración del harness — *always-on* por su efecto

- **Hooks** como el punto anterior.
- **Plugins habilitados**: cada plugin puede traer hooks, comandos, agentes y skills.
- **Ajuste de ventana**: si declara una ventana por encima del techo real del proveedor,
  produce turnos muertos y compactaciones tardías.
- **Permisos**: `permissions.allow` no cuesta contexto, pero un `deny` ausente sobre
  directorios pesados permite que el agente lea lo que no debe.

### 7. Salidas de herramientas — *por turno*, no fijo

Un `tool_result` de 40MB llena la ventana de golpe. No es un problema de configuración: se
resuelve paginando, filtrando en el propio comando, o delegando la lectura a un subagente que
devuelva el resumen.

### 8. Historial de sesión — *crece*, no fijo

El historial de la conversación es lo que la compactación recorta. Si es el mayor de los ocho,
el problema es de **duración de sesión**, no de configuración: Divide la sesión por unidad de
trabajo.

## Cómo se decide el orden de trabajo

Ordena por **tokens ahorrados × reversibilidad ÷ riesgo**, no por tamaño de fichero:

| Intervención | Ahorro típico | Reversibilidad | Riesgo |
|---|---|---|---|
| Quitar un servidor MCP no usado | muy alto | alta (`claude mcp remove`) | bajo |
| Recortar un `AGENTS.md` gigante | alto | alta (backup + git) | medio |
| Podar un índice de memoria | medio | alta | bajo |
| Acortar descripciones de skills | medio | alta | bajo |
| Quitar hooks de prompt | medio | alta | medio |
| Subir el umbral de ventana | bajo (no ahorra tokens) | alta | medio |
| Actualizar el harness | **muy alto y automático** | alta | bajo |
| Partir sesiones por trabajo | alto (a largo plazo) | n/a | bajo |

Fíjate en la tercera fila de la tabla: **actualizar el harness** suele estar por encima de
todo lo demás y no requiere criterio. Antes de recortar a mano, comprueba la versión.

## Qué NO puede ver el inventario estático

El script mide lo que está en disco. Estas cosas sólo se ven en ejecución:

- **Memoria dinámica** que el harness inyecta por consulta (más allá del índice).
- **RAG en tiempo de ejecución** que tira documentos por turno.
- **Instrucciones de servidor MCP** emitidas al conectar, no declaradas en disco.
- **Hooks que devuelven `additionalContext`**, cuyo texto depende del resultado.
- **Contexto inyectado por plugins** en tiempo de ejecución.

Por eso el inventario estático es el **piso** del diagnóstico, no el techo. Si el estático es
pequeño y el contexto real es grande, la diferencia es runtime: hay que mirar la carga real de
una petición (`01-diagnostico.md`).

### 9. Lo que el agente puede leer por accidente

No es una fuente de contexto, es un **filtro**: decide qué ficheros el agente puede leer. Sin
él, un `Grep` recursivo o una exploración de directorio se carries con `node_modules/`,
`target/`, `dist/` o `build/`, y cada resultado entra en el contexto.

**No existe `.claudeignore`.** El nombre circula mucho en blogs y no hace nada: no está en el
harness. Los mecanismos reales son tres, y se acumulan:

| Mecanismo | Qué cubre | Costo |
|---|---|---|
| `.gitignore` del repo | `Grep` ya lo respeta | **cero** — el repo probablemente ya lo tiene |
| `CLAUDE_CODE_GLOB_NO_IGNORE=false` | hace que `Glob` también lo respete | un flag global |
| `Read(...)` deny rules | lectura explícita, comandos de fichero en `Bash`, menciones `@` | una regla por artefacto |
| `sandbox.filesystem.denyRead` | todo lo que abra un proceso, a nivel de SO | sandbox activado |

El caso habitual es que el repo ya tiene su `.gitignore` y basta con el flag: **no hace falta
escribir una lista de artefactos en ningún sitio nuevo**.

Lo que **no** debe hacerse: excluir ficheros que son autoridad del proyecto (roadmap,
changelog, especificaciones) para "ahorrar contexto". Eso daña el trabajo, y en un proyecto con
un artefacto canónico —un `pkg/` que es la salida del build— la regla equivocada rompe la
verificación.

## Inventario por proyecto y por máquina

Un agente que trabaja en varios repos carga la misma configuración global en todos ellos. Dos
comprobaciones Amplían el alcance:

1. **Por máquina**: los ficheros de configuración del usuario se aplican a todos los proyectos.
   Un servidor global sobrante se paga en todos.
2. **Por proyecto**: los ficheros de instrucciones y el `.mcp.json` son por repo. Un repo con
   2.000 líneas de política es un impuesto local, y un repo hermano sin nada no paga nada.
