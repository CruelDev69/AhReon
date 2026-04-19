import tkinter as tk
import customtkinter as ctk
import threading
from typing import List, Optional

from gui.theme import *
from scraper import GameResult, search_all, fetch_details, ALL_SOURCES
from gui.widgets import SearchBar, GameCard, DetailPanel, StatusBar
from gui.image_loader import load_image_async
import os

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

BATCH_SIZE = 8


class GameFinderApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("AhReon")
        try:
            icon_path = os.path.join(os.getcwd(), "assets", "AhReon.ico")
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass
        self.geometry(f"{APP_WIDTH}x{APP_HEIGHT}")
        self.minsize(MIN_WIDTH, MIN_HEIGHT)
        self.configure(fg_color=BG_DARK)

        self._results: List[GameResult] = []
        self._selected: Optional[GameResult] = None
        self._render_index: int = 0         
        self._search_id: int = 0          

        self._build_ui()

    # ─────────────────────────────────────────
    #  UI Build
    # ─────────────────────────────────────────

    def _build_ui(self):
        self.status = StatusBar(self)
        self.status.pack(side="bottom", fill="x")

        self.search_bar = SearchBar(self, search_cb=self._on_search)
        self.search_bar.pack(side="top", fill="x")

        self.main_frame = ctk.CTkFrame(self, fg_color="transparent", corner_radius=0)
        self.main_frame.pack(side="top", fill="both", expand=True)

        self.results_frame = ctk.CTkScrollableFrame(
            self.main_frame, fg_color=BG_DARK, corner_radius=0,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=ACCENT,
        )
        self.results_frame.pack(side="left", fill="both", expand=True, padx=(10, 5), pady=10)

        ctk.CTkFrame(self.main_frame, fg_color=BORDER, width=1,
                     corner_radius=0).pack(side="left", fill="y", pady=10)

        self.detail_panel = DetailPanel(
            self.main_frame, copy_cb=self._copy_to_clipboard, width=300)
        self.detail_panel.pack(side="right", fill="y")

        self._show_splash()

    # ─────────────────────────────────────────
    #  Splash
    # ─────────────────────────────────────────

    def _show_splash(self):
        self._clear_results_frame()
        splash = ctk.CTkFrame(self.results_frame, fg_color="transparent")
        splash.pack(expand=True, pady=60, padx=40)

        ctk.CTkLabel(splash, text="🎮", font=("Segoe UI Emoji", 64),
                     text_color=ACCENT).pack()
        ctk.CTkLabel(splash, text="AhReon",
                     font=("Segoe UI", 32, "bold"),
                     text_color=TEXT_PRIMARY).pack(pady=(8, 0))
        ctk.CTkLabel(
            splash,
            text="Search across FitGirl · GoGUnlocked · RG Mechanics · CroTorrent\n"
                 "to find repacks and grab magnet/torrent links instantly.",
            font=FONT_BODY, text_color=TEXT_SECONDARY, justify="center",
        ).pack(pady=(6, 20))

        tips = [
            ("🔍", "Type a game name and press Enter or click Search"),
            ("🧲", "Click any result to load magnet/torrent links"),
            ("📋", "Copy individual or all magnets with one click"),
            ("🌍", "Open the full page in your browser for more info"),
        ]
        for icon, tip in tips:
            row = ctk.CTkFrame(splash, fg_color=BG_CARD, corner_radius=8)
            row.pack(fill="x", pady=3, ipady=4, ipadx=8)
            ctk.CTkLabel(row, text=icon, font=("Segoe UI Emoji", 16),
                         width=30).pack(side="left", padx=(8, 4))
            ctk.CTkLabel(row, text=tip, font=FONT_SMALL,
                         text_color=TEXT_SECONDARY,
                         anchor="w").pack(side="left", fill="x", expand=True)

    # ─────────────────────────────────────────
    #  Search  ← main fix here
    # ─────────────────────────────────────────

    def _on_search(self):
        query = self.search_bar.get_query()
        if not query:
            return
        sources = self.search_bar.get_sources()
        if not sources:
            self.status.set("⚠  Please select at least one source.")
            return

        # Increment ID so any older in-flight search is ignored
        self._search_id += 1
        my_id = self._search_id

        self._clear_results_frame()
        self._show_loading()
        self.search_bar.set_loading(True)
        self.status.set(f"🔍  Searching '{query}' in {', '.join(sources)}…")

        def worker():
            results = search_all(query, sources)  
            if my_id != self._search_id:
                return
            self.after(0, lambda: self._on_results(results, query))

        threading.Thread(target=worker, daemon=True).start()

    def _show_loading(self):
        f = ctk.CTkFrame(self.results_frame, fg_color="transparent")
        f.pack(expand=True, pady=60)
        ctk.CTkLabel(f, text="⏳  Searching…", font=FONT_HEADING,
                     text_color=TEXT_SECONDARY).pack()
        bar = ctk.CTkProgressBar(
            f, mode="indeterminate", fg_color=BORDER,
            progress_color=ACCENT, width=300)
        bar.pack(pady=12)
        bar.start()

    # ─────────────────────────────────────────
    #  Results  ← batch rendering fix
    # ─────────────────────────────────────────

    def _on_results(self, results: List[GameResult], query: str):
        self._results = results
        self._render_index = 0
        self.search_bar.set_loading(False)
        self._clear_results_frame()

        if not results:
            self._show_no_results(query)
            self.status.set(f"No results found for '{query}'")
            return

        counts = {}
        for r in results:
            counts[r.source] = counts.get(r.source, 0) + 1

        self.status.set(
            f"✅  {len(results)} result(s) for '{query}'",
            "  ·  ".join(f"{s}: {n}" for s, n in counts.items()),
        )

        # Summary bar
        summary = ctk.CTkFrame(self.results_frame, fg_color=BG_PANEL, corner_radius=8)
        summary.pack(fill="x", padx=4, pady=(0, 8))
        ctk.CTkLabel(summary, text=f"  {len(results)} results",
                     font=FONT_SUBHEAD, text_color=TEXT_PRIMARY).pack(
            side="left", padx=10, pady=6)
        for src, count in counts.items():
            color = SOURCE_COLORS.get(src, ACCENT)
            ctk.CTkLabel(summary, text=f"{src}: {count}",
                         font=FONT_SMALL, text_color=color).pack(side="left", padx=8)

        # Render first batch immediately, rest lazily
        self._render_batch()

    def _render_batch(self):
        end = min(self._render_index + BATCH_SIZE, len(self._results))
        for i in range(self._render_index, end):
            game = self._results[i]
            card = GameCard(self.results_frame, game,
                            click_cb=self._on_game_click)
            card.pack(fill="x", padx=4, pady=4)

            if game.image_url:
                img_label = card.img_label
                load_image_async(
                    game.image_url, 100, 130,
                    callback=lambda ph, lbl=img_label: self.after(
                        0, lambda p=ph, l=lbl: self._set_card_image(l, p)
                    ),
                )

        self._render_index = end

        if self._render_index < len(self._results):
            self.after(30, self._render_batch)

    def _set_card_image(self, label, photo):
        try:
            label.configure(image=photo, text="")
        except Exception:
            pass

    def _show_no_results(self, query):
        f = ctk.CTkFrame(self.results_frame, fg_color="transparent")
        f.pack(expand=True, pady=60, padx=40)
        ctk.CTkLabel(f, text="😕", font=("Segoe UI Emoji", 48)).pack()
        ctk.CTkLabel(f, text=f"No results for '{query}'",
                     font=FONT_HEADING, text_color=TEXT_PRIMARY).pack(pady=(8, 4))
        ctk.CTkLabel(
            f,
            text="Try a different spelling or check your source filters.",
            font=FONT_BODY, text_color=TEXT_MUTED, justify="center",
        ).pack()

    # ─────────────────────────────────────────
    #  Game click / detail
    # ─────────────────────────────────────────

    def _on_game_click(self, game: GameResult):
        self._selected = game
        self.status.set(f"📦  Loading details for '{game.title}'…")
        self.detail_panel.show(game)

        def worker():
            updated = fetch_details(game)
            self.after(0, lambda: self._on_details_loaded(updated))

        threading.Thread(target=worker, daemon=True).start()

    def _on_details_loaded(self, game: GameResult):
        self._selected = game
        self.detail_panel.show(game)
        n_mag = sum(1 for l in game.magnets if l.startswith("magnet:"))
        n_tor = sum(1 for l in game.magnets if not l.startswith("magnet:"))
        parts = []
        if n_mag:
            parts.append(f"{n_mag} magnet(s)")
        if n_tor:
            parts.append(f"{n_tor} torrent(s)")
        self.status.set(
            f"✅  {game.title}  —  {', '.join(parts) or 'no links found'}")
        if game.image_url:
            load_image_async(
                game.image_url, 280, 180,
                callback=lambda ph: self.after(
                    0, lambda p=ph: self.detail_panel.set_hero_image(p)
                ),
                rounded=True,
            )

    # ─────────────────────────────────────────
    #  Helpers
    # ─────────────────────────────────────────

    def _clear_results_frame(self):
        for w in self.results_frame.winfo_children():
            w.destroy()

    def _copy_to_clipboard(self, text: str):
        self.clipboard_clear()
        self.clipboard_append(text)
        self.update()
        prev = self.status._label.cget("text")
        self.status.set("📋  Copied to clipboard!")
        self.after(2500, lambda: self.status.set(prev))
