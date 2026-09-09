# GH-BOT-REPOS-MAC 🍏

> **Status**: Versión Final Completa (Fase 1, Fase 2 y Fase 3 Implementadas y Validadas)

`GH-BOT-REPOS-MAC` es una aplicación de escritorio nativa para macOS que vigila repositorios Git locales y automatiza el flujo de sincronización (`git add`, `git commit`, `git push`) según las políticas y modos establecidos (`AUTO`, `COMMIT_ONLY`, `PAUSED`).

Diseñada específicamente para el ecosistema de macOS con ejecución en segundo plano, integración segura con macOS Keychain, auto-inicio oficial mediante LaunchAgents, notificaciones de sistema y empaquetado como aplicación `.app`.

---

## ✨ Características Principales

1. **Interfaz Gráfica macOS**:
   - Tarjetas interactivas por proyecto con indicador de estado (🟢 AUTO / 🟡 COMMIT ONLY / ⏸️ PAUSED).
   - Selector de carpetas nativo para añadir repositorios locales.
   - Sincronización manual bajo demanda (botón *"Subir ahora"*).
   - Eliminación segura que desvincula el proyecto sin tocar archivos locales.
   - Visor integrado de logs de actividad.
2. **Ejecución en Segundo Plano Continua**:
   - Al cerrar la ventana principal, el bot continúa vigilando y sincronizando en segundo plano.
   - Botón explícito para salir limpiamente de la aplicación y detener todos los procesos.
3. **Inicio Automático con macOS (LaunchAgents)**:
   - Configuración con un clic (`☑ Iniciar GH-BOT-REPOS-MAC al iniciar sesión`).
   - Mecanismo oficial de macOS sin necesidad de privilegios `sudo`.
   - Inicia silenciosamente en segundo plano sin desplegar ventanas molestas.
4. **Seguridad y macOS Keychain**:
   - Conexión segura con GitHub sin guardar tokens en texto plano ni en `projects.json`.
   - Almacenamiento protegido mediante el subsistema de seguridad nativo de macOS (`/usr/bin/security`).
5. **Notificaciones Nativas Inteligentes**:
   - Alertas del sistema solo para eventos importantes (push exitoso, errores de push o fallos de autenticación), evitando el spam.
6. **Clasificación Avanzada de Errores Git**:
   - Tipificación de fallos (`NO_REMOTE`, `AUTH_FAILED`, `NETWORK_ERROR`, `REJECTED_NON_FAST_FORWARD`, etc.) sin recurrir jamás a comandos destructivos ni forzados (`--force`).

---

## 📁 Arquitectura Completa del Proyecto

```text
GH-BOT-REPOS-MAC/
├── config/
│   ├── .gitkeep
│   └── projects.json          # Configuración persistente de proyectos
├── dist/
│   └── GH-BOT-REPOS-MAC.app   # Aplicación nativa empaquetada para macOS
├── docs/                      # Documentación técnica
├── logs/
│   ├── .gitkeep
│   └── app.log                # Registro estructurado de logs
├── scripts/
│   ├── build_app.py           # Generador de GH-BOT-REPOS-MAC.app
│   ├── .gitkeep
│   └── run_tests.py           # Ejecutor de la suite de pruebas
├── src/
│   ├── config/                # Capa de configuración y modelos
│   │   ├── __init__.py
│   │   ├── manager.py
│   │   └── models.py
│   ├── core/                  # Orquestador central, estados y GitHub service
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── github_service.py
│   │   ├── main.py
│   │   ├── project_manager.py
│   │   └── state.py
│   ├── git/                   # Abstracción y operaciones Git CLI seguras
│   │   ├── __init__.py
│   │   ├── git_manager.py
│   │   └── models.py
│   ├── ui/                    # Capa de presentación macOS
│   │   ├── __init__.py
│   │   ├── app.py             # Lanzador de la aplicación de escritorio
│   │   ├── components.py      # Tarjetas de proyectos y diálogos modales
│   │   ├── main_window.py     # Ventana principal
│   │   └── styles.py          # Paleta visual HIG macOS
│   └── utils/                 # Utilidades del sistema operativo
│       ├── __init__.py
│       ├── autostart.py       # Gestor LaunchAgents de macOS
│       ├── constants.py
│       ├── keychain.py        # Almacenamiento seguro en Keychain
│       ├── logger.py          # Logging rotativo estructurado
│       └── notifications.py   # Notificaciones de escritorio AppleScript
├── tests/                     # Suite completa (29 tests automatizados)
│   ├── config/
│   ├── core/
│   ├── git/
│   ├── ui/
│   ├── utils/
│   └── watcher/
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

---

## 🚀 Guía de Uso y Ejecución

### 1. Ejecutar en Desarrollo
Para abrir la interfaz gráfica de inmediato:

```bash
# Modo normal
python3 -m src.ui.app

# Modo con logs detallados
python3 -m src.ui.app --debug

# Modo segundo plano (como arranca al iniciar sesión)
python3 -m src.ui.app --background
```

### 2. Generar y Ejecutar `GH-BOT-REPOS-MAC.app`
Para compilar la aplicación nativa para macOS:

```bash
# 1. Compilar el bundle .app
python3 scripts/build_app.py

# 2. Abrir la aplicación empaquetada
open dist/GH-BOT-REPOS-MAC.app
```
*(También podés arrastrar `dist/GH-BOT-REPOS-MAC.app` a tu carpeta `/Applications` de macOS).*

---

## 🛠️ Operación de la Aplicación

### Conectar Cuenta de GitHub
1. En la ventana principal, hacé clic en **"Conectar GitHub"**.
2. Ingresá tu nombre de usuario y opcionalmente tu Personal Access Token.
3. El token se almacenará de forma cifrada en tu **macOS Keychain** personal.

### Añadir un Proyecto
1. Hacé clic en **"+ Añadir proyecto"**.
2. Se abrirá el selector de carpetas nativo de macOS. Seleccioná el directorio de tu repositorio Git local.
3. El bot validará que sea un repositorio Git válido y lo incorporará a la vigilancia activa.

### Cambiar Modos de Sincronización
En la tarjeta de cada proyecto, seleccioná el modo deseado:
- **`AUTO`**: Commit automático + Push tras 5 minutos de inactividad.
- **`COMMIT_ONLY`**: Solo commit automático (sin push).
- **`PAUSED`**: Pausa el monitoreo de ese repositorio.

### Sincronización Inmediata ("Subir ahora")
Hacé clic en **"Subir ahora"** en la tarjeta del proyecto para disparar el flujo de staging, commit y push al instante sin esperar el temporizador de inactividad.

### Eliminar Proyecto
Hacé clic en **"Eliminar"**. Aparecerá una confirmación. Al aceptar, el proyecto se desvincula del bot, pero **todos tus archivos y repositorios locales se mantienen 100% intactos**.

### Activar Inicio Automático
Marcá la casilla **"Iniciar al iniciar sesión"** en la barra superior. El bot configurará el agente oficial en `~/Library/LaunchAgents/` para arrancar silenciosamente en segundo plano cada vez que inicies sesión en tu Mac.

---

## 🧪 Pruebas Automatizadas

Para correr toda la suite de pruebas (29 tests):

```bash
python3 scripts/run_tests.py
```
*(Resultado: `Ran 29 tests - OK`)*
