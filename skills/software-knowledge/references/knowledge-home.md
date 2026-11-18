# Knowledge Home: ubicación privada elegida al inicializar

La base autoritativa nunca se coloca por defecto en el repositorio de código. El patrón [Home Repo](https://www.aihero.dev/the-home-repo-pattern) se adapta a una colección privada con referencias a repositorios; si ya existe Backlog.md en el Home Repo, **se reutiliza esa autoridad y es la opción elegida**, no se crea otra base. Una base es un proyecto de conocimiento lógico: varios repos de código pueden apuntar al mismo ámbito y a sus IDs nativos; los bounded contexts, tags y referencias distinguen componentes. No volver a registrar un mismo Backlog raíz con otro project ID. Federar solo autoridades realmente distintas.

## Elección explícita

1. Localizar binding por raíz de código conocida, sin escanear el home ni leer secretos.
2. Si no hay binding, inspeccionar un Home Repo explícitamente identificado por el usuario/host (instrucciones existentes, no heurísticas de nombres). Si tiene un Backlog inicializado, elegir home-repo + backlog tras confirmar privacidad. Si no existe, ofrecer user-local como predeterminado y git-ignored como opt-in. Un Home Repo no necesita contener software de esta skill.
3. Planificar antes de inicializar. Seleccionar proyecto lógico estable, todas las raíces de código conocidas, proveedor y modalidad. No crear automáticamente repos Git ni Backlog, trasladar contenido existente, instalar CLI ni cambiar configuración. La confirmación de privacidad del Home Repo es una declaración del host, no comprobación de permisos remotos. No publicar a repos públicos, no almacenar secretos. No usar el auditor de artefactos de un repo de código para retirar Backlog de un Home Repo autorizado.
4. Guardar binding privado y reutilizarlo. Si deja de ser válido, detener operaciones gestionadas y revisar; no crear otra autoridad ni migrar automáticamente.

    python3 scripts/knowledge_home.py locate --repo /work/pipeline-kotlin
    python3 scripts/knowledge_home.py recommend --home-repo /work/home

Home Repo existente (mismo project ID para un único Backlog que abarca varios repos):

    python3 scripts/knowledge_home.py plan --project ecosystem --repo /work/pipeline-kotlin --repo /work/fabric --mode home-repo --provider backlog --home-repo /work/home --confirm-private-home
    python3 scripts/knowledge_home.py init --project ecosystem --repo /work/pipeline-kotlin --repo /work/fabric --mode home-repo --provider backlog --home-repo /work/home --confirm-private-home --confirm

Los documentos, tareas y decisiones permanecen en el Backlog del Home Repo, gestionado por CLI/MCP desde su raíz. No crear un directorio knowledge/ paralelo. Para un Home Repo sin Backlog, elegir markdown y una raíz dedicada nueva; alternativamente preparar Backlog mediante su propio flujo autorizado antes de hacer binding.

Sin Home Repo:

    python3 scripts/knowledge_home.py init --project demo --repo /work/demo --mode user-local --provider markdown --confirm

El directorio de datos durable sigue el [estándar XDG](https://specifications.freedesktop.org/basedir/): por defecto ~/.local/share/software-knowledge/projects/<hash>. Configuración de ubicación en ~/.config/software-knowledge/bindings-v1/<hash>.json. Snapshots derivados en ~/.local/state/software-knowledge/snapshots-v1/<hash>.json, no en el repo. SQLite como antes en ~/.cache/software-knowledge/index-v1. Se admiten overrides XDG absolutos fuera de Git. El nombre se deriva del ID estable, no de una ruta de checkout. Los nuevos directorios de datos/bindings/snapshots gestionados tienen modo 0700 y los JSON 0600 en POSIX. Los documentos editados por el host deben respetar permisos y políticas del área. No cifrado ni garantía contra procesos del mismo usuario.

Modo ignorado: elegir raíz dedicada (por defecto /work/demo/.knowledge), comprobar que ya esté ignorada íntegramente y que no tenga ficheros en el índice. Se recomienda exclusión local en .git/info/exclude si no se quiere modificar el repo compartido. No editar ignore ni quitar tracked files automáticamente; ignorar no protege contra git add -f, historial o copias. Revalidar al resolver. Una base con Backlog requiere seleccionar una raíz ya inicializada y privada según modo. No adoptar automáticamente contenido Markdown no vacío; migración requiere revisión y copia privada.

## Uso gestionado

    python3 scripts/knowledge_home.py resolve --project ecosystem
    python3 scripts/capture_backlog.py --home ecosystem --confirm-cli-read --task TASK-1
    python3 scripts/knowledge.py --home ecosystem context --anchor task:TASK-1
    python3 scripts/knowledge.py --home ecosystem --cache search "execution"
    python3 scripts/knowledge.py --home demo overview

capture --home usa el Backlog real de la raíz registrada y las restricciones locales de captura; guarda snapshot derivado privado mediante escritura atómica y devuelve solo metadatos, no el corpus por stdout. El snapshot es parcial y reemplazable, no autoridad ni prueba de vigencia. Recapturar al cambiar fuente/TASK/docs. El modo sin caché sigue por defecto. El modo gestionado Backlog comprueba snapshot y binding antes de indexar; añade una lectura de validación. No copiar snapshots a Git ni publicar resultados privados. Los comandos previos con --corpus, --markdown o --root siguen siendo entradas explícitas para interoperabilidad y tests, no una política de almacenamiento: el host debe garantizar privacidad de su origen, salida y temporales. No exportar a repo de código y usar solo destinos privados explícitos; export es una copia derivada.

## Límites

No hay migración/rebinding automático, sincronización remota, auto-commit, daemon ni nueva autoridad. El bloqueo de inicialización evita registros simultáneos superpuestos; si un proceso muere, revisar el lock local antes de retirarlo. Los checks no confieren permisos. Si se cambia ubicación o miembros del ecosistema, revisar y conservar evidencia antes de un futuro flujo de reconfiguración; nunca borrar contenido por resolver un binding inválido.
