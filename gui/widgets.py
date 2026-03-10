import tkinter as tk
import customtkinter as ctk
import webbrowser
from .theme import *


class SourceBadge(ctk.CTkLabel):
    def __init__(self, parent, source: str, **kwargs):
        color = SOURCE_COLORS.get(source, ACCENT)
        super().__init__(
            parent, text=f" {source} ",
            font=FONT_TINY, fg_color=color,
            text_color="#ffffff", corner_radius=4, **kwargs,
        )


class MagnetButton(ctk.CTkButton):
    def __init__(self, parent, link: str, index: int, copy_cb, open_cb, **kwargs):
        is_torrent = link.endswith(".torrent") or ".torrent?" in link
        label  = f"🗂 Torrent {index}" if is_torrent else f"🧲 Magnet {index}"
        color  = "#2d6a4f" if is_torrent else ACCENT2
        hover  = "#1b4332" if is_torrent else "#6a44a8"
        super().__init__(
            parent, text=label, font=FONT_SMALL,
            fg_color=color, hover_color=hover,
            text_color=TEXT_PRIMARY, corner_radius=6, height=28,
            command=lambda: (open_cb(link) if is_torrent else copy_cb(link)),
            **kwargs,
        )


class StatusBar(ctk.CTkFrame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent, fg_color=BG_PANEL, height=26, corner_radius=0, **kwargs)
        self._label = ctk.CTkLabel(self, text="Ready  •  Search for a game",
                                   font=FONT_TINY, text_color=TEXT_MUTED, anchor="w")
        self._label.pack(side="left", padx=12)
        self._right = ctk.CTkLabel(self, text="FitGirl · GoGUnlocked · RG Mechanics · CroTorrent",
                                   font=FONT_TINY, text_color=TEXT_MUTED, anchor="e")
        self._right.pack(side="right", padx=12)

    def set(self, msg: str, right: str = ""):
        self._label.configure(text=msg)
        if right:
            self._right.configure(text=right)


class SearchBar(ctk.CTkFrame):
    def __init__(self, parent, search_cb, **kwargs):
        super().__init__(parent, fg_color=BG_PANEL, corner_radius=12, **kwargs)
        title_row = ctk.CTkFrame(self, fg_color="transparent")
        title_row.pack(fill="x", padx=18, pady=(14, 4))
        ctk.CTkLabel(title_row, text="🎮  AhReon",
                     font=FONT_TITLE, text_color=ACCENT).pack(side="left")
        ctk.CTkLabel(title_row, text="FitGirl · GoGUnlocked · RG Mechanics · CroTorrent",
                     font=FONT_SMALL, text_color=TEXT_MUTED).pack(side="left", padx=(10, 0), pady=(6, 0))
        search_row = ctk.CTkFrame(self, fg_color="transparent")
        search_row.pack(fill="x", padx=18, pady=(0, 6))
        search_row.columnconfigure(0, weight=1)

        self.entry = ctk.CTkEntry(
            search_row,
            placeholder_text="  Search games…  e.g.  Cyberpunk 2077",
            font=FONT_BODY, fg_color=BG_INPUT, border_color=ACCENT,
            border_width=2, text_color=TEXT_PRIMARY,
            placeholder_text_color=TEXT_MUTED, corner_radius=10, height=40,
        )
        self.entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.entry.bind("<Return>", lambda _: search_cb())

        self.btn = ctk.CTkButton(
            search_row, text="  Search", font=FONT_SUBHEAD,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            text_color="#ffffff", corner_radius=10, height=40, width=110,
            command=search_cb,
        )
        self.btn.grid(row=0, column=1)
        toggle_row = ctk.CTkFrame(self, fg_color="transparent")
        toggle_row.pack(fill="x", padx=18, pady=(0, 12))
        ctk.CTkLabel(toggle_row, text="Sources:", font=FONT_SMALL,
                     text_color=TEXT_SECONDARY).pack(side="left", padx=(0, 8))

        self._source_vars = {}
        for source, color in SOURCE_COLORS.items():
            var = tk.BooleanVar(value=True)
            self._source_vars[source] = var
            ctk.CTkCheckBox(
                toggle_row, text=source, variable=var,
                font=FONT_SMALL, text_color=color,
                fg_color=color, hover_color=ACCENT_HOVER,
                checkmark_color="#ffffff",
            ).pack(side="left", padx=(0, 14))

    def get_query(self) -> str:
        return self.entry.get().strip()

    def get_sources(self):
        return [s for s, v in self._source_vars.items() if v.get()]

    def set_loading(self, loading: bool):
        self.btn.configure(
            text=" Searching…" if loading else "  Search",
            state="disabled" if loading else "normal",
        )


class GameCard(ctk.CTkFrame):
    def __init__(self, parent, game, click_cb, **kwargs):
        super().__init__(parent, fg_color=BG_CARD, corner_radius=12,
                         border_width=1, border_color=BORDER, **kwargs)
        self.game = game
        self._click_cb = click_cb
        self._build()
        self._bind_hover()

    def _build(self):
        self.img_label = ctk.CTkLabel(self, text="", width=100, height=130,
                                      fg_color=BG_CARD_HOVER, corner_radius=8)
        self.img_label.pack(side="left", padx=(10, 8), pady=10)

        info = ctk.CTkFrame(self, fg_color="transparent")
        info.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=10)

        top = ctk.CTkFrame(info, fg_color="transparent")
        top.pack(fill="x")
        SourceBadge(top, self.game.source).pack(side="left", padx=(0, 6))
        ctk.CTkLabel(
            top,
            text=self.game.title[:55] + ("…" if len(self.game.title) > 55 else ""),
            font=FONT_SUBHEAD, text_color=TEXT_PRIMARY, anchor="w", wraplength=220,
        ).pack(side="left", fill="x", expand=True)

        meta = ctk.CTkFrame(info, fg_color="transparent")
        meta.pack(fill="x", pady=(4, 2))
        ctk.CTkLabel(meta, text=f"💾 {self.game.size}", font=FONT_SMALL,
                     text_color=SUCCESS).pack(side="left", padx=(0, 12))
        ctk.CTkLabel(meta, text=f"📅 {self.game.date}", font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(side="left")

        if self.game.description:
            snippet = self.game.description[:120].replace("\n", " ")
            ctk.CTkLabel(info, text=snippet + "…", font=FONT_TINY,
                         text_color=TEXT_MUTED, anchor="w",
                         wraplength=270, justify="left").pack(fill="x", pady=(2, 0))

        ctk.CTkButton(
            info, text="View Details  →", font=FONT_SMALL,
            fg_color="transparent", hover_color=BG_CARD_HOVER,
            text_color=ACCENT, border_color=ACCENT, border_width=1,
            corner_radius=6, height=26, width=120, anchor="w",
            command=lambda: self._click_cb(self.game),
        ).pack(side="left", pady=(6, 0))

    def _bind_hover(self):
        def on_enter(e):
            self.configure(fg_color=BG_CARD_HOVER, border_color=ACCENT)
        def on_leave(e):
            self.configure(fg_color=BG_CARD, border_color=BORDER)
        for widget in self.winfo_children() + [self]:
            widget.bind("<Enter>", on_enter)
            widget.bind("<Leave>", on_leave)
            widget.bind("<Button-1>", lambda e: self._click_cb(self.game))


class DetailPanel(ctk.CTkScrollableFrame):
    def __init__(self, parent, copy_cb, **kwargs):
        super().__init__(parent, fg_color=BG_PANEL, corner_radius=0, **kwargs)
        self._copy_cb = copy_cb
        self._placeholder()

    def _placeholder(self):
        for w in self.winfo_children():
            w.destroy()
        ctk.CTkLabel(self, text="👈  Select a game\nto view details",
                     font=FONT_HEADING, text_color=TEXT_MUTED,
                     justify="center").pack(expand=True, pady=80)

    def show(self, game):
        for w in self.winfo_children():
            w.destroy()

        self.hero_label = ctk.CTkLabel(self, text="", height=180,
                                       fg_color=BG_CARD, corner_radius=10)
        self.hero_label.pack(fill="x", padx=14, pady=(14, 8))
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=14)
        SourceBadge(header, game.source).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(header, text=game.title, font=FONT_HEADING,
                     text_color=TEXT_PRIMARY, wraplength=240,
                     justify="left", anchor="w").pack(side="left", fill="x", expand=True)

        meta_frame = ctk.CTkFrame(self, fg_color=BG_CARD, corner_radius=8)
        meta_frame.pack(fill="x", padx=14, pady=8)

        def meta_row(icon, label, val):
            row = ctk.CTkFrame(meta_frame, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=2)
            ctk.CTkLabel(row, text=f"{icon} {label}:", font=FONT_SMALL,
                         text_color=TEXT_MUTED, width=80, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=val or "—", font=FONT_SMALL,
                         text_color=TEXT_PRIMARY, anchor="w",
                         wraplength=180).pack(side="left", fill="x", expand=True)

        meta_row("💾", "Size",      game.size)
        meta_row("📅", "Date",      game.date)
        meta_row("🌐", "Languages", game.languages or "—")
        meta_row("🎭", "Genres",    game.genres or "—")

        ctk.CTkButton(
            self, text="🌍  Open Page in Browser", font=FONT_SMALL,
            fg_color=BG_INPUT, hover_color=ACCENT2, text_color=TEXT_PRIMARY,
            corner_radius=8, height=32,
            command=lambda: webbrowser.open(game.url),
        ).pack(fill="x", padx=14, pady=(0, 6))

        if game.description:
            ctk.CTkLabel(self, text="Description", font=FONT_SUBHEAD,
                         text_color=TEXT_SECONDARY, anchor="w").pack(fill="x", padx=14, pady=(6, 2))
            ctk.CTkLabel(self, text=game.description, font=FONT_SMALL,
                         text_color=TEXT_MUTED, wraplength=260,
                         justify="left", anchor="nw").pack(fill="x", padx=14, pady=(0, 8))

        magnet_links = [l for l in game.magnets if l.startswith("magnet:")]
        torrent_links = [l for l in game.magnets if not l.startswith("magnet:")]

        for section_links, label, icon in [
            (magnet_links,  "Magnet Links",   "🧲"),
            (torrent_links, "Torrent Files",  "🗂"),
        ]:
            if not section_links:
                continue
            ctk.CTkLabel(self, text=f"{icon}  {label}  ({len(section_links)})",
                         font=FONT_SUBHEAD, text_color=TEXT_SECONDARY,
                         anchor="w").pack(fill="x", padx=14, pady=(8, 4))
            for i, link in enumerate(section_links[:10], 1):
                MagnetButton(self, link, i,
                             copy_cb=self._copy_cb,
                             open_cb=webbrowser.open,
                             ).pack(fill="x", padx=14, pady=2)

        if not game.magnets:
            ctk.CTkLabel(self, text="No links found.\nTry opening the page in browser.",
                         font=FONT_SMALL, text_color=TEXT_MUTED,
                         justify="left").pack(padx=14)
        if magnet_links:
            ctk.CTkButton(
                self, text="📋  Copy All Magnets", font=FONT_SMALL,
                fg_color=SUCCESS, hover_color="#009874", text_color="#000000",
                corner_radius=8, height=32,
                command=lambda: self._copy_cb("\n".join(magnet_links)),
            ).pack(fill="x", padx=14, pady=(6, 14))

    def set_hero_image(self, photo):
        if hasattr(self, "hero_label"):
            self.hero_label.configure(image=photo, text="")
            self.hero_label.image = photo
