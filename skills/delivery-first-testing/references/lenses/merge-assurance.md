# Lente: merge rápido con señal honesta

**Pregunta:** ¿el cambio integra sin romper los compromisos relevantes? Verificar build/compilación incrementales, lint útil, contratos públicos afectados, unitarios/component tests, un smoke de consumidor si necesario y selección conservadora para cambios transversales. No compilar artefactos release completos por defecto.

Usar la autoridad CI local existente (PipelineK, Gradle, cargo, pnpm). Si existe selector, comprobar que sus decisiones afectan a **las tareas ejecutadas**, no solo imprimen un plan mientras corren todas. Mantener un negativo de runner que se ejecute por cambio de harness/CI, no un `exit 1` siempre al final de aceptación normal. Evitar esconder fallos con `|| true` o `exit` temprano.

**Proporcional y progresivo.** El nivel sale de la clasificación de [impacto](change-impact.md) (`docs` · `bounded` · `global`), y el veredicto publicado **nombra el carril** que lo produjo para que un verde acotado no se lea como completo. Ordenar por coste y cercanía para que un rojo llegue pronto: anillo 0 (formato, lint de lo afectado, contratos baratos) → anillo 1 (lo que cambió) → anillo 2 (sus dependientes). Ejecutar **una vez** cada prueba con **una** configuración de build por anillo: el mismo test bajo dos conjuntos de features, o un subconjunto de una suite que ya corre entera, paga compilación y tiempo sin nueva garantía.

**Un veredicto por cambio.** Si el gate de merge ya es la autoridad, no exigir además una batería local completa antes del PR: el inner loop usa lo afectado y el gate decide. Mientras el gate corre, la espera no es tiempo muerto: si su build está aislado (destino propio), continuar con la siguiente unidad; nunca relanzar el mismo gate en paralelo.

**Cierre:** HEAD exacto, carril y motivo del nivel, lista de pruebas ejecutadas y no ejecutadas, salida/outcome coherente; PASS indica cobertura esperada para merge, no certificación completa de release.
