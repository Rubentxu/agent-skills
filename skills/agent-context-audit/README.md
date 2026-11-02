# agent-context-audit

Audita y recorta el presupuesto de contexto de un harness de agente (Claude Code y compatibles).

## Qué resuelve

Un harness no se queda sin contexto por lo que el modelo **lee**, sino por lo que **carga sin
que nadie lo pidiera**: esquemas de herramientas, ficheros de instrucciones, índice de memoria,
descripciones de skills. Si esa carga fija se acerca al umbral de compactación, el ciclo es
ineludible: se compacta, se recorta sólo la conversación, la carga fija sigue igual, y a los
pocos turnos se llena otra vez.

## Cuándo usarla

- El agente "compacta y no avanza", o repite compactaciones muchas veces por hora.
- Se queda sin ventana a mitad de una tarea.
- Quieres saber **qué** consume el contexto de un harness, con cifras.
- El contexto se llena de golpe y no sabes por qué.

## Modos

| Modo | Para qué |
|---|---|
| `diagnose` | Confirmar el bucle de compactación y localizar la carga fija |
| `inventory` | Saber qué carga siempre y cuánto |
| `recipe` | Aplicar un recorte concreto con su reversión |
| `score` | Comparar dos estados con una rúbrica común |

## Script de medición

```bash
python3 scripts/measure_context.py --project /ruta/al/repo
python3 scripts/measure_context.py --project /ruta/al/repo --json
```

Sólo lee. Devuelve el inventario dividido en **always-on** (se paga cada turno) y **on-demand**
(sólo al invocarse), los servidores MCP declarados y en qué scope, los hooks por evento, y un
aviso cuando un servidor MCP está declarado en más de un sitio.

## Lo que esta skill hace y no hace

**Hace**: medir, distinguir carga fija de historial, proponer recortes reversibles por
prioridad, y avisar de los errores de scope que hacen que un "arreglo" no funcione.

**No hace**: reescribir la política de un repositorio sin criterio, subir el umbral de ventana
como si fuera un ahorro de tokens, ni contar como bloat el cuerpo de una skill que sólo carga
al invocarse.

## Referencias

- [`references/01-diagnostico.md`](references/01-diagnostico.md) — detectar el bucle y medir la carga fija real
- [`references/02-inventario.md`](references/02-inventario.md) — qué carga, en qué scope y a qué coste
- [`references/03-recetas.md`](references/03-recetas.md) — recortes por fuente, con reversión
- [`references/04-rubrica.md`](references/04-rubrica.md) — filtros de recorte, puntuación y severidad

## Créditos

Los filtros de recorte y la rúbrica adaptan `usage-audit` de `mathews-tom/armory` (derivada de
la guía `context-audit` de Claude Code Context Cleanup Guide, 2026). La separación
always-on/on-demand sigue la práctica de `ctxweight` (GonzaloPeriane) y `context-checkup`
(eai-org/agent-toolkit).
