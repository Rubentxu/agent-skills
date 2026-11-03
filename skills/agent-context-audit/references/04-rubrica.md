# Rúbrica: filtros de recorte, puntuación y severidad

La rúbrica sirve para **comparar** dos auditorías (dos proyectos, dos turnos, antes y después).
Los pesos son un punto de partida ajustable, no un veredicto: el usuario puede sobrescribirlos
en su fichero de instrucciones.

## Los cinco filtros de recorte

Cada regla de un fichero de instrucciones se pasa por estos filtros. Una regla que falla
varios filtros se recorta antes que una que falla uno.

| Filtro | Se marca cuando | Ejemplo |
|---|---|---|
| **Por defecto** | El agente ya lo hace sin que se lo digas | "escribe código limpio", "gestiona los errores" |
| **Contradicción** | Choca con otra regla del mismo u otro fichero | un fichero exige "no abstraigas" y otro "extrae interfaces" |
| **Redundancia** | Repite algo ya cubierto en otro sitio | la misma regla en el fichero global y el del proyecto |
| **Apaño** | Se añadió para arreglar una salida concreta, no para mejorar las salidas | "cuando genere JSON, no lo envuelvas en ```json" |
| **Vago** | Se interpreta de forma distinta cada vez | "escribe de forma natural", "usa buen tono" |

**Cómo se aplica en la práctica:** cita la regla, nombra el filtro y da una razón de una
línea. No hace falta reescribir la regla en el informe: el recorte lo decide quien conoce la
norma.

**Advertencia:** un filtro sólo vale si el recorte no pierde información. "Por defecto" aplicado
a una convención específica de la casa es un error. Si dudas de un filtro, **no lo apliques**:
márcalo como "dudoso" y explica por qué dudas.

## Puntuación

Empieza en 100 y descuenta. Suelo en 0.

| Problema | Puntos |
|---|---|
| Fichero de instrucciones > 200 líneas | -10 |
| Fichero de instrucciones > 500 líneas | -20 |
| Fichero de instrucciones > 2.000 líneas | -30 |
| Reglas marcadas por los filtros, de 5 en 5 | -5 por cada grupo |
| Contradicción entre ficheros | -10 |
| Servidor MCP con más de 50 herramientas | -10 |
| Servidor MCP sin uso registrado en semanas | -5 |
| Descripción de skill de más de 60 palabras | -2 |
| Hook con `additionalContext` o `stdout` por turno | -5 |
| Índice de memoria por encima de 100 líneas | -5 |
| Umbral de ventana por encima del techo real observado | -10 |
| Versión del harness anterior a la que difiere los esquemas | -10 |
| Falta `permissions.deny` sobre directorios pesados presentes | -5 |
| `Glob` no respeta `.gitignore` (falta `CLAUDE_CODE_GLOB_NO_IGNORE=false`) | -5 |

Etiquetas: **90-100** limpio · **70-89** necesita trabajo · **50-69** inflado ·
**0-49** crítico.

**La puntuación compara, no absuelve.** Un 95 con una carga fija del 90% de la ventana sigue
siendo un problema: la puntuación mide el **desorden**, no el **presupuesto**. Pon siempre las
dos cifras juntas: la puntuación y el margen real de trabajo.

## Severidad

| Severidad | Criterio | Qué hacer |
|---|---|---|
| **CRÍTICO** | Bloquea el trabajo: bucle de compactación, turno muerto, error por ventana | arreglar primero, sin preguntar el "qué" |
| **ALERTA** | Recorta ≥ 10% del presupuesto o hace el trabajo más lento de forma medible | proponer y aplicar con aprobación |
| **INFO** | Bajo 5% o mejora de higiene | listar, no作用于 por su cuenta |

En la práctica, casi todo lo que una auditoría encuentra es INFO y ALERTA. Reservar CRÍTICO
para lo que **impide trabajar** es lo que mantiene la auditoría creíble.

## Etiquetado de cada acción

Cada hallazgo lleva una etiqueta de aplicabilidad:

| Etiqueta | Significado |
|---|---|
| `[AUTO]` | Segura, reversible y de una sola vez: se aplica sin preguntar |
| `[DECIDE]` | Tú eliges: se propone con su ahorro y su reversión |
| `[MANUAL]` | La aplicas tú: se entrega el diff o el comando exacto |

`[AUTO]` es una categoría **pequeña**. Si todo acaba siendo `[AUTO]`, el informe no ha
distinguido nada.

## Formato del informe

```markdown
# Auditoría de contexto — <proyecto>

Carga fija medida: ≈N tokens por petición (umbral W, margen ≈M tokens)
Puntuación: N/100 [etiqueta]

## Inventario

| Fuente | Scope | ≈tokens | Always-on | Veredicto |
|---|---|---|---|---|
| ... | ... | ... | sí | ... |

## Hallazgos

### [CRÍTICO] <fuente>
<Qué pasa, con la cifra.>
Ahorro: ≈N tokens por turno
Acción: `[AUTO]` <pasos exactos>
Reversión: <cómo deshacerlo>

## Top 3
1. ...
2. ...
3. ...
```

**Cada hallazgo lleva su cifra.** Un hallazgo sin número es una opinión; con número, es un
hecho que el usuario puede discutir.

## Verificación posterior

Vuelve a medir con **el mismo método** que la línea base y enséñalo:

```text
antes:  carga fija ≈295.173 tokens/petición, 117 compactaciones/sesión
después: carga fija ≈13.893 tokens/petición, 0 compactaciones
método: mismo comando, misma sesión de referencia
```

Si los dos números salen con métodos distintos, no compares: vuelve a medir.

## Lo que el informe no debe hacer

- **Recomendar subir el umbral de ventana como ahorro de tokens.** No lo es: sólo cambia
  cuándo se compacta. Es una corrección, no un recorte.
- **Proponer dividir ficheros por debajo de 200 líneas.** Un fichero universal corto es sano.
- **Marcar como bloat el cuerpo de una skill.** Sólo su descripción se carga siempre.
- **Contar los esquemas de un servidor si el harness los difiere.** Entonces el coste es el
  número de nombres y el texto de instrucciones.
- **Presupuestar el precio.** Los precios de tokens cambian por proveedor y por plan; el
  ahorro en tokens es el dato estable.
