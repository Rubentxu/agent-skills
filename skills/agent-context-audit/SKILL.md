---
name: agent-context-audit
description: "Audita y recorta el presupuesto de contexto de un harness de agente (Claude Code y compatibles): mide la carga fija de cada petición, distingue lo always-on de lo on-demand, detecta el bucle de compactación continua y propone recortes reversibles por prioridad (MCP, AGENTS.md/CLAUDE.md, memoria, skills, hooks, settings). Úsala cuando el agente 'compacta y no avanza', repite compactaciones, se queda sin ventana, el contexto se llena de golpe, o consume tokens de más — aunque el síntoma se describa como 'el modelo no me entiende', 'la sesión va lenta' o 'se le olvida todo'."
metadata:
  version: "1.0.0"
---

# Auditoría del presupuesto de contexto

Un harness de agente no se queda sin contexto por lo que el modelo **lee**, sino por lo que
**carga sin que nadie lo pidiera**. Cada petición arrastra las mismas piezas: los esquemas de
herramientas, los ficheros de instrucciones, el índice de memoria, las descripciones de skills.
Si esa carga fija se acerca al umbral de compactación, el ciclo es ineludible: se compacta, se
recorta **sólo la conversación**, la carga fija sigue igual, y a los pocos turnos se llena otra
vez. El agente entonces "avanza" y "no avanza" en el mismo turno.

Esta skill **mide antes de proponer** y **separa lo que cuesta siempre de lo que cuesta al
invocarse**. Una skill de 40KB que nunca se dispara no es un problema; un `AGENTS.md` de 40KB
es un impuesto en cada turno.

> Esta skill es un router. Carga sólo la referencia del modo actual.

## Modos

| Modo | Cuándo | Referencias |
|---|---|---|
| `diagnose` | El agente compacta sin parar, se queda sin ventana o "no avanza" | `01-diagnostico.md` |
| `inventory` | Sabes que sobra contexto pero no dónde | `02-inventario.md` |
| `recipe` | Ya sabes la fuente del bloat y quieres el recorte | `03-recetas.md` |
| `score` | Quieres una medida comparable entre proyectos o entre turnos | `04-rubrica.md` |

## El principio que ordena todo lo demás

**Always-on vs on-demand.** Hay tres cosas que el harness carga en cada petición y una que
sólo carga cuando se invoca:

| | Se paga | Cuándo se paga |
|---|---|---|
| Ficheros de instrucciones (cadena `AGENTS.md`/`CLAUDE.md`, reglas sin `paths:`) | **siempre** | cada turno |
| Esquemas de herramientas MCP | **según el harness** (carga diferida si la búsqueda de herramientas está activa) | cada turno o bajo demanda |
| Instrucciones y nombres de servidor MCP | siempre, si el servidor está habilitado | cada turno |
| Descripciones de skills, agentes y comandos | siempre (sólo nombre + descripción) | cada turno |
| **Cuerpo de una skill, sus `references/`, sus `scripts/`** | **on-demand** | sólo al invocarla |
| Ficheros de tema de la memoria | on-demand | sólo al leerlos |

Sumar todo en un único número miente. Un inventario con 40K de skills que rara vez usas es
sano; el mismo 40K en `AGENTS.md` es un impuesto permanente. **Mide los dos por separado.**

## No negociables

1. **Mide, no estimes.** Los bytes del fichero y los tokens observados en la respuesta valen
   más que cualquier regla general. Si puedes leer la carga real de una petición, úsala como
   línea base; si no, declara que es una estimación.
2. **Un recorte que no se puede deshacer no es un recorte, es un cambio.** Todo lo que toques
   en configuración va con copia de seguridad; lo que toques en ficheros de instrucciones se
   enseña antes de aplicarlo.
3. **La carga fija es el sospechoso, no la conversación.** Si tras compactar el contexto apenas
   baja, el problema no es el historial: es lo que se carga siempre. Míralo antes de culpar al
   modelo o al prompt.
4. **El mismo servidor MCP puede estar declarado en tres sitios.** Global, fichero `.mcp.json`
   del proyecto y plugins. Limpiar uno no basta si los otros siguen: **busca los tres**.
5. **Un perfil puede pisar la configuración global.** Si el harness lanza con un `--settings`
   propio, su bloque `env` gana. Un ajuste global que "no hace nada" suele estar siendo
   sobreescrito.
6. **La versión del harness cambia lo que es posible.** Antes de recortar schemas a mano,
   comprueba si hay una versión nueva que ya los difiera. Descargar el harness puede valer más
   que cualquier recorte manual.
7. **No toques la política de un repositorio sin criterio.** Un fichero de instrucciones
   denso puede ser una norma deliberada y no un error. Si no puedes nombrar la regla que se
   pierde, no lo recortes: consúltalo.
8. **Mide el antes y el después con el mismo método.** Comparar un `/context` con una
   estimación por bytes no prueba nada.

## Flujo por defecto

```text
1. diagnose    ¿compacta en bucle? ¿la carga fija es el problema?
2. inventory   qué carga siempre, cuánto, y qué parte es on-demand
3. score       qué recorte paga más por unidad de riesgo
4. recipe      cómo aplicar cada recorte, con su reversión
5. verify      medir de nuevo con el mismo método y comparar
```

## Cuándo NO usar esta skill

- El problema es de calidad del modelo o de una instrucción concreta: eso es revisión de
  contenido, no de presupuesto.
- El agente no ha muerto, sólo va lento por latencia de proveedor: mide la latencia primero.
- Nadie ha medido nada todavía y la pregunta es "¿por qué va lento?": empieza por `diagnose`,
  no por cambiar ficheros.

## Referencias

- [`01-diagnostico.md`](references/01-diagnostico.md) — detectar el bucle de compactación y medir la carga fija real
- [`02-inventario.md`](references/02-inventario.md) — qué carga, en qué scope y a qué coste
- [`03-recetas.md`](references/03-recetas.md) — recortes por fuente, con reversión
- [`04-rubrica.md`](references/04-rubrica.md) — filtros de recorte, puntuación y severidad

## Créditos

Los filtros de recorte y la rúbrica de puntuación adaptan la skill `usage-audit` de
`mathews-tom/armory` (a su vez derivada de la guía `context-audit` de Claude Code Context
Cleanup Guide, 2026) y la práctica de `ctxweight` (GonzaloPeriane) y `context-checkup`
(eai-org/agent-toolkit) sobre separar carga *always-on* de carga *on-demand*.
