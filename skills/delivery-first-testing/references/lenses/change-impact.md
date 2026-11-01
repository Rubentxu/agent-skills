# Lente: impacto y selección mínima

**Pregunta:** ¿qué comportamientos y garantías podría alterar este cambio? Inspeccionar diff real, usos y consumidores, build graph, contratos públicos y datos persistidos. Prefiere capacidades y dependencias reales a listas de paths exactos. Un archivo renombrado sin cambio semántico no exige registrar una nueva capacidad; una nueva ruta pública sí.

Seleccionar tests por módulo/capacidad y dependencia inversa; añadir un smoke de frontera para cambio público. `unknown` o riesgo de infraselección se escala, no se convierte en selección vacía. Cambios de docs solo pueden ejecutar lint documental si no afectan código generado, release assets o documentación consumida como producto.

**Nivel por radio, no por costumbre.** Clasificar el diff en `docs` (nada que se compile o empaquete: comprobar que ningún build incluye esos ficheros, p. ej. `include_str!`, codegen o assets, y correr los tests que **leen** documentos del repo), `bounded` (componentes cambiados + sus dependientes inversos, leídos del grafo real de build: manifiestos, imports) y `global` (manifiesto raíz, toolchain, lockfile sin delta legible, fixtures compartidas o cualquier duda). Dentro de un componente grande, bajar a módulo: módulo cambiado → módulos que lo importan → sus tests. Un cambio en el **propio harness** se juzga ejecutando las etapas que cambiaron o que usan el script cambiado, no la batería de producto entera.

## Fitness del selector

Un selector que recorta pruebas puede dar verdes falsos con la misma cara que uno correcto. Antes de confiar en él y en cada cambio suyo:

- **Dirección:** un cambio en una dependencia alcanza a quienes la usan, no al revés. Caso mínimo: base compartida → incluye a sus consumidores; hoja → solo ella.
- **Fallo cerrado:** diff vacío, ruta desconocida, manifiesto/toolchain → nivel `global`, nunca selección vacía.
- **Cobertura frente a un oráculo independiente** (otra forma de ver dependencias, p. ej. nombres que solo define un módulo y que otro menciona fuera de comentarios/strings): exigir un mínimo (≥98 %) y que los fallos sean explicables.
- **Controles negativos:** romper el selector a propósito (invertir aristas, ignorar un tipo de import) debe poner su contrato en rojo.
- **Reproducción sobre historial:** pasar el selector por los últimos N cambios fusionados para estimar ahorro y tamaño típico de selección **antes** de adoptarlo; es hipótesis de ahorro, no medición de escapes.
- **Red y bucle de escape:** batería completa periódica en la rama principal; un rojo allí que un cambio dio por no afectado es `SELECTOR_ESCAPE` ([triaje](failure-triage.md)): se corrige la regla y su caso entra en el contrato del selector.

Si existen decenas de variantes de la misma regla, consultar [data-driven-design](data-driven-design.md): identificar particiones, límites e invariantes antes de crear más tests. En contratos costosos considerar un E2E efímero solo para la composición que no quede demostrada por contratos. Para seleccionar tests históricos, usar historial únicamente para **ampliar**, no estrechar, la selección estática hasta medir falsos negativos.

**Salida:** decisiones `run-affected`, `widen`, `defer-to-integration` con motivo, riesgo y comandos reales. No ejecutar por sí misma. Para cambios críticos (seguridad, durabilidad, artefactos, protocolo) mantener prueba discriminante en merge y RC según alcance. Contraprueba: introducir un consumidor nuevo no mapeado jamás debe producir PASS vacío.
