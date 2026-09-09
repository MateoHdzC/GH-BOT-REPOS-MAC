"""Reusable Dark Mode UI components: ProjectCard, LogsView, SettingsView, and Modals."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Optional

from src.config.models import ProjectMode
from src.core.engine import BotEngine
from src.core.state import ProjectRuntimeState, SyncStatus
from src.ui.styles import (
    BG_BADGE_AUTO,
    BG_BADGE_COMMIT,
    BG_BADGE_PAUSED,
    BG_BUTTON_SECONDARY,
    BG_CARD,
    BG_CARD_HOVER,
    BG_HEADER,
    BG_INPUT,
    BG_WINDOW,
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_DANGER,
    COLOR_SUCCESS,
    COLOR_WARNING,
    FG_MUTED,
    FG_PRIMARY,
    FG_SECONDARY,
    FG_WHITE,
    FONT_BADGE,
    FONT_BODY,
    FONT_BUTTON,
    FONT_CARD_PATH,
    FONT_CARD_TITLE,
    FONT_LOGS,
    FONT_SECTION_HEADER,
    FONT_SMALL,
    FONT_SUBTITLE,
    FONT_TITLE,
)
from src.utils.autostart import disable_autostart, enable_autostart, is_autostart_enabled
from src.utils.constants import DEFAULT_LOG_PATH


class ProjectCard(tk.Frame):
    """Modern dark mode card displaying a managed repository's status and actions."""

    def __init__(
        self,
        parent: tk.Widget,
        state: ProjectRuntimeState,
        on_mode_change: Callable[[str, ProjectMode], None],
        on_manual_sync: Callable[[str], None],
        on_delete: Callable[[str], None],
        **kwargs,
    ) -> None:
        super().__init__(
            parent,
            bg=BG_CARD,
            highlightbackground=COLOR_BORDER,
            highlightthickness=1,
            padx=16,
            pady=14,
            **kwargs,
        )
        self.state = state
        self.on_mode_change = on_mode_change
        self.on_manual_sync = on_manual_sync
        self.on_delete = on_delete

        self._build_ui()

    def _build_ui(self) -> None:
        # Header Row: Indicator + Name + Branch + Mode Badge
        header = tk.Frame(self, bg=BG_CARD)
        header.pack(fill=tk.X)

        dot = "🟢" if self.state.mode == ProjectMode.AUTO else ("🟡" if self.state.mode == ProjectMode.COMMIT_ONLY else "⚪")
        name_lbl = tk.Label(
            header,
            text=f"{dot}  {self.state.name}",
            font=FONT_CARD_TITLE,
            fg=FG_PRIMARY,
            bg=BG_CARD,
        )
        name_lbl.pack(side=tk.LEFT)

        if self.state.current_branch:
            branch_lbl = tk.Label(
                header,
                text=f" 🌿 {self.state.current_branch} ",
                font=FONT_BADGE,
                fg=FG_SECONDARY,
                bg=BG_BUTTON_SECONDARY,
                padx=4,
                pady=2,
            )
            branch_lbl.pack(side=tk.LEFT, padx=(10, 0))

        # Mode Badge
        badge_bg = (
            BG_BADGE_AUTO
            if self.state.mode == ProjectMode.AUTO
            else (BG_BADGE_COMMIT if self.state.mode == ProjectMode.COMMIT_ONLY else BG_BADGE_PAUSED)
        )
        badge_fg = (
            COLOR_SUCCESS
            if self.state.mode == ProjectMode.AUTO
            else (COLOR_WARNING if self.state.mode == ProjectMode.COMMIT_ONLY else FG_MUTED)
        )
        badge = tk.Label(
            header,
            text=f" {self.state.mode.value} ",
            font=FONT_BADGE,
            fg=badge_fg,
            bg=badge_bg,
            padx=6,
            pady=2,
        )
        badge.pack(side=tk.RIGHT)

        # Path Row
        path_str = self._format_path(self.state.path)
        path_lbl = tk.Label(
            self,
            text=path_str,
            font=FONT_CARD_PATH,
            fg=FG_MUTED,
            bg=BG_CARD,
            anchor="w",
        )
        path_lbl.pack(fill=tk.X, pady=(6, 4))

        # Live Metadata & Status Row
        status_text, status_color = self._get_status_info()
        meta_lbl = tk.Label(
            self,
            text=status_text,
            font=FONT_SMALL,
            fg=status_color,
            bg=BG_CARD,
            anchor="w",
        )
        meta_lbl.pack(fill=tk.X, pady=(0, 10))

        # Action Buttons Row
        actions = tk.Frame(self, bg=BG_CARD)
        actions.pack(fill=tk.X)

        # Mode Selector
        mode_var = tk.StringVar(value=self.state.mode.value)
        mode_cb = ttk.Combobox(
            actions,
            textvariable=mode_var,
            values=["AUTO", "COMMIT_ONLY", "PAUSED"],
            state="readonly",
            width=13,
        )
        mode_cb.pack(side=tk.LEFT, padx=(0, 10))
        mode_cb.bind(
            "<<ComboboxSelected>>",
            lambda e: self.on_mode_change(
                self.state.name, ProjectMode.from_string(mode_var.get())
            ),
        )

        # Subir Ahora Button
        sync_btn = tk.Button(
            actions,
            text="⚡ Subir ahora",
            font=FONT_SMALL,
            bg=COLOR_ACCENT,
            fg=FG_WHITE,
            activebackground=COLOR_BORDER,
            activeforeground=FG_WHITE,
            relief=tk.FLAT,
            padx=10,
            pady=3,
            cursor="pointinghand",
            command=lambda: self.on_manual_sync(self.state.name),
        )
        sync_btn.pack(side=tk.LEFT)

        # Delete Button
        del_btn = tk.Button(
            actions,
            text="Eliminar",
            font=FONT_SMALL,
            fg=COLOR_DANGER,
            bg=BG_CARD,
            activebackground=BG_BUTTON_SECONDARY,
            activeforeground=COLOR_DANGER,
            relief=tk.FLAT,
            padx=8,
            pady=3,
            cursor="pointinghand",
            command=self._confirm_delete,
        )
        del_btn.pack(side=tk.RIGHT)

    def _format_path(self, raw_path: str) -> str:
        try:
            home = str(Path.home())
            if raw_path.startswith(home):
                return "~" + raw_path[len(home):]
            return raw_path
        except Exception:
            return raw_path

    def _get_status_info(self) -> tuple[str, str]:
        parts = []
        if self.state.last_commit_hash:
            short_hash = self.state.last_commit_hash[:7]
            msg = f"Commit: {short_hash}"
            if self.state.last_commit_message:
                msg += f" ({self.state.last_commit_message})"
            parts.append(msg)
        else:
            parts.append("Sin commits recientes")

        if self.state.last_sync_status == SyncStatus.ERROR or self.state.last_error:
            parts.append(f"🔴 {self.state.last_error or 'Error en sync'}")
            return "  •  ".join(parts), COLOR_DANGER

        if self.state.last_sync_status == SyncStatus.SUCCESS:
            parts.append("🟢 Sincronizado")
            return "  •  ".join(parts), FG_SECONDARY

        if self.state.last_sync_status == SyncStatus.NO_CHANGES:
            parts.append("⚪ Sin cambios pendientes")
            return "  •  ".join(parts), FG_MUTED

        if self.state.last_sync_status == SyncStatus.SKIPPED_PAUSED:
            parts.append("⏸️ En pausa")
            return "  •  ".join(parts), FG_MUTED

        return "  •  ".join(parts), FG_MUTED

    def _confirm_delete(self) -> None:
        confirmed = messagebox.askyesno(
            title="Confirmar eliminación",
            message=f"¿Deseas desvincular el proyecto '{self.state.name}' de GH-BOT-REPOS-MAC?\n\n(Tus archivos y repositorios locales se mantendrán 100% intactos).",
            parent=self,
        )
        if confirmed:
            self.on_delete(self.state.name)


class LogsView(tk.Frame):
    """Full-featured dark activity and log inspection console."""

    def __init__(self, parent: tk.Widget, **kwargs) -> None:
        super().__init__(parent, bg=BG_WINDOW, padx=20, pady=20, **kwargs)
        self._build_ui()
        self.refresh_logs()

    def _build_ui(self) -> None:
        # Header toolbar
        top = tk.Frame(self, bg=BG_WINDOW)
        top.pack(fill=tk.X, pady=(0, 14))

        title = tk.Label(
            top,
            text="Registro de Actividad",
            font=FONT_TITLE,
            fg=FG_PRIMARY,
            bg=BG_WINDOW,
        )
        title.pack(side=tk.LEFT)

        refresh_btn = tk.Button(
            top,
            text="🔄 Actualizar",
            font=FONT_SMALL,
            bg=BG_BUTTON_SECONDARY,
            fg=FG_PRIMARY,
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="pointinghand",
            command=self.refresh_logs,
        )
        refresh_btn.pack(side=tk.RIGHT)

        # Log container
        log_frame = tk.Frame(self, bg=BG_CARD, highlightbackground=COLOR_BORDER, highlightthickness=1)
        log_frame.pack(fill=tk.BOTH, expand=True)

        self.text = tk.Text(
            log_frame,
            font=FONT_LOGS,
            bg=BG_CARD,
            fg=FG_PRIMARY,
            insertbackground=FG_WHITE,
            relief=tk.FLAT,
            padx=14,
            pady=14,
            wrap=tk.WORD,
        )
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scrollbar.set)

        self.text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def refresh_logs(self) -> None:
        self.text.configure(state=tk.NORMAL)
        self.text.delete("1.0", tk.END)

        if DEFAULT_LOG_PATH.exists():
            try:
                lines = DEFAULT_LOG_PATH.read_text(encoding="utf-8").splitlines()
                recent = lines[-150:]  # Last 150 entries
                self.text.insert(tk.END, "\n".join(recent))
                self.text.see(tk.END)
            except Exception as err:
                self.text.insert(tk.END, f"Error al leer logs: {err}")
        else:
            self.text.insert(tk.END, "No se han generado logs todavía.")

        self.text.configure(state=tk.DISABLED)


class SettingsView(tk.Frame):
    """System settings and account configuration panel."""

    def __init__(
        self,
        parent: tk.Widget,
        engine: BotEngine,
        on_refresh: Callable[[], None],
        **kwargs,
    ) -> None:
        super().__init__(parent, bg=BG_WINDOW, padx=24, pady=20, **kwargs)
        self.engine = engine
        self.on_refresh = on_refresh
        self._build_ui()

    def _build_ui(self) -> None:
        title = tk.Label(
            self,
            text="Configuración del Sistema",
            font=FONT_TITLE,
            fg=FG_PRIMARY,
            bg=BG_WINDOW,
        )
        title.pack(anchor="w", pady=(0, 20))

        # Section 1: Inicio Automático macOS
        card1 = tk.Frame(self, bg=BG_CARD, highlightbackground=COLOR_BORDER, highlightthickness=1, padx=16, pady=16)
        card1.pack(fill=tk.X, pady=(0, 14))

        tk.Label(
            card1,
            text="Inicio Automático en macOS",
            font=FONT_CARD_TITLE,
            fg=FG_PRIMARY,
            bg=BG_CARD,
        ).pack(anchor="w")

        tk.Label(
            card1,
            text="Inicia el bot silenciosamente en segundo plano al iniciar sesión mediante LaunchAgents.",
            font=FONT_SUBTITLE,
            fg=FG_MUTED,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(2, 10))

        self.autostart_var = tk.BooleanVar(value=is_autostart_enabled())
        autostart_cb = tk.Checkbutton(
            card1,
            text="Iniciar GH-BOT-REPOS-MAC al iniciar sesión en macOS",
            variable=self.autostart_var,
            font=FONT_BODY,
            fg=FG_PRIMARY,
            bg=BG_CARD,
            activebackground=BG_CARD,
            activeforeground=FG_PRIMARY,
            selectcolor=BG_INPUT,
            command=self._toggle_autostart,
        )
        autostart_cb.pack(anchor="w")

        # Section 2: GitHub Account
        card2 = tk.Frame(self, bg=BG_CARD, highlightbackground=COLOR_BORDER, highlightthickness=1, padx=16, pady=16)
        card2.pack(fill=tk.X, pady=(0, 14))

        tk.Label(
            card2,
            text="Cuenta de GitHub",
            font=FONT_CARD_TITLE,
            fg=FG_PRIMARY,
            bg=BG_CARD,
        ).pack(anchor="w")

        gh_status = self.engine.get_github_status()
        status_text = (
            f"🟢 Conectado como @{gh_status.username} (Credenciales en macOS Keychain)"
            if gh_status.connected
            else "⚪ No conectado"
        )
        self.gh_label = tk.Label(
            card2,
            text=status_text,
            font=FONT_BODY,
            fg=COLOR_SUCCESS if gh_status.connected else FG_MUTED,
            bg=BG_CARD,
        )
        self.gh_label.pack(anchor="w", pady=(4, 12))

        gh_btn_text = "Desconectar GitHub" if gh_status.connected else "Conectar GitHub"
        gh_btn_bg = COLOR_DANGER if gh_status.connected else COLOR_ACCENT
        self.gh_btn = tk.Button(
            card2,
            text=gh_btn_text,
            font=FONT_BUTTON,
            bg=gh_btn_bg,
            fg=FG_WHITE,
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="pointinghand",
            command=self._handle_github_click,
        )
        self.gh_btn.pack(anchor="w")

        # Section 3: Environment Info
        card3 = tk.Frame(self, bg=BG_CARD, highlightbackground=COLOR_BORDER, highlightthickness=1, padx=16, pady=16)
        card3.pack(fill=tk.X)

        tk.Label(
            card3,
            text="Información del Entorno",
            font=FONT_CARD_TITLE,
            fg=FG_PRIMARY,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 6))

        info_text = f"Directorio de Trabajo: {Path.cwd()}\nArchivo de Configuración: {self.engine.config_manager.config_path}\nRegistro de Logs: {DEFAULT_LOG_PATH}"
        tk.Label(
            card3,
            text=info_text,
            font=FONT_CARD_PATH,
            fg=FG_MUTED,
            bg=BG_CARD,
            justify="left",
        ).pack(anchor="w")

    def _toggle_autostart(self) -> None:
        if self.autostart_var.get():
            if enable_autostart():
                messagebox.showinfo("Inicio Automático", "GH-BOT-REPOS-MAC se iniciará al arrancar macOS.", parent=self)
            else:
                self.autostart_var.set(False)
                messagebox.showerror("Error", "No se pudo habilitar el LaunchAgent.", parent=self)
        else:
            if disable_autostart():
                messagebox.showinfo("Inicio Automático", "Inicio automático desactivado.", parent=self)
            else:
                self.autostart_var.set(True)
                messagebox.showerror("Error", "No se pudo deshabilitar el LaunchAgent.", parent=self)

    def _handle_github_click(self) -> None:
        gh_status = self.engine.get_github_status()
        current_u = gh_status.username or self.engine.config.github_username
        if gh_status.connected:
            self.engine.disconnect_github()
            messagebox.showinfo("Desconectado", "Cuenta de GitHub desconectada.", parent=self)
        else:
            GitHubConnectDialog(
                parent=self,
                current_user=current_u,
                on_connect=self.engine.connect_github,
                on_disconnect=self.engine.disconnect_github,
            )
        self.on_refresh()


class GitHubConnectDialog(tk.Toplevel):
    """Modal dialog for securely connecting GitHub account via macOS Keychain."""

    def __init__(
        self,
        parent: tk.Widget,
        current_user: Optional[str],
        on_connect: Callable[[str, Optional[str]], bool],
        on_disconnect: Callable[[], bool],
    ) -> None:
        super().__init__(parent)
        self.title("Conectar GitHub")
        self.geometry("400x290")
        self.resizable(False, False)
        self.configure(bg=BG_CARD)
        self.transient(parent)
        self.grab_set()

        self.current_user = current_user
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect

        self._build_ui()

    def _build_ui(self) -> None:
        pad = tk.Frame(self, bg=BG_CARD, padx=22, pady=20)
        pad.pack(fill=tk.BOTH, expand=True)

        title = tk.Label(
            pad,
            text="Autenticación de GitHub",
            font=FONT_CARD_TITLE,
            fg=FG_PRIMARY,
            bg=BG_CARD,
        )
        title.pack(anchor="w", pady=(0, 4))

        subtitle = tk.Label(
            pad,
            text="Las credenciales se guardan de forma cifrada en macOS Keychain.",
            font=FONT_SMALL,
            fg=FG_MUTED,
            bg=BG_CARD,
        )
        subtitle.pack(anchor="w", pady=(0, 14))

        tk.Label(
            pad,
            text="Usuario de GitHub:",
            font=FONT_SMALL,
            fg=FG_SECONDARY,
            bg=BG_CARD,
        ).pack(anchor="w")

        user_entry = tk.Entry(
            pad,
            font=FONT_BODY,
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            insertbackground=FG_WHITE,
            relief=tk.SOLID,
            bd=1,
            highlightthickness=1,
            highlightbackground=COLOR_BORDER,
        )
        user_entry.pack(fill=tk.X, pady=(2, 10))

        tk.Label(
            pad,
            text="Personal Access Token (Opcional):",
            font=FONT_SMALL,
            fg=FG_SECONDARY,
            bg=BG_CARD,
        ).pack(anchor="w")

        token_entry = tk.Entry(
            pad,
            show="•",
            font=FONT_BODY,
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            insertbackground=FG_WHITE,
            relief=tk.SOLID,
            bd=1,
            highlightthickness=1,
            highlightbackground=COLOR_BORDER,
        )
        token_entry.pack(fill=tk.X, pady=(2, 16))

        if self.current_user:
            user_entry.insert(0, self.current_user)
            from src.utils.keychain import KeychainManager
            saved_token = KeychainManager.get_credential(self.current_user)
            if saved_token:
                token_entry.insert(0, saved_token)

        connect_btn = tk.Button(
            pad,
            text="Guardar y Conectar",
            font=FONT_BUTTON,
            bg=COLOR_ACCENT,
            fg=FG_WHITE,
            relief=tk.FLAT,
            pady=7,
            cursor="pointinghand",
            command=lambda: self._do_connect(user_entry.get(), token_entry.get()),
        )
        connect_btn.pack(fill=tk.X)

    def _do_connect(self, username: str, token: str) -> None:
        if not username.strip():
            messagebox.showwarning("Campo requerido", "Por favor ingresa tu usuario de GitHub.", parent=self)
            return
        if self.on_connect(username.strip(), token.strip() if token else None):
            messagebox.showinfo("Éxito", f"Cuenta @{username.strip()} conectada con éxito.", parent=self)
            self.destroy()


class AddProjectDialog(tk.Toplevel):
    """Modal dialog for adding and configuring a repository with folder and remote URL."""

    def __init__(
        self,
        parent: tk.Widget,
        engine: BotEngine,
        on_success: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self.title("Añadir Proyecto")
        self.geometry("490x510")
        self.resizable(False, False)
        self.configure(bg=BG_CARD)
        self.transient(parent)
        self.grab_set()

        self.engine = engine
        self.on_success = on_success

        self._build_ui()

    def _build_ui(self) -> None:
        pad = tk.Frame(self, bg=BG_CARD, padx=24, pady=20)
        pad.pack(fill=tk.BOTH, expand=True)

        # Header
        tk.Label(
            pad,
            text="Añadir Proyecto",
            font=FONT_TITLE,
            fg=FG_PRIMARY,
            bg=BG_CARD,
        ).pack(anchor="w")

        tk.Label(
            pad,
            text="Selecciona la carpeta local y el link de GitHub donde se subirá.",
            font=FONT_SMALL,
            fg=FG_MUTED,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(2, 14))

        # Field 1: Carpeta local
        tk.Label(
            pad,
            text="Carpeta local del proyecto:",
            font=FONT_SMALL,
            fg=FG_SECONDARY,
            bg=BG_CARD,
        ).pack(anchor="w")

        folder_row = tk.Frame(pad, bg=BG_CARD)
        folder_row.pack(fill=tk.X, pady=(2, 10))

        self.path_var = tk.StringVar()
        self.path_entry = tk.Entry(
            folder_row,
            textvariable=self.path_var,
            font=FONT_BODY,
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            insertbackground=FG_WHITE,
            relief=tk.SOLID,
            bd=1,
            highlightthickness=1,
            highlightbackground=COLOR_BORDER,
        )
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        browse_btn = tk.Button(
            folder_row,
            text="Examinar...",
            font=FONT_SMALL,
            bg=BG_BUTTON_SECONDARY,
            fg=FG_PRIMARY,
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="pointinghand",
            command=self._browse_directory,
        )
        browse_btn.pack(side=tk.RIGHT)

        # Field 2: Nombre del proyecto
        tk.Label(
            pad,
            text="Nombre del proyecto:",
            font=FONT_SMALL,
            fg=FG_SECONDARY,
            bg=BG_CARD,
        ).pack(anchor="w")

        self.name_var = tk.StringVar()
        self.name_entry = tk.Entry(
            pad,
            textvariable=self.name_var,
            font=FONT_BODY,
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            insertbackground=FG_WHITE,
            relief=tk.SOLID,
            bd=1,
            highlightthickness=1,
            highlightbackground=COLOR_BORDER,
        )
        self.name_entry.pack(fill=tk.X, pady=(2, 10))

        # Field 3: Link de GitHub (URL Remota)
        tk.Label(
            pad,
            text="Link del repositorio de GitHub (URL donde se subirá):",
            font=FONT_SMALL,
            fg=FG_SECONDARY,
            bg=BG_CARD,
        ).pack(anchor="w")

        self.remote_url_var = tk.StringVar()
        self.remote_url_entry = tk.Entry(
            pad,
            textvariable=self.remote_url_var,
            font=FONT_BODY,
            bg=BG_INPUT,
            fg=FG_PRIMARY,
            insertbackground=FG_WHITE,
            relief=tk.SOLID,
            bd=1,
            highlightthickness=1,
            highlightbackground=COLOR_BORDER,
        )
        self.remote_url_entry.pack(fill=tk.X, pady=(2, 4))

        tk.Label(
            pad,
            text="Ej: https://github.com/usuario/mi-repo.git (opcional)",
            font=FONT_SMALL,
            fg=FG_MUTED,
            bg=BG_CARD,
        ).pack(anchor="w", pady=(0, 10))

        # Field 4: Modo de sincronización
        tk.Label(
            pad,
            text="Modo de sincronización:",
            font=FONT_SMALL,
            fg=FG_SECONDARY,
            bg=BG_CARD,
        ).pack(anchor="w")

        self.mode_var = tk.StringVar(value="AUTO")
        mode_cb = ttk.Combobox(
            pad,
            textvariable=self.mode_var,
            values=["AUTO", "COMMIT_ONLY", "PAUSED"],
            state="readonly",
        )
        mode_cb.pack(fill=tk.X, pady=(2, 18))

        # Submit & Cancel Buttons
        btns = tk.Frame(pad, bg=BG_CARD)
        btns.pack(fill=tk.X)

        submit_btn = tk.Button(
            btns,
            text="Guardar y Empezar a Vigilar",
            font=FONT_BUTTON,
            bg=COLOR_ACCENT,
            fg=FG_WHITE,
            relief=tk.FLAT,
            pady=8,
            cursor="pointinghand",
            command=self._do_save,
        )
        submit_btn.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))

        cancel_btn = tk.Button(
            btns,
            text="Cancelar",
            font=FONT_BUTTON,
            bg=BG_BUTTON_SECONDARY,
            fg=FG_PRIMARY,
            relief=tk.FLAT,
            pady=8,
            cursor="pointinghand",
            command=self.destroy,
        )
        cancel_btn.pack(side=tk.RIGHT)

    def _browse_directory(self) -> None:
        chosen = filedialog.askdirectory(
            title="Seleccionar carpeta de proyecto",
            mustexist=True,
            parent=self,
        )
        if chosen:
            dir_path = Path(chosen).expanduser().resolve()
            self.path_var.set(str(dir_path))
            if not self.name_var.get().strip():
                self.name_var.set(dir_path.name)

            # If it's already a Git repo, check for remote origin URL
            if self.engine.git_manager.is_git_repo(dir_path):
                rem_url = self.engine.git_manager.get_remote_url(dir_path)
                if rem_url and not self.remote_url_var.get().strip():
                    self.remote_url_var.set(rem_url)
            elif not self.remote_url_var.get().strip():
                gh_user = self.engine.config.github_username
                if gh_user:
                    self.remote_url_var.set(f"https://github.com/{gh_user}/{dir_path.name}.git")

    def _do_save(self) -> None:
        raw_path = self.path_var.get().strip()
        if not raw_path:
            messagebox.showwarning("Campo requerido", "Por favor selecciona la carpeta local del proyecto.", parent=self)
            return

        dir_path = Path(raw_path).expanduser().resolve()
        if not dir_path.exists() or not dir_path.is_dir():
            messagebox.showerror("Directorio Inválido", f"La ruta especificada no existe o no es un directorio:\n{dir_path}", parent=self)
            return

        name = self.name_var.get().strip() or dir_path.name
        remote_url = self.remote_url_var.get().strip() or None
        mode = ProjectMode.from_string(self.mode_var.get())

        # Check if Git is initialized; if not, ask to init
        if not self.engine.git_manager.is_git_repo(dir_path):
            confirm = messagebox.askyesno(
                "Inicializar Repositorio Git",
                f"La carpeta seleccionada:\n'{dir_path}'\n\nno contiene un repositorio Git inicializado (.git).\n\n¿Deseas inicializarlo automáticamente con 'git init' ahora para comenzar a vigilarlo?",
                parent=self,
            )
            if not confirm:
                return

            init_ok, init_msg = self.engine.init_git_repo(dir_path)
            if not init_ok:
                messagebox.showerror("Error al inicializar Git", init_msg, parent=self)
                return

        # Add project with remote_url
        success, msg, created = self.engine.add_project(
            name=name,
            path=dir_path,
            mode=mode,
            remote_url=remote_url,
        )

        if success:
            display_name = created.name if created else name
            messagebox.showinfo(
                "Proyecto Registrado",
                f"El proyecto '{display_name}' ha sido registrado y el bot comenzó a vigilarlo exitosamente.",
                parent=self,
            )
            self.on_success()
            self.destroy()
        else:
            messagebox.showerror("Error al añadir proyecto", msg, parent=self)
