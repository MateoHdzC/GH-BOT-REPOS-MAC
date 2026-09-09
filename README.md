# GH-BOT-REPOS-MAC

> **macOS Git Automation Daemon & Workspace Management System**

`GH-BOT-REPOS-MAC` is a native macOS background daemon and desktop application designed to monitor local Git repositories and automate the version control lifecycle (`git add`, `git commit`, `git push`) based on configurable operational policies (`AUTO`, `COMMIT_ONLY`, `PAUSED`).

Engineered specifically for the macOS ecosystem, it integrates directly with macOS LaunchAgents, macOS Keychain, native desktop notifications, and continuous background process management.

---

## Key Features

- **Native macOS Interface**: Two-column Dark Mode dashboard for managing multiple repositories with real-time health indicators, branch metadata, and operational controls.
- **Continuous Background Execution**: Closing the main window keeps the daemon and file watchers actively running in the background. Full termination is controlled explicitly via the application menu.
- **Intelligent Debounce Engine**: Batches consecutive file modifications within a configurable inactivity window (default: 5 minutes) before triggering staging and commit operations, preventing fragmented commits.
- **Multi-Tiered Security**: Personal Access Tokens (PAT) and GitHub credentials are stored securely via the macOS Keychain (`/usr/bin/security`) and local restricted secrets (`0600`), isolated completely from version control.
- **Smart Remote Configuration**: Configure local directory paths and target GitHub remote URLs directly from the UI, with automatic `git init` initialization and upstream tracking (`-u`).
- **macOS LaunchAgents Autostart**: One-click configuration to launch silently in the background at macOS login without requiring administrator (`sudo`) privileges.
- **Non-Destructive Operations**: Never executes destructive commands (`--force`, `reset --hard`). Repository deletion from the bot leaves all local files and `.git` trees 100% intact.

---

## System Requirements

- **Operating System**: macOS 12.0 (Monterey), macOS 13 (Ventura), macOS 14 (Sonoma), macOS 15 (Sequoia), or later.
- **Python**: Python 3.10 or higher with `tkinter` support.
- **Git**: Apple Git or Homebrew Git (v2.28+ recommended).

---

## Installation & Setup

### 1. Clone the Repository
```bash
git clone https://github.com/MateoHdzC/GH-BOT-REPOS-MAC.git
cd GH-BOT-REPOS-MAC
```

### 2. Install Dependencies
```bash
pip3 install -r requirements.txt
```

### 3. Build Native macOS Application
To compile the standalone macOS application bundle:
```bash
python3 scripts/build_app.py
```
This generates `dist/GH-BOT-REPOS-MAC.app`. You can move it to `/Applications` or launch it directly:
```bash
open dist/GH-BOT-REPOS-MAC.app
```

---

## Usage & Operational Guide

### 1. Connecting GitHub
1. Navigate to **Configuración** in the sidebar or click **Conectar GitHub** in the top navigation bar.
2. Enter your GitHub **Username** and **Personal Access Token (PAT)**.
   - *Recommended*: GitHub Token (Classic) with `repo` scope, or Fine-Grained Token with `Contents: Read and write` permission.
3. Credentials are saved locally into the macOS Keychain and ignored by `.gitignore`.

### 2. Adding a Project
1. Click **+ Añadir proyecto** in the top bar.
2. Fill out the project details:
   - **Carpeta local**: Click *Examinar...* to select any local folder. If the folder is not yet a Git repository, the system offers automatic initialization (`git init`).
   - **Nombre del proyecto**: Pre-filled with the directory name (customizable).
   - **Link de GitHub (URL Remota)**: Enter your remote repository URL (e.g. `https://github.com/username/repo.git`).
   - **Modo de sincronización**: Select `AUTO`, `COMMIT_ONLY`, or `PAUSED`.
3. Click **Guardar y Empezar a Vigilar**.

### 3. Operational Modes
Each registered repository operates independently in one of three modes:
- **`AUTO`**: Watches file system events. When changes occur, waits for the debounce window (5 minutes without edits), stages all modifications (`git add .`), creates an automated commit, and pushes to GitHub (`git push -u origin <branch>`).
- **`COMMIT_ONLY`**: Automatically creates local commits after changes settle, but never executes `git push`.
- **`PAUSED`**: Temporarily halts file system observation and timers for the selected repository.

### 4. Immediate Synchronization ("Subir ahora")
Click **⚡ Subir ahora** on any project card to bypass debounce timers and trigger an immediate staging, commit, and push sequence.

### 5. Background Execution
- Clicking the **(X)** red close button hides the window to the background while keeping all watchers and background sync pipelines active.
- To reopen the interface, launch the app from Finder / Dock or run `open dist/GH-BOT-REPOS-MAC.app`.
- To completely terminate the application, click **Salir de GH-BOT** at the bottom of the sidebar.

### 6. Auto-Start on macOS Login
Enable the **Iniciar GH-BOT-REPOS-MAC al iniciar sesión en macOS** checkbox in *Configuración*. The daemon creates a user-level LaunchAgent at:
```text
~/Library/LaunchAgents/com.mateohdz.ghbotmac.plist
```

---

## Directory Architecture

```text
GH-BOT-REPOS-MAC/
├── .github/workflows/         # CI/CD test automation workflows
├── config/
│   ├── .secrets.json          # Private user credentials (git-ignored, 0600)
│   └── projects.json          # Local project registry (git-ignored)
├── dist/
│   └── GH-BOT-REPOS-MAC.app   # Standalone native macOS application bundle
├── docs/                      # Technical documentation
├── logs/
│   └── app.log                # Structured operational logs
├── scripts/
│   ├── build_app.py           # macOS application bundle builder
│   └── run_tests.py           # Automated test suite runner
├── src/
│   ├── config/                # Configuration management & data models
│   ├── core/                  # Orchestrator engine & background state
│   ├── git/                   # Git CLI subprocess manager & auth handlers
│   ├── ui/                    # Dark Mode graphical interface & modals
│   ├── utils/                 # macOS Keychain, LaunchAgents & notifications
│   └── watcher/               # File system observer & debounce timers
├── tests/                     # Comprehensive test suite (33 tests)
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

---

## Testing & Quality Assurance

The project includes an automated test suite covering configuration serialization, Git command classification, debounce timers, thread safety, and UI view controllers:

```bash
python3 scripts/run_tests.py
```

Expected result:
```text
Ran 33 tests in ~10s
OK
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
