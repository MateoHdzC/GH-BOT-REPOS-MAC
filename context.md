# GH-BOT-REPOS-MAC: Technical Context & System Architecture

## 1. Executive Summary

`GH-BOT-REPOS-MAC` is a specialized background daemon and desktop application engineered for macOS (12.0 Monterey through macOS Sequoia/Sonoma). Its primary objective is to monitor local Git workspace folders and automate the version control lifecycle (`git add`, `git commit`, `git push`) according to configurable operational modes and inactivity debounce intervals.

The system is built entirely on Python with Tkinter for its Dark Mode graphical interface, Apple FSEvents / Watchdog for file system observation, the macOS Keychain (`/usr/bin/security`) for encrypted credential persistence, and macOS LaunchAgents for silent autostart on user login.

---

## 2. High-Level Architecture

```text
+-------------------------------------------------------------------------------+
|                             macOS Desktop Layer                               |
|  - MainWindow (Tkinter)  - SidebarNav  - ProjectCard  - Modals & Settings     |
+-------------------------------------------------------------------------------+
                                      |
                                      v
+-------------------------------------------------------------------------------+
|                            Core Engine Orchestrator                           |
|  - BotEngine: Thread-safe coordinator & state manager                         |
|  - ProjectManager: CRUD, directory validation, Git repository discovery       |
|  - GitHubAuthService: Token retrieval & Keychain synchronization              |
+-------------------------------------------------------------------------------+
           |                                                |
           v                                                v
+-----------------------------+        +----------------------------------------+
|    Watcher & Debounce Layer |        |         Git Subprocess Layer           |
|  - WatcherManager           |        |  - GitManager: Safe CLI subprocesses   |
|  - RepoWatcher              |        |  - Large Buffer Handlers (500MB post)  |
|  - DebounceTimer            |        |  - Safe Authentication Injection       |
|  - FileFilter Rules         |        |  - Non-destructive Error Classification|
+-----------------------------+        +----------------------------------------+
           |                                                |
           +-----------------------+------------------------+
                                   |
                                   v
+-------------------------------------------------------------------------------+
|                            Storage & OS Services                              |
|  - config/projects.json: Watched projects configuration                       |
|  - macOS Keychain / config/.secrets.json (0600): Private PAT storage          |
|  - ~/Library/LaunchAgents/com.mateohdz.ghbotmac.plist: Background Daemon      |
|  - osascript: Native macOS notification center alerts                         |
+-------------------------------------------------------------------------------+
```

---

## 3. Directory & File Inventory

```text
GH-BOT-REPOS-MAC/
├── assets/
│   ├── AppIcon.icns              # macOS application icon bundle (16x16 to 1024x1024 Retina)
│   ├── logo_36.png               # Sidebar header logo (36x36)
│   ├── logo_48.png               # Dialog badge logo (48x48)
│   ├── logo_64.png               # Window/Dock icon (64x64)
│   └── logo_128.png              # High-resolution asset (128x128)
├── config/
│   ├── .secrets.json             # Local private credentials fallback (chmod 0600, gitignored)
│   └── projects.json             # Registered repository configs (gitignored)
├── dist/
│   └── GH-BOT-REPOS-MAC.app      # Standalone native macOS application bundle
├── logs/
│   └── app.log                   # Operational event log with rotation
├── scripts/
│   ├── build_app.py              # macOS bundle generator (creates .app structure & Info.plist)
│   └── run_tests.py              # Automated test suite discovery and runner
├── src/
│   ├── config/
│   │   ├── manager.py            # JSON serialization, schema validation, persistence
│   │   └── models.py             # Dataclasses: ProjectConfig, AppConfig, ProjectMode
│   ├── core/
│   │   ├── engine.py             # Central BotEngine orchestrator and pipeline execution
│   │   ├── github_service.py     # GitHub authentication status and token bridge
│   │   ├── project_manager.py    # Non-UI project lifecycle, validation, and CRUD operations
│   │   └── state.py              # ProjectRuntimeState, SystemStatus, SyncStatus enums
│   ├── git/
│   │   ├── git_manager.py        # Subprocess manager for status, stage, commit, and push
│   │   ├── models.py             # GitCommandResult, CommitInfo, GitErrorType enums
│   │   └── secret_scanner.py     # Pre-commit pattern scanner for credentials & private keys
│   ├── ui/
│   │   ├── app.py                # Main desktop application bootstrap and signal handlers
│   │   ├── components.py         # ProjectCard, LogsView, SettingsView, Modals
│   │   ├── main_window.py        # Two-column Dark Mode dashboard & navigation frame
│   │   ├── sidebar.py            # Navigation category filters, counters, branding & logo
│   │   └── styles.py             # Design system palette (Pure Black & Strong Royal Blue)
│   ├── utils/
│   │   ├── autostart.py          # LaunchAgents manager for login autostart
│   │   ├── constants.py          # System defaults, ignored files, and directory patterns
│   │   ├── keychain.py           # macOS Keychain (/usr/bin/security) & 0600 fallback
│   │   ├── logger.py             # Rotating file and console structured logging
│   │   ├── notifications.py      # Native macOS Notification Center integration
│   │   ├── process_lock.py       # Single-instance process lock using Unix fcntl.flock
│   │   ├── network.py            # Network reachability monitor and offline event queue
│   │   └── time_utils.py         # Human-readable debounce duration parser & formatter
│   └── watcher/
│       ├── debounce_timer.py     # Thread-safe resettable countdown timer
│       ├── file_filter.py        # VCS, lockfile, cache, and system file ignore rules
│       └── repo_watcher.py       # Watchdog / Polling file system directory observer
├── tests/                        # 59 automated unit & integration tests (100% passing)
│   ├── config/
│   ├── core/
│   ├── git/
│   ├── ui/
│   ├── utils/
│   └── watcher/
├── .gitignore                    # Exclusion rules protecting secrets, logs, and build artifacts
├── GHBOT.png                     # Master application source icon
├── LICENSE                       # MIT License
└── requirements.txt              # Minimal runtime dependencies (watchdog, pytest)
```

---

## 4. Core Subsystems

### 4.1. File System Watcher & Debounce Engine
- **Observer (`repo_watcher.py`)**: Uses `watchdog.observers.Observer` (native macOS FSEvents) with a clean fallback to `PollingRepoObserver` if watchdog is unavailable.
- **Ignore Filter (`file_filter.py`)**: Ignores `.git`, `.DS_Store`, `.venv`, `node_modules`, temporary files, build directories, and secrets.
- **Debounce Timer (`debounce_timer.py`)**: Resettable countdown timer (`threading.Timer`). When modifications occur rapidly (e.g. saving multiple files or build steps), the timer resets on every event. The Git pipeline only executes when a full quiet period has elapsed without any new modifications.
- **Configurable Intervals (`time_utils.py`)**: Supports presets (`1m`, `4m`, `5m`, `10m`, `15m`, `30m`, `1h`, `2h`, `3h`, `4h`, `8h`, `24h`) or custom formatted inputs (`10m`, `1h`, `45s`, etc.). Users can update wait times on the fly per repository or globally.

### 4.2. Safe Git Execution Engine (`git_manager.py`)
- **Non-Destructive Guarantee**: Prohibits `--force`, `--hard reset`, or destructive commands.
- **Buffer Overflow Prevention**: Injects `-c http.postBuffer=524288000` (500 MB) and `-c http.maxRequestBuffer=524288000` into `git push` to prevent HTTP 400 RPC packet disconnects when pushing repositories with images or binary assets.
- **Authentication**: Seamlessly injects GitHub Personal Access Tokens via base64 `http.extraHeader=Authorization: Basic ...` headers during push commands without storing plaintext credentials in the git remote URL or command line history.
- **Repository Bootstrapping**: Offers one-click `git init` and remote upstream tracking (`-u origin <branch>`) when adding non-initialized directories.

### 4.3. Multi-Tiered Security & Keychain (`keychain.py`)
- **Tier 1 (macOS Keychain)**: Stores tokens securely via `/usr/bin/security` in the user's macOS login keychain.
- **Tier 2 (Restricted File Fallback)**: If Keychain is inaccessible or running in sandboxed environments, credentials are stored in `config/.secrets.json` enforced with restricted `0600` permissions (read/write only by owner).
- **Leak Prevention**: `.gitignore` strictly ignores `config/.secrets.json`, `.secrets.*`, `credentials.*`, and `.env*`.

### 4.4. macOS Background Execution & Lifecycle
- **Window Close Interception (`main_window.py`)**: When the user clicks the red close button (**X**), the window triggers `hide_to_background()`. It minimizes via `self.withdraw()` while keeping all background watcher threads and Git pipelines fully operational.
- **System Notification (`notifications.py`)**: Dispatches a desktop notification informing the user that the bot remains active in the background.
- **Application Termination**: Controlled explicitly via the "Salir de GH-BOT" action in the sidebar.
- **Autostart on Login (`autostart.py`)**: Installs a user-level LaunchAgent at `~/Library/LaunchAgents/com.mateohdz.ghbotmac.plist` running `--background`.

### 4.5. User Interface & Dark Theme Design System (`styles.py`)
- **Layout**: Two-column layout with a fixed-width left navigation sidebar and a dynamic scrollable content pane.
- **Color Palette**:
  - `BG_WINDOW = "#07080C"` (Canvas Black)
  - `BG_SIDEBAR = "#040508"` (Sidebar Black)
  - `BG_HEADER = "#0A0C14"` (Header Midnight Black)
  - `BG_CARD = "#0C0F18"` (Surface Obsidian Card)
  - `BG_INPUT = "#040508"` (Input Black)
  - `COLOR_ACCENT = "#0055FF"` (Electric Royal Blue)
  - `COLOR_BORDER = "#172033"` (Slate Blue Border)
  - `FG_PRIMARY = "#FFFFFF"` / `FG_SECONDARY = "#94A3B8"`
- **Responsive Controls**: Quick operational mode switcher (`AUTO`, `COMMIT_ONLY`, `PAUSED`), instant debounce duration dropdown, "⚡ Subir ahora" manual trigger, and delete confirmation dialogs.

---

## 5. Operational Modes Reference

| Mode | Observation | Staging (`git add`) | Committing (`git commit`) | Pushing (`git push`) | Inactivity Timer |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **`AUTO`** | Active | Automatic | Automatic | Automatic | Active (Configurable: 1m - 24h) |
| **`COMMIT_ONLY`** | Active | Automatic | Automatic | Never (Skipped) | Active (Configurable: 1m - 24h) |
| **`PAUSED`** | Halts events | Disabled | Disabled | Disabled | Cancelled / Inactive |
| **⚡ Subir ahora** | N/A | Immediate | Immediate | Immediate | Bypasses Inactivity Timer |

---

## 6. Testing & Quality Standards

The test suite consists of **43 automated unit and integration tests** located under `tests/`:
- `tests/config/`: Configuration loading, corruption handling, schema validation.
- `tests/core/`: `BotEngine` lifecycle, project manager CRUD, multi-mode transitions, thread safety.
- `tests/git/`: Git status parser, commit detection, push error classification, remote configuration.
- `tests/ui/`: View controller state updates, filter metrics, debounce handlers.
- `tests/utils/`: Time duration parser/formatter, LaunchAgent installer, notifications.
- `tests/watcher/`: Debounce timer reset on rapid triggers, ignore rules, FSEvents dispatches.

To run the complete test suite:
```bash
python3 scripts/run_tests.py
```
Expected output:
```text
Ran 43 tests in ~10s
OK
```

To compile the standalone macOS application bundle:
```bash
python3 scripts/build_app.py
```
