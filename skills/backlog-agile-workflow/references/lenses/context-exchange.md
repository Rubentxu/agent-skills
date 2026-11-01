# Lente: intercambio privado opcional de referencias

**Pregunta:** ¿cómo continuar en otra máquina sin exportar conversaciones ni crear un servicio?

1. `context_exchange.py export memory.json handoff.json > references-private.json` crea una lista blanca: pins, IDs, scope, tarea y SHA. No contiene citas, conversaciones, contenido de código ni credenciales.
2. `context_exchange.py inspect references-private.json` comprueba estructura estricta y digest de corrupción accidental. El SHA-256 **no** firma el emisor ni autentica el mensaje humano.
3. Usar un canal privado cifrado/autenticado administrado fuera de la skill. No subir el archivo a Git, Issues, PR o logs. No imponer nueva base de datos, daemon o servicio.
4. En destino, volver a leer Backlog y verificar mensajes originales, revisiones y permisos antes de reutilizar las referencias. Si el origen no puede recuperarse, mantener `UNVERIFIED`.
5. El transporte sincronizado multi-máquina es opt-in y requiere una política de retención, revocación y copias de seguridad externa explícita.

**No objetivos:** implementar cifrado casero, guardar prompts completos, considerar un bundle como autorización o prometer sincronización entre máquinas por el simple export.
