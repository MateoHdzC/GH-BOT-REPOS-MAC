# GH-BOT-REPOS-MAC

> **Daemon de Automatización de Git y Gestor de Espacios de Trabajo para macOS**

`GH-BOT-REPOS-MAC` es un servicio en segundo plano (daemon) y aplicación de escritorio nativa para macOS, diseñada para monitorizar repositorios Git locales y automatizar el ciclo de vida del control de versiones (`git add`, `git commit`, `git push`) según políticas operativas configurables (`AUTO`, `COMMIT_ONLY`, `PAUSED`).

Diseñado específicamente para el ecosistema macOS, se integra directamente con LaunchAgents, Keychain de macOS (`/usr/bin/security`), notificaciones nativas del sistema y gestión continua de procesos en segundo plano.

---

## Características Principales

- **Interfaz Nativa para macOS**: Panel de control con diseño oscuro (Dark Mode) de dos columnas para administrar múltiples repositorios con indicadores de estado en tiempo real, metadatos de ramas y controles operativos.
- **Ejecución Continua en Segundo Plano**: Cerrar la ventana principal oculta la interfaz y mantiene el motor y los vigilantes de archivos activos en segundo plano. El apagado total se controla explícitamente desde el menú de la aplicación.
- **Motor de Debounce Inteligente**: Agrupa modificaciones continuas dentro de una ventana de inactividad configurable (por defecto: 5 minutos) antes de ejecutar las operaciones de staging y commit, evitando commits fragmentados.
- **Seguridad Multinivel**: Los tokens de acceso personal (PAT) y credenciales de GitHub se almacenan de forma segura en el Keychain de macOS y en un archivo local restringido (`0600`), completamente aislados del control de versiones.
- **Configuración Remota Inteligente**: Configura rutas de carpetas locales y URLs remotas de GitHub directamente desde la interfaz, con inicialización automática (`git init`) y vinculación de rama upstream (`-u`).
- **Inicio Automático con macOS (LaunchAgents)**: Configuración en un clic para iniciar de forma silenciosa al iniciar sesión en macOS sin requerir privilegios de administrador (`sudo`).
- **Operaciones No Destructivas**: Nunca ejecuta comandos destructivos (`--force`, `reset --hard`). Al eliminar un proyecto del bot, todos los archivos locales y el historial de `.git` se conservan 100% intactos.

---

## Requisitos del Sistema

- **Sistema Operativo**: macOS 12.0 (Monterey), macOS 13 (Ventura), macOS 14 (Sonoma), macOS 15 (Sequoia) o superior.
- **Python**: Python 3.10 o superior con soporte para `tkinter`.
- **Git**: Apple Git o Homebrew Git (v2.28+ recomendado).

---

## Instalación y Configuración

### 1. Clonar el Repositorio
```bash
git clone https://github.com/MateoHdzC/GH-BOT-REPOS-MAC.git
cd GH-BOT-REPOS-MAC
```

### 2. Instalar Dependencias
```bash
pip3 install -r requirements.txt
```

### 3. Compilar la Aplicación Nativa para macOS
Para generar el paquete ejecutable `.app` independiente para macOS:
```bash
python3 scripts/build_app.py
```
Esto genera `dist/GH-BOT-REPOS-MAC.app`. Podés moverlo a tu carpeta `/Applications` o abrirlo directamente:
```bash
open dist/GH-BOT-REPOS-MAC.app
```

---

## Guía de Uso y Operación

### 1. Conectar GitHub
1. Entrá en **Configuración** en la barra lateral o hacé clic en **Conectar GitHub** en la barra superior.
2. Ingresá tu **Usuario de GitHub** y tu **Token de Acceso Personal (PAT)**.
   - *Recomendado*: Token clásico de GitHub con alcance `repo`, o Token Fine-Grained con permisos de `Contents: Read and write`.
3. Las credenciales se guardan de forma segura en el Keychain de macOS y quedan excluidas de cualquier commit vía `.gitignore`.

### 2. Añadir un Proyecto
1. Hacé clic en **+ Añadir proyecto** en la barra superior.
2. Completá los datos del proyecto:
   - **Carpeta local**: Hacé clic en *Examinar...* para seleccionar cualquier carpeta de tu Mac. Si la carpeta aún no es un repositorio Git, el sistema ofrece inicializarlo automáticamente (`git init`).
   - **Nombre del proyecto**: Se completa automáticamente con el nombre de la carpeta (personalizable).
   - **Link de GitHub (URL Remota)**: Ingresá la URL del repositorio remoto (ej. `https://github.com/usuario/repo.git`).
   - **Modo de sincronización**: Seleccioná `AUTO`, `COMMIT_ONLY` o `PAUSED`.
3. Hacé clic en **Guardar y Empezar a Vigilar**.

### 3. Modos de Operación
Cada repositorio registrado funciona de manera independiente en uno de tres modos:
- **`AUTO`**: Vigila eventos en el sistema de archivos. Cuando detecta cambios, espera la ventana de inactividad (5 minutos sin nuevos cambios), añade todos los archivos (`git add .`), genera un commit automático y lo sube a GitHub (`git push -u origin <rama>`).
- **`COMMIT_ONLY`**: Genera commits locales automáticamente al estabilizarse los cambios, pero nunca ejecuta `git push`.
- **`PAUSED`**: Detiene temporalmente la observación del sistema de archivos y los temporizadores para el repositorio seleccionado.

### 4. Sincronización Inmediata ("Subir ahora")
Hacé clic en **⚡ Subir ahora** en la tarjeta de cualquier proyecto para omitir los temporizadores de inactividad y forzar de inmediato el staging, commit y push hacia GitHub.

### 5. Ejecución en Segundo Plano
- Al hacer clic en el botón rojo de cerrar ventana **(X)**, la ventana se oculta pero la aplicación **sigue activa** en segundo plano vigilando y sincronizando tus cambios.
- Para volver a abrir la interfaz gráfica, ejecutá la aplicación desde Finder / Dock o mediante `open dist/GH-BOT-REPOS-MAC.app`.
- Para cerrar la aplicación de forma definitiva, hacé clic en **Salir de GH-BOT** en la parte inferior de la barra lateral.

### 6. Inicio Automático con macOS
Activá la casilla **Iniciar GH-BOT-REPOS-MAC al iniciar sesión en macOS** dentro de *Configuración*. El daemon crea un LaunchAgent a nivel de usuario en:
```text
~/Library/LaunchAgents/com.mateohdz.ghbotmac.plist
```

---

## Arquitectura de Directorios

```text
GH-BOT-REPOS-MAC/
├── .github/workflows/         # Flujos automatizados de CI/CD
├── config/
│   ├── .secrets.json          # Credenciales privadas locales (ignorado en git, 0600)
│   └── projects.json          # Registro local de proyectos (ignorado en git)
├── dist/
│   └── GH-BOT-REPOS-MAC.app   # Bundle nativo independiente para macOS
├── docs/                      # Documentación técnica
├── logs/
│   └── app.log                # Registro de eventos y logs estructurados
├── scripts/
│   ├── build_app.py           # Compilador del bundle de macOS
│   └── run_tests.py           # Ejecutor de la suite de pruebas
├── src/
│   ├── config/                # Modelos de datos y gestor de configuración
│   ├── core/                  # Orquestador del motor y estado en segundo plano
│   ├── git/                   # Gestor de subprocesos de Git y autenticación
│   ├── ui/                    # Interfaz gráfica en Dark Mode y cuadros de diálogo
│   ├── utils/                 # Keychain de macOS, LaunchAgents y notificaciones
│   └── watcher/               # Observador de archivos y temporizadores de debounce
├── tests/                     # Suite completa de pruebas automatizadas (33 tests)
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

---

## Pruebas y Validación de Calidad

El proyecto incluye una suite de pruebas automatizadas que cubren serialización de configuración, clasificación de errores de Git, temporizadores de debounce, seguridad en concurrencia y controladores de interfaz gráfica:

```bash
python3 scripts/run_tests.py
```

Resultado esperado:
```text
Ran 33 tests in ~10s
OK
```

---

## Licencia

Este proyecto está bajo la Licencia MIT. Consultá [LICENSE](LICENSE) para más información.
