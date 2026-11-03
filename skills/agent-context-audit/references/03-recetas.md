# Recetas: recorte por fuente, con su reversión

Cada receta dice qué se hace, cómo se deshace y qué hay que comprobar después. **Ninguna se
aplica sin copia de seguridad** cuando toca un fichero de configuración.

## Antes de tocar nada

1. Copia de seguridad de cada fichero que vas a modificar (`cp <fichero> <fichero>.bak`).
2. Anota la medición de partida con el mismo método que usarás para el "después".
3. Decide el alcance: ¿esta sesión, este proyecto o toda la máquina? **El alcance más
   pequeño que arregla el problema.**

---

## R1 · Actualizar el harness

**Cuándo:** siempre, antes de cualquier recorte manual. Una versión nueva puede diferir los
esquemas de herramientas, cambiar la política de auto-compactación o corregir el cálculo de
ventana.

```bash
claude --version          # actual
claude update             # comprueba e instala
```

**Reversión:** la versión anterior suele quedar en el directorio de versiones del propio
harness.

**Comprobar:** repetir la medición de carga fija. Es el recorte de mejor relación esfuerzo/efecto
y no exige criterio.

---

## R2 · Quitar un servidor MCP

**Cuándo:** el servidor no se ha usado en semanas, o aporta herramientas que el proyecto no
necesita.

```bash
claude mcp list                       # qué hay y en qué scope
claude mcp remove <servidor> -s user  # o -s project / -s local
```

**Los tres scopes.** Un servidor MCP puede estar declarado en la configuración global, en un
`.mcp.json` del proyecto y en un plugin. **Busca los tres antes de quitar:**

```bash
grep -rl '"<servidor>"' ~/.claude.json <proyecto>/.mcp.json ~/.claude/plugins/ 2>/dev/null
```

Si el `.mcp.json` del proyecto lo declara, quitar el global **no hace nada**: el proyecto lo
repone. Es el error más caro de esta auditoría.

**Alternativa a borrar:** moverlo a scope de proyecto, para que sólo cargue donde se usa:

```bash
claude mcp add <servidor> -s project -- <comando> <args>
```

**Reversión:** volver a añadirlo con el comando original, que el mensaje de `remove` imprime.

**Comprobar:** nueva sesión → medir `input_tokens` de la primera petición. La diferencia es el
impuesto del servidor.

---

## R3 · Recortar un fichero de instrucciones gigante

**Cuándo:** más de 200 líneas, o una proporción alta de justificación frente a reglas.

**El método que funciona: separar la regla de su historia.**

| Se queda en el fichero | Se va al historial / a una referencia |
|---|---|
| "Una prueba que ninguna mutación pone roja no es una prueba" | "porque en el ciclo X la ley sobrevivió porque la mutación era un error de compilación" |
| "Nada se borra sin cobertura equivalente demostrada" | la cronología de los cinco borrados que hicieron falta para convincinglo |
| Los códigos de salida y su significado | la historia de por qué el código 1 y el 2 se separaron |

El recorte no es "quitar líneas": es **cambiar la prosa que narra por la prosa que manda**.

```bash
wc -l -c <fichero>                       # punto de partida
cp <fichero> <fichero>.bak               # respaldo
```

Si la política es deliberadamente densa y no puedes nombrar la regla que se pierde al
recortar, **no la recortes**: dilo y pregunta. Un fichero de instruccionestoo corto es peor que
uno largo, porque la regla que falta no se nota.

**Reversión:** el `.bak` y el historial de git.

**Comprobar:** nueva sesión → los tokens de la primera petición bajan en la proporción esperada.

---

## R4 · Podar un índice de memoria

**Cuándo:** el índice tiene muchas entradas o descripciones largas.

**El objetivo es un catálogo, no un ensayo.** Una línea por lección: gancho + fichero.

Antes:

```text
- Un caso negativo sin su control lo satisface cualquier lector → fichero: leccion.md
  el «fuera de presupuesto» de H5.6 volvía «sin tamaño» por alineación; por eso todo límite lleva control
```

Después:

```text
- Todo límite lleva su control → fichero: leccion.md
  sin control, el caso negativo lo satisface cualquiera
```

**No borres los ficheros de tema**: sólo el índice. El agente los sigue leyendo bajo demanda.

**Cuidado con la realimentación:** si el harness regenera el índice automáticamente, podar sin
cortar la fuente es trabajo perdido. Comprueba si crece entre sesiones.

**Reversión:** copia del índice.

---

## R5 · Acortar descripciones de skills y agentes

**Cuándo:** el catálogo de skills/ agentes es grande o las descripciones son párrafos.

El coste por turno es **la longitud de la descripción**, no la del fichero. Una descripción
debe decir **cuándo** disparar la skill, no qué es la skill en general.

Antes: *"Investiga la arquitectura implementada con CogniCode CLI/MCP mediante preguntas,
pruebas de capacidades por lenguaje y evidencia estructurada; produce Mermaid, Structurizr,
LikeC4 y atlas en workspace externo."*

Después: *"Documenta la arquitectura de un repo Rust. Úsala al pedir diagramas C4, atlas o
estructura de un proyecto."*

**Longitudes de referencia:** ~15-25 palabras es holgado; por encima de 60 palabras es un
hallazgo.

---

## R6 · Desactivar hooks caros

**Cuándo:** un hook imprime salida o añade contexto en cada turno, o en cada compactación.

```bash
jq '.hooks | keys' ~/.claude/settings.json      # qué eventos tienen hook
```

Un hook en el evento de compactación se ejecuta **por cada compactación**: en un bucle, son
decenas. Retirarlo de ese evento es el arreglo más barato cuando hay bucle.

Clasificación de coste:

| Tipo de hook | ¿Entra en el contexto? |
|---|---|
| Escribe a un log o fichero | No |
| `stdout` en un hook de herramienta | No |
| `additionalContext` | **Sí**, en cada llamada que coincida |
| `stdout` en `UserPromptSubmit` / `SessionStart` | **Sí**, en cada turno |
| En `compact` | **Sí**, por cada compactación |

**Reversión:** copia de la configuración.

---

## R7 · Ajustar la ventana y el umbral de compactación

**Cuándo:** hay turnos muertos por ventana excedida, o compactaciones demasiado tardías.

**Regla:** el umbral va al **~85% del menor techo real observado**, no del anunciado.

El techo real se obtiene de la evidencia: el menor `input_tokens` que falló con "prompt too
long" y el mayor que pasó. Si nunca falló, no hay techo observado: usa el anunciado por el
proveedor con margen, y valida con una carga controlada.

Si el harness ofrece un **porcentaje de reserva** para auto-compactación, úsalo: es lo que el
harness espera para calcular su propio margen, y no depende del tokenizador del proveedor.

**Ojo con los perfiles:** si el harness se lanza con un fichero de configuración propio, su
bloque de entorno gana al global. Un ajuste global que "no hace nada" suele estar siendo
sobreescrito por un perfil.

**Reversión:** el valor anterior, anotado.

---

## R8 · Reducir el alcance de los ficheros de instrucciones

**Cuándo:** un fichero universal contiene reglas que sólo aplican a un subsistema.

Dos mecanismos, según el harness:

- **Ficheros de reglas con `paths:`** — se cargan sólo cuando el agente toca esos ficheros.
- **Skills** — se cargan al invocarlas, y su gancho las dispara por descripción.

```markdown
---
paths:
  - "src/api/**"
---

Las convenciones de API de este servicio: ...
```

**No compliques por gusto:** un fichero universal por debajo de 200 líneas es sano. Dividir por
dividir crea más sitios que actualizar y más reglas que se contradicen.

---

## R9 · Delegar la lectura pesada a un subagente

**Cuándo:** el agente necesita leer mucho (un `ROADMAP.md` de 400KB, un changelog, un árbol de
código) y el resultado le cabe en tres líneas.

Un subagente lee en **su** contexto y devuelve el resumen al hilo principal. El hilo principal
recibe lo que pidió, no lo que leyó.

Es la única receta que **reduce** el contexto en vez de pagarlo, y la que evita que un solo
`tool_result` grande llene la ventana de golpe.

```text
"Busca en ROADMAP.md los tres hitos abiertos de M4 y devuélveme sólo
 título, estado y fichero; no leas el resto."
```

---

## R10 · Partir la sesión por unidad de trabajo

**Cuándo:** la sesión lleva horas, la conversación ha crecido mucho y compactar ya no ayuda.

El historial es lo único que la compactación recorta. Si el contexto es mayoritariamente
conversación, la solución no es de configuración: es **cerrar y abrir sesión**.

Transfiere el estado por escrito (un fichero de notas en el repo, un recibo, el hilo del
ticket) y arranca limpio. La compacted memoria persistente sobrevive; la conversación, no.

---

## R11 · Higiene de disco (no es contexto, pero engaña)

Las sesiones viejas se acumulan en gigabytes y no cuestan tokens, pero hace la auditoría
imposible de leer y consume disco. **No es un arreglo de contexto**: archívalos aparte, y no
los borres sin副本 si alguna sesión sigue viva.

```bash
find ~/.claude/projects/<slug> -maxdepth 1 -name '*.jsonl' -mtime +1 -size +10M
```

Criterio seguro: **más de 48 horas sin modificar**. Las sesiones abiertas pueden estar
escribiendo aunque no tengan el fichero abierto de forma visible.

---

## R12 · Que el agente no lea artefactos de build

**Cuándo:** el agente recorre el proyecto y vuelve con rutas de artefactos, o un `Grep`
recursivo devuelve basura de compilación.

**Ojo: no existe `.claudeignore`.** Un fichero con ese nombre se ignora: no está en el
harness y no produce ningún efecto. Es una idea muy extendida en blogs que no es cierta
para este harness — y una receta que no aplica es peor que ninguna, porque da una
sensación de protección que no existe.

Los tres mecanismos reales, de menos a más fuerte:

### 1 · `Grep` ya respeta `.gitignore`

`Grep` salta los ficheros ignorados por git. No hay nada que configurar: si el repo ya
ignora `target/`, `Grep` no lo devuelve.

### 2 · `Glob` no lo respeta por defecto — un flag lo arregla

`Glob` encuentra los ficheros ignorados junto a los versionados. El flag que lo corrige:

```json
{ "env": { "CLAUDE_CODE_GLOB_NO_IGNORE": "false" } }
```

En el `settings.json` del usuario, para que aplique a todos los repos. Con esto, `Glob`
respeta el `.gitignore` que el repo ya tiene, y no hay que escribir una lista de
artefactos en ningún sitio nuevo.

### 3 · `Read(...)` deny rules: la segunda capa

Bloquean la lectura explícita de un artefacto, y alcanzan también a los comandos de
fichero que el harness reconoce en `Bash` (`cat`, `head`, `tail`, `sed`, `tee`) y a las
menciones `@`.

En `.claude/settings.json` del proyecto:

```json
{
  "permissions": {
    "deny": [
      "Read(node_modules/**)",
      "Read(target/**)",
      "Read(build/**)",
      "Read(dist/**)",
      "Read(coverage/**)"
    ]
  }
}
```

Sin barra inicial la regla casa a **cualquier profundidad** (un `target/` dentro de un
workspace Rust también queda fuera); con `/` inicial se ancla a la raíz del proyecto.

**Efecto secundario que hay que conocer:** una regla `Read` alcanza a los comandos de
`Bash` que leen ficheros. Un `find .` que recorra un directorio bloqueado puede ser
denegado aunque el comando en sí no apunte al artefacto. El agente debe usar `Glob` y
`Grep`, que además son las herramientas correctas.

**Lo que las deny rules NO cubren:** un `grep -r` launched sin nombrar el fichero, o un
script que abre los ficheros por su cuenta. Para eso está el sandbox
(`sandbox.filesystem.denyRead`), que es un nivel distinto.

**Regla de discernimiento:** se excluye lo **generado**, no lo **autoritativo**. Un
`ROADMAP.md` de 500KB es autoridad y debe poder leerse; lo que se le pide al agente es que
lo lea por partes, y eso se dice en las instrucciones del proyecto. Excluir un fichero de
autoridad para "ahorrar contexto" es un recorte que **daña el trabajo** — y en un proyecto
con un artefacto canónico (un `pkg/` que es la salida del build), la regla equivocada
rompe la verificación.

**Reversión:** borrar las reglas y el flag.

**Comprobar:** un `Glob` que antes devolvía `target/` ya no lo devuelve, y un `Read` de un
artefacto se deniega nombrando la regla.

---

## R13 · Verificar que la clave existe antes de proponerla

**Cuándo:** vas a recomendar un ajuste de configuración.

Una clave que no existe en la versión instalada **no hace nada** — o peor, hace algo distinto
del que crees. Antes de proponer un ajuste:

```bash
claude --version                     # la versión que la va a leer
strings "$(readlink -f "$(which claude)")" | grep -x 'CLAUDE_CODE_MAX_CONTEXT_TOKENS'
```

Si la clave no aparece, **no la propongas**: di que la versión instalada no la expone y ofrece
la alternativa (un porcentaje de reserva, si el harness lo ofrece, o el ajuste equivalente
en la configuración del proveedor).

Una recomendación que no aplica es peor que ninguna: el usuario la aplica, no ve efecto y
concluye que la auditoría no sirve.

**Reversión:** no aplica — es un requisito de la propuesta.

---

## Orden recomendado

```text
R1 actualizar el harness           (sin criterio, el mayor rendimiento)
R2 quitar MCP no usados            (el mayor ahorro inmediato)
R3 recortar ficheros de instrucciones
R4 podar memoria · R5 descripciones · R6 hooks
R7 ajustar ventana                 (cuando el resto ya está)
R9 delegar lecturas · R10 partir sesiones
```

Mide después de cada paso con el mismo método. Un recorte sin medición posterior es una
intención, no un arreglo.
