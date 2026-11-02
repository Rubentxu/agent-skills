# Diagnóstico: detectar el bucle de compactación

El síntoma "compacta y no avanza" tiene una firma medible. Esta referencia explica cómo
reconocerla y dónde está la carga fija.

## 1. La firma del bucle

Tres hechos juntos, y sólo tres:

1. **Compactaciones repetidas** en una misma sesión, muchas por hora.
2. **El contexto apenas baja tras compactar.** Si la petición siguiente a una compactación
   sigue pidiendo casi lo mismo, la compactación no recortó nada: lo que ocupa la ventana es
   carga fija, no conversación.
3. **La ventana real se agota antes del umbral declarado.** Aparece un error de "prompt too
   long" o similar, por debajo del umbral que el harness cree tener.

Si falta el segundo, el problema es otro: quizá el historial es enorme de verdad (y entonces
el recorte es por sesiones, no por configuración).

## 2. Dónde mirar

Los harnesses que registran sesiones dejan un fichero de historial por sesión, en JSON Lines.
Rutas habituales: `~/.claude/projects/<proyecto-slug>/<session-id>.jsonl` (Claude Code),
`<directorio-de-estado>/sessions/`. Cada línea es un evento.

### Contar compactaciones

```bash
f=~/.claude/projects/<slug>/<session-id>.jsonl
grep -c 'compact_boundary' "$f"          # eventos de compactación
grep -c 'Autocompact is thrashing' "$f"   # el propio harness declarando el bucle
grep -c 'Prompt is too long' "$f"         # turnos muertos por ventana excedida
```

Si el harness emite su propio aviso de *thrashing*, no hace falta interpretar nada: ya lo ha
diagnosticado. Ese aviso aparece cuando el contexto se rellena hasta el límite en pocos turnos
varias veces seguidas.

### Ver el contexto real por petición

```bash
jq -r 'select(.type=="assistant" and .message.usage != null)
       | [.timestamp, .message.usage.input_tokens,
          .message.usage.cache_read_input_tokens] | @tsv' "$f" | tail -20
```

`input_tokens` es lo que va en la petición. Los valores que se repiten exactamente (el mismo
número tres veces seguidas) son reintentos de la misma llamada, no turnos nuevos: contarlos
como turnos distintos infla el recuento.

### Medir la carga fija (el paso que decide todo)

El historial de sesión guarda lo que el harness **envía**, no sólo lo que el modelo responde.
En Claude Code, cada línea de tipo `attachment` es un bloque de la petición:

```bash
# qué adjuntos hay y cuánto pesan, en el fichero entero
awk '{ match($0, /"type":"[a-z_]+"/);
       if (RSTART>0) { t=substr($0,RSTART+8,RLENGTH-9); a[t]+=length($0); c[t]++ } }
     END { for (k in a) printf "%9.1f KB  %5d  %s\n", a[k]/1024, c[k], k }' "$f" | sort -rn
```

Los adjuntos queImportan para la carga fija:

| Adjunto | Qué contiene | Interpretación |
|---|---|---|
| `prompt_snapshot` | system prompt + **definiciones de herramientas** | si es enorme, las herramientas son el problema |
| `instructions` | ficheros de instrucciones + índice de memoria | carga por turno garantizada |
| `mcp_instructions_delta` | instrucciones de cada servidor MCP | texto por servidor habilitado |
| `skill_listing` / `agent_listing_delta` | nombre + descripción de cada uno | coste de catálogo |
| `deferred_tools_delta` | **nombres** de herramientas diferidas | si aparecen, el harness difiere los esquemas |

### Descomponer los esquemas de herramientas

Si `prompt_snapshot` es el adjunto gigante, extrae las herramientas y ordénalas por tamaño:

```bash
n=$(grep -n '"prompt_snapshot"' "$f" | tail -1 | cut -d: -f1)
sed -n "${n}p" "$f" | jq -r '.attachment.tools[] | "\((tojson|length))\t\(.name)"' | sort -rn | head -20
```

Y agrupa por familia para ver quién manda:

```bash
sed -n "${n}p" "$f" | jq -r '.attachment.tools[] | "\(.name)\t\((tojson|length))"' \
  | awk -F'\t' '{ if ($1 ~ /^mcp__/) { split($1,a,"__"); fam="MCP:"a[2] } else fam="builtin"
                 b[fam]+=$2; c[fam]++ }
                 END { for (f in b) printf "%-16s %4d tools  %7.0f KB\n", f, c[f], b[f]/1024 }' | sort -k4 -rn
```

Un solo servidor con **más de 50 herramientas** es un hallazgo por sí solo: la regla general
es que por encima de 20-30 herramientas el modelo empieza a confundir herramientas similares,
ignorar descripciones y elegir mal, incluso si el contexto sobrara.

### Ver si el harness difiere los esquemas

Si aparece `deferred_tools_delta` con nombres de herramientas MCP, el harness **carga los
esquemas bajo demanda**: el coste por turno es el nombre (~10-15 tokens), no el esquema. En
ese caso, el "gasto" de un servidor MCP se mide por sus nombres e instrucciones, no por sus
esquemas completos.

Esto cambia la conclusión: antes de culpar a un MCP por sus esquemas, comprueba si están
diferidos. Si lo están, el problema es la **cantidad de servidores** y el **texto de sus
instrucciones**, no el número de herramientas.

## 3. La ventana real del modelo

El harness calcula una ventana efectiva según lo que conoce del modelo. Si el modelo no está
en su catálogo (un modelo propio, un proxy, otro proveedor), esa ventana es una **suposición**.
Búscala en el registro de depuración:

```bash
grep -a 'effectiveWindow\|autocompact' ~/.claude/debug/*.txt | tail -5
```

Y contrasta la suposición con la realidad: busca los turnos que fallaron por ventana y los que
pasaron, y mira el tokens en cada caso. El **menor** de esos tokens de fallo es el techo real
aproximado.

**Regla para elegir el umbral:** ponlo al ~85% del *menor* techo real observado, nunca del
anunciado. Si el umbral queda por encima del techo real, el harness compacta tarde y encima
puede quedarse sin poder compactar (el resumen necesita enviar el contexto entero).

Si el harness ofrece un porcentaje de reserva para auto-compactación, usa ese knob antes que
un número absoluto: es lo que el propio harness espera.

## 4. Antes de culpar a un fichero de instrucciones

Comprueba si el fichero se carga **una vez por turno** o **una vez por sesión**:

- Si el harness lo re-adjunta en cada petición, es carga fija: cada token se paga cada turno.
- Si lo lee bajo demanda al abrir un directorio, es on-demand: pagarlo una vez.

En Claude Code, la cadena de ficheros de instrucciones (`AGENTS.md` en el proyecto y en cada
directorio padre) y el índice de memoria se re-adjuntan **por petición**. Ése es el objetivo
más rentable: un fichero de instrucciones de 40KB son ~10K tokens en cada turno, para siempre.

## 5. La prueba que cierra el diagnóstico

Si la carga fija medida es `F` y la ventana del harness es `W`, el margen de trabajo real es
`W - F`. Calcula:

```text
margen = W - F - (reserva para compactación y salida)
```

Si `margen` es pequeño comparado con el trabajo que hace el agente, el problema es de
presupuesto, no de modelo ni de prompt. Si `margen` es amplio y aun así hay bucle, el problema
está en **qué** se carga: vuelve a `02-inventario.md` y revisa herramientas y adjuntos uno a
uno.

## 6. Otras firmas que se confunden con esta

| Firma | Cómo se distingue |
|---|---|
| Sesión interminable por historial | Tras compactar el contexto **sí** baja mucho. El recorte es por sesiones, no por configuración. |
| Turnos muertos por ventana | Errores de "prompt too long" **sin** compactaciones previas: el umbral está mal puesto, no la carga. |
| Latencia del proveedor | Compacta poco y los turnos tardan: no es presupuesto. |
| Herramienta que devuelve 40MB | Un solo `tool_result` enorme: es el **resultado**, no la carga fija. Se recorta con paginación o con un subagente que lea y resuma. |
