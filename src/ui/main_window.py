"""Main application window with two-column Dark Mode navigation and live dashboard."""

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Optional

from src.config.models import ProjectMode
from src.core.engine import BotEngine
from src.core.state import SystemStatus
from src.ui.components import (
    AddProjectDialog,
    GitHubConnectDialog,
    LogsView,
    ProjectCard,
    SettingsView,
)
from src.ui.sidebar import SidebarNav
from src.ui.styles import (
    BG_BUTTON_SECONDARY,
    BG_CARD,
    BG_HEADER,
    BG_WINDOW,
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_SUCCESS,
    FG_MUTED,
    FG_PRIMARY,
    FG_SECONDARY,
    FG_WHITE,
    FONT_BUTTON,
    FONT_CARD_TITLE,
    FONT_SMALL,
    FONT_SUBTITLE,
    FONT_TITLE,
)
from src.utils.logger import get_logger

logger = get_logger("ui")


class MainWindow(tk.Tk):
    """Main Dark Mode desktop interface for GH-BOT-REPOS-MAC on macOS."""

    def __init__(
        self,
        engine: BotEngine,
        on_quit_app: Callable[[], None],
    ) -> None:
        super().__init__()
        self.engine = engine
        self.on_quit_app = on_quit_app

        self.title("GH-BOT-REPOS-MAC")
        self.geometry("880x640")
        self.minsize(760, 520)
        self.configure(bg=BG_WINDOW)

        # Intercept window close to keep running in background
        self.protocol("WM_DELETE_WINDOW", self.hide_to_background)

        self.current_view_key = "all"
        self._build_layout()
        self._schedule_periodic_refresh()

    def _build_layout(self) -> None:
        # Main Horizontal Container: Left Sidebar + Right Content
        main_container = tk.Frame(self, bg=BG_WINDOW)
        main_container.pack(fill=tk.BOTH, expand=True)

        # 1. Left Sidebar Navigation
        self.sidebar = SidebarNav(
            main_container,
            on_view_selected=self._handle_view_change,
            on_quit_app=self.on_quit_app,
        )
        self.sidebar.pack(side=tk.LEFT, fill=tk.Y)

        # 2. Right Content Wrapper
        self.right_wrapper = tk.Frame(main_container, bg=BG_WINDOW)
        self.right_wrapper.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Top Header Bar
        self._build_header(self.right_wrapper)

        # Dynamic Content View Container
        self.content_area = tk.Frame(self.right_wrapper, bg=BG_WINDOW)
        self.content_area.pack(fill=tk.BOTH, expand=True)

        self._render_current_view()

    def _build_header(self, parent: tk.Widget) -> None:
        header = tk.Frame(parent, bg=BG_HEADER, padx=20, pady=14, highlightbackground=COLOR_BORDER, highlightthickness=1)
        header.pack(fill=tk.X)

        # Breadcrumb / View title
        self.header_title_lbl = tk.Label(
            header,
            text="Todos los Proyectos",
            font=FONT_TITLE,
            fg=FG_PRIMARY,
            bg=BG_HEADER,
        )
        self.header_title_lbl.pack(side=tk.LEFT)

        # Right Action Buttons: GitHub Status + Add Project
        right_actions = tk.Frame(header, bg=BG_HEADER)
        right_actions.pack(side=tk.RIGHT)

        self.gh_header_btn = tk.Button(
            right_actions,
            text="GitHub: Conectar",
            font=FONT_SMALL,
            bg=BG_BUTTON_SECONDARY,
            fg=FG_SECONDARY,
            activebackground=COLOR_BORDER,
            activeforeground=FG_WHITE,
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor="pointinghand",
            command=self._open_github_modal,
        )
        self.gh_header_btn.pack(side=tk.LEFT, padx=(0, 10))

        add_btn = tk.Button(
            right_actions,
            text="+ Añadir proyecto",
            font=FONT_BUTTON,
            bg=COLOR_ACCENT,
            fg=FG_WHITE,
            activebackground=COLOR_BORDER,
            activeforeground=FG_WHITE,
            relief=tk.FLAT,
            padx=12,
            pady=4,
            cursor="pointinghand",
            command=self._prompt_add_project,
        )
        add_btn.pack(side=tk.LEFT)

    def _handle_view_change(self, view_key: str) -> None:
        self.current_view_key = view_key
        titles = {
            "all": "Todos los Proyectos",
            "active": "Proyectos Activos",
            "paused": "Proyectos Pausados",
            "logs": "Registro de Actividad",
            "settings": "Configuración",
        }
        self.header_title_lbl.configure(text=titles.get(view_key, "GH-BOT-REPOS-MAC"))
        self._render_current_view()

    def _render_current_view(self) -> None:
        # Clear content area
        for widget in self.content_area.winfo_children():
            widget.destroy()

        if self.current_view_key in ("all", "active", "paused"):
            self._render_projects_view()
        elif self.current_view_key == "logs":
            LogsView(self.content_area).pack(fill=tk.BOTH, expand=True)
        elif self.current_view_key == "settings":
            SettingsView(self.content_area, engine=self.engine, on_refresh=self._render_current_view).pack(fill=tk.BOTH, expand=True)

    def _render_projects_view(self) -> None:
        system_status: SystemStatus = self.engine.get_system_status()

        # Update sidebar counts
        self.sidebar.update_counts(
            total=system_status.total_projects,
            active=system_status.active_projects,
            paused=system_status.paused_projects,
        )

        # Update GitHub pill
        gh_status = self.engine.get_github_status()
        if gh_status.connected and gh_status.username:
            self.gh_header_btn.configure(
                text=f"GitHub: @{gh_status.username}",
                fg=COLOR_SUCCESS,
            )
        else:
            self.gh_header_btn.configure(
                text="GitHub: Conectar",
                fg=FG_SECONDARY,
            )

        # Filter projects according to current view
        all_projects = system_status.projects
        if self.current_view_key == "active":
            displayed = [p for p in all_projects if p.enabled and p.mode != ProjectMode.PAUSED]
        elif self.current_view_key == "paused":
            displayed = [p for p in all_projects if p.mode == ProjectMode.PAUSED or not p.enabled]
        else:
            displayed = all_projects

        # Scrollable container for cards
        canvas = tk.Canvas(self.content_area, bg=BG_WINDOW, highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.content_area, orient="vertical", command=canvas.yview)
        scroll_frame = tk.Frame(canvas, bg=BG_WINDOW)

        scroll_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")

        def _on_canvas_resize(event):
            canvas.itemconfig(canvas_window, width=event.width)

        canvas.bind("<Configure>", _on_canvas_resize)
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=20, pady=16)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=16)

        if not displayed:
            empty_box = tk.Frame(scroll_frame, bg=BG_WINDOW, pady=60)
            empty_box.pack(fill=tk.X)
            tk.Label(
                empty_box,
                text="No hay proyectos en esta sección.\nHaz clic en '+ Añadir proyecto' para registrar un repositorio local.",
                font=FONT_SUBTITLE,
                fg=FG_MUTED,
                bg=BG_WINDOW,
                justify="center",
            ).pack()
            return

        for p_state in displayed:
            card = ProjectCard(
                parent=scroll_frame,
                state=p_state,
                on_mode_change=self._handle_mode_change,
                on_manual_sync=self._handle_manual_sync,
                on_delete=self._handle_delete_project,
            )
            card.pack(fill=tk.X, pady=(0, 12))

    def _schedule_periodic_refresh(self) -> None:
        if self.current_view_key in ("all", "active", "paused"):
            self._render_projects_view()
        self.after(2500, self._schedule_periodic_refresh)

    def _prompt_add_project(self) -> None:
        """Opens the modal dialog to configure local directory and GitHub remote URL."""
        AddProjectDialog(
            parent=self,
            engine=self.engine,
            on_success=self._render_current_view,
        )

    def _handle_mode_change(self, project_name: str, new_mode: ProjectMode) -> None:
        success, msg = self.engine.set_project_mode(project_name, new_mode)
        if success:
            self._render_current_view()
        else:
            messagebox.showerror("Error", msg, parent=self)

    def _handle_manual_sync(self, project_name: str) -> None:
        success, msg = self.engine.sync_project(project_name)
        self._render_current_view()
        if not success:
            messagebox.showwarning("Aviso de Sincronización", msg, parent=self)

    def _handle_delete_project(self, project_name: str) -> None:
        success, msg = self.engine.remove_project(project_name)
        if success:
            self._render_current_view()
        else:
            messagebox.showerror("Error al eliminar", msg, parent=self)

    def _open_github_modal(self) -> None:
        gh_status = self.engine.get_github_status()
        current_u = gh_status.username or self.engine.config.github_username
        GitHubConnectDialog(
            parent=self,
            current_user=current_u,
            on_connect=self.engine.connect_github,
            on_disconnect=self.engine.disconnect_github,
        )
        self._render_current_view()

    def hide_to_background(self) -> None:
        """Hides the main window while keeping BotEngine and watchers running in background."""
        self.withdraw()
        logger.info("[UI] Window minimized to background. Watchers remain active.")
        try:
            from src.utils.notifications import send_macos_notification
            send_macos_notification(
                message="GH-BOT-REPOS-MAC continúa activo en segundo plano vigilando tus proyectos.",
                subtitle="Ejecución en segundo plano",
            )
        except Exception:
            pass

    def show_window(self) -> None:
        """Brings the main window to foreground."""
        self.deiconify()
        self.lift()
        self.focus_force()
        self._render_current_view()
