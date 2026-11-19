# Plan de verificación transferible

Propietario: delivery-first-testing. El supervisor observa el harness y el radio real y prepara un plan antes de delegar. Usar garantías observables (AC/DoD) y candidatos de ejecución reales; cada candidato representa una invocación agrupada, no un test individual. Un comando no se ejecuta desde el compilador. Agrupar pruebas que comparten build; coste observado o null. Selección greedy ponderada por garantías nuevas/coste, no óptimo ni prueba de cobertura. Conservar pruebas obligatorias, oráculos independientes y garantías de seguridad. No diferir garantías de aceptación a integración. Unknown/global o selector no verificado requieren resolver alcance y confirmar gate global real antes de adoptar el plan reducido; no inferir PASS.

Entrada: verification-plan-input v1 con taskId, repository, baseRevision, scope, impactRef, selector (manual/verified/unverified), budgetMs, guarantees (id,statement,stage acceptance/integration) y candidates (id,argv,cwd,covers,stage worker/supervisor/integration,mandatory,independent,costMs,sourceRef). argv es un vector observado, no shell generado, cwd relativo sujeto a validación del host. El supervisor comprueba permisos, selectores, inventario y equivalencia; un coste superior al presupuesto exige decisión, no omisión.

```bash
python3 scripts/verification_plan.py < examples/verification-plan-input.json
```

El plan incluye exclusiones, cobertura pendiente, coste conocido y checks desconocidos. Transferir solo las invocaciones relevantes y referencias; si cambia impacto, emitir plan nuevo. El worker ejecuta pruebas afectadas, comunica ampliación por riesgo real, evita full suite por costumbre. El supervisor contrasta todas las garantías mediante evidencias y reejecuta solo oráculo decisivo cuando el riesgo/política lo requiere.

Para reutilizar, enviar objeto {plan,observations}, observations kind verification-observations v1 con planDigest, treeDigest, environmentDigest y receipts (id,treeDigest,environmentDigest,outcome,runnerRef,executed,failed,skipped,role worker/supervisor/ci). Digest canónico SHA-256 de JSON ordenado compacto UTF-8. TreeDigest representa árbol real incluido dirty state; environmentDigest incluye configuración, dependencias y artefacto. No reutilizar ante cambio o incertidumbre. Candidatos no acreditan que se ejecutó el runner ni que el recuento esperado se corresponde con la selección: comprobar evidencia original, número esperado, skips y oráculo. Cero casos nunca PASS. Una ejecución en vuelo compatible se adopta por referencia nativa; no relanzar durante espera. No añadir un ledger.

Las pruebas globales obligatorias conservan su autoridad CI. Diferir únicamente controles no necesarios para esa aceptación y con destino de integración acordado. No declarar entrega publicada cuando falta un gate obligatorio. Los casos sintéticos solo comprueban selección y contratos.
