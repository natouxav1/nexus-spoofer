"""
Nexus Spoofer - UI de mise à jour.
Popup non-bloquant qui s'affiche si une nouvelle version est disponible.
"""
import webbrowser
import customtkinter as ctk
from updater import download_update, apply_update
from version import CURRENT_VERSION, RELEASES_URL

# ─── DESIGN (sync avec gui.py) ────────────────────────────────────────────────
BG_DARK       = "#060609"
BG_PANEL      = "#0c0c14"
BG_CARD       = "#13131f"
ACCENT        = "#8b5cf6"
ACCENT_GLOW   = "#a78bfa"
ACCENT_MUTED  = "#4c1d95"
BORDER        = "#1e1e2e"
TEXT_PRIMARY  = "#f8faff"
TEXT_SECONDARY= "#94a3b8"
SUCCESS       = "#10b981"
DANGER        = "#f43f5e"
WARNING       = "#f59e0b"


class UpdatePopup(ctk.CTkToplevel):
    """
    Popup de mise à jour.
    - Affiche la version distante + changelog
    - Bouton "Mettre à jour" : télécharge + applique
    - Bouton "Plus tard"     : ferme (sauf si mandatory=True)
    """

    def __init__(self, parent, update_info: dict):
        super().__init__(parent)
        self.update_info = update_info
        self.title("")
        self.geometry("480x360")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        # Centrer sur le parent
        parent.update_idletasks()
        px = parent.winfo_x() + parent.winfo_width() // 2 - 240
        py = parent.winfo_y() + parent.winfo_height() // 2 - 180
        self.geometry(f"+{px}+{py}")

        self._build()

    def _build(self):
        info = self.update_info

        # Bordure accent
        border = ctk.CTkFrame(self, fg_color=ACCENT, corner_radius=20)
        border.pack(fill="both", expand=True, padx=1, pady=1)

        main = ctk.CTkFrame(border, fg_color=BG_DARK, corner_radius=19)
        main.pack(fill="both", expand=True, padx=2, pady=2)

        # Badge "MISE À JOUR"
        badge_frame = ctk.CTkFrame(main, fg_color=ACCENT_MUTED, corner_radius=20)
        badge_frame.pack(pady=(22, 0))
        ctk.CTkLabel(badge_frame, text="  ⬆  MISE À JOUR DISPONIBLE  ",
                     font=ctk.CTkFont("Segoe UI", 10, "bold"),
                     text_color=ACCENT_GLOW).pack(padx=10, pady=5)

        # Versions
        ver_frame = ctk.CTkFrame(main, fg_color="transparent")
        ver_frame.pack(pady=12)
        ctk.CTkLabel(ver_frame, text=f"v{CURRENT_VERSION}",
                     font=ctk.CTkFont("Consolas", 13),
                     text_color=TEXT_SECONDARY).pack(side="left")
        ctk.CTkLabel(ver_frame, text="  →  ",
                     font=ctk.CTkFont("Segoe UI", 13),
                     text_color=ACCENT_GLOW).pack(side="left")
        ctk.CTkLabel(ver_frame, text=f"v{info['version']}",
                     font=ctk.CTkFont("Consolas", 13, "bold"),
                     text_color=SUCCESS).pack(side="left")

        # Changelog
        if info.get("changelog"):
            log_box = ctk.CTkFrame(main, fg_color=BG_CARD, corner_radius=12,
                                   border_width=1, border_color=BORDER)
            log_box.pack(fill="x", padx=25, pady=(0, 12))
            ctk.CTkLabel(log_box, text="CHANGELOG",
                         font=ctk.CTkFont("Segoe UI", 9, "bold"),
                         text_color=ACCENT).pack(anchor="w", padx=12, pady=(8, 2))
            ctk.CTkLabel(log_box, text=info["changelog"],
                         font=ctk.CTkFont("Segoe UI", 11),
                         text_color=TEXT_SECONDARY,
                         justify="left", wraplength=380).pack(anchor="w", padx=12, pady=(0, 10))

        # Barre de progression (cachée au départ)
        self.pbar_frame = ctk.CTkFrame(main, fg_color="transparent")
        self.pbar_frame.pack(fill="x", padx=25)

        self.pbar = ctk.CTkProgressBar(self.pbar_frame, height=6,
                                       fg_color=BG_PANEL, progress_color=ACCENT)
        self.pbar.set(0)

        self.pbar_label = ctk.CTkLabel(self.pbar_frame, text="",
                                       font=ctk.CTkFont("Segoe UI", 10),
                                       text_color=TEXT_SECONDARY)

        # Boutons
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill="x", padx=25, pady=15)

        self.update_btn = ctk.CTkButton(
            btn_frame, text="⬆  Mettre à jour",
            height=42, corner_radius=12,
            fg_color=ACCENT, hover_color=ACCENT_GLOW,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            command=self._start_update)
        self.update_btn.pack(side="left", fill="x", expand=True, padx=(0, 8))

        mandatory = self.update_info.get("mandatory", False)
        self.later_btn = ctk.CTkButton(
            btn_frame,
            text="Plus tard" if not mandatory else "Obligatoire",
            height=42, corner_radius=12,
            fg_color=BG_CARD, hover_color=BG_PANEL,
            border_width=1, border_color=BORDER,
            font=ctk.CTkFont("Segoe UI", 12),
            text_color=TEXT_SECONDARY,
            state="normal" if not mandatory else "disabled",
            command=self.destroy)
        self.later_btn.pack(side="left", fill="x", expand=True)

    # ─── ACTIONS ──────────────────────────────────────────────────────────────

    def _start_update(self):
        url = self.update_info.get("download_url", "")

        # Pas d'URL directe → ouvrir la page releases
        if not url:
            webbrowser.open(RELEASES_URL)
            self.destroy()
            return

        self.update_btn.configure(state="disabled", text="Téléchargement...")
        self.later_btn.configure(state="disabled")

        # Afficher la barre
        self.pbar.pack(fill="x", pady=(0, 4))
        self.pbar_label.pack(anchor="w")

        download_update(
            url=url,
            on_progress=self._on_progress,
            on_done=self._on_done,
            on_error=self._on_error,
        )

    def _on_progress(self, percent: int):
        self.after(0, lambda: self._update_progress(percent))

    def _update_progress(self, percent: int):
        self.pbar.set(percent / 100)
        self.pbar_label.configure(text=f"Téléchargement... {percent}%")

    def _on_done(self, tmp_path: str):
        self.after(0, lambda: self._apply(tmp_path))

    def _apply(self, tmp_path: str):
        self.pbar.configure(progress_color=SUCCESS)
        self.pbar_label.configure(text="Installation en cours...", text_color=SUCCESS)
        self.update_btn.configure(text="Installation...")
        self.after(800, lambda: apply_update(tmp_path))

    def _on_error(self, msg: str):
        self.after(0, lambda: self._show_error(msg))

    def _show_error(self, msg: str):
        self.pbar.configure(progress_color=DANGER)
        self.pbar_label.configure(text=f"Erreur : {msg}", text_color=DANGER)
        self.update_btn.configure(
            state="normal", text="Réessayer",
            fg_color=DANGER, hover_color="#e11d48")
        self.later_btn.configure(state="normal")


def show_update_popup(parent, update_info: dict) -> None:
    """Affiche le popup de mise à jour si une update est disponible."""
    if update_info.get("available"):
        UpdatePopup(parent, update_info)
