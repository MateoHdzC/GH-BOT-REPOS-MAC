"""Sidebar navigation panel with category filters and system status."""

import tkinter as tk
from typing import Callable

from src.ui.styles import (
    BG_BUTTON_SECONDARY,
    BG_SIDEBAR,
    COLOR_ACCENT,
    COLOR_BORDER,
    COLOR_DANGER,
    COLOR_SUCCESS,
    FG_MUTED,
    FG_PRIMARY,
    FG_SECONDARY,
    FG_WHITE,
    FONT_BADGE,
    FONT_CARD_TITLE,
    FONT_NAV_ITEM,
    FONT_NAV_ITEM_ACTIVE,
    FONT_SECTION_HEADER,
    FONT_SMALL,
)


class SidebarNav(tk.Frame):
    """Sidebar navigation bar managing view switching and metric counts."""

    def __init__(
        self,
        parent: tk.Widget,
        on_view_selected: Callable[[str], None],
        on_quit_app: Callable[[], None],
        **kwargs,
    ) -> None:
        super().__init__(parent, bg=BG_SIDEBAR, width=220, highlightbackground=COLOR_BORDER, highlightthickness=1, **kwargs)
        self.pack_propagate(False)
        self.on_view_selected = on_view_selected
        self.on_quit_app = on_quit_app
        self.current_view = "all"

        self._nav_buttons: dict[str, tuple[tk.Button, tk.Label]] = {}

        self._build_ui()

    def _build_ui(self) -> None:
        # Header Brand
        brand_frame = tk.Frame(self, bg=BG_SIDEBAR, padx=16, pady=20)
        brand_frame.pack(fill=tk.X)

        title_lbl = tk.Label(
            brand_frame,
            text="GH-BOT-MAC",
            font=FONT_CARD_TITLE,
            fg=FG_PRIMARY,
            bg=BG_SIDEBAR,
        )
        title_lbl.pack(anchor="w")

        version_lbl = tk.Label(
            brand_frame,
            text="v1.0.0 • macOS Native",
            font=FONT_SMALL,
            fg=FG_MUTED,
            bg=BG_SIDEBAR,
        )
        version_lbl.pack(anchor="w", pady=(2, 0))

        # Divider
        tk.Frame(self, bg=COLOR_BORDER, height=1).pack(fill=tk.X, padx=16, pady=(0, 14))

        # Category: PROYECTOS
        tk.Label(
            self,
            text="PROYECTOS",
            font=FONT_SECTION_HEADER,
            fg=FG_MUTED,
            bg=BG_SIDEBAR,
            padx=16,
        ).pack(anchor="w", pady=(0, 6))

        self._create_nav_item("all", "📁  Todos", count="0")
        self._create_nav_item("active", "🟢  Activos", count="0")
        self._create_nav_item("paused", "⚪  Pausados", count="0")

        # Category: SISTEMA
        tk.Label(
            self,
            text="SISTEMA",
            font=FONT_SECTION_HEADER,
            fg=FG_MUTED,
            bg=BG_SIDEBAR,
            padx=16,
        ).pack(anchor="w", pady=(18, 6))

        self._create_nav_item("logs", "📋  Actividad / Logs")
        self._create_nav_item("settings", "⚙️  Configuración")

        # Bottom System Health & Quit
        bottom_frame = tk.Frame(self, bg=BG_SIDEBAR, padx=16, pady=16)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X)

        self.health_label = tk.Label(
            bottom_frame,
            text="🟢 Motor activo",
            font=FONT_SMALL,
            fg=COLOR_SUCCESS,
            bg=BG_SIDEBAR,
        )
        self.health_label.pack(anchor="w", pady=(0, 10))

        quit_btn = tk.Button(
            bottom_frame,
            text="Salir de GH-BOT",
            font=FONT_SMALL,
            fg=COLOR_DANGER,
            bg=BG_BUTTON_SECONDARY,
            activebackground=COLOR_BORDER,
            activeforeground=COLOR_DANGER,
            relief=tk.FLAT,
            padx=8,
            pady=4,
            cursor="pointinghand",
            command=self.on_quit_app,
        )
        quit_btn.pack(fill=tk.X)

        self.set_active_view("all")

    def _create_nav_item(self, view_key: str, label_text: str, count: str = "") -> None:
        item_frame = tk.Frame(self, bg=BG_SIDEBAR, padx=12, pady=2)
        item_frame.pack(fill=tk.X)

        btn = tk.Button(
            item_frame,
            text=f"  {label_text}",
            font=FONT_NAV_ITEM,
            fg=FG_SECONDARY,
            bg=BG_SIDEBAR,
            activebackground=BG_BUTTON_SECONDARY,
            activeforeground=FG_WHITE,
            relief=tk.FLAT,
            anchor="w",
            padx=4,
            pady=6,
            cursor="pointinghand",
            command=lambda: self._on_item_click(view_key),
        )
        btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

        badge = tk.Label(
            item_frame,
            text=count,
            font=FONT_BADGE,
            fg=FG_MUTED,
            bg=BG_SIDEBAR,
            padx=4,
        )
        if count != "":
            badge.pack(side=tk.RIGHT)

        self._nav_buttons[view_key] = (btn, badge)

    def _on_item_click(self, view_key: str) -> None:
        self.set_active_view(view_key)
        self.on_view_selected(view_key)

    def set_active_view(self, view_key: str) -> None:
        self.current_view = view_key
        for key, (btn, badge) in self._nav_buttons.items():
            if key == view_key:
                btn.configure(
                    font=FONT_NAV_ITEM_ACTIVE,
                    fg=FG_WHITE,
                    bg=BG_BUTTON_SECONDARY,
                )
            else:
                btn.configure(
                    font=FONT_NAV_ITEM,
                    fg=FG_SECONDARY,
                    bg=BG_SIDEBAR,
                )

    def update_counts(self, total: int, active: int, paused: int) -> None:
        if "all" in self._nav_buttons:
            self._nav_buttons["all"][1].configure(text=str(total))
        if "active" in self._nav_buttons:
            self._nav_buttons["active"][1].configure(text=str(active))
        if "paused" in self._nav_buttons:
            self._nav_buttons["paused"][1].configure(text=str(paused))
