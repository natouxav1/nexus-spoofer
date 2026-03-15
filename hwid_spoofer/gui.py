"""
Nexus SPOOFER - GUI (V2 Premium)
"""
import sys, threading, builtins, time, os
import customtkinter as ctk
from PIL import Image
from spoofer import (get_cpu, get_bios, get_motherboard, get_smbios_uuid,
                     backup, restore, spoof_all)
from autostart import install as autostart_install, uninstall as autostart_uninstall, is_installed as autostart_installed

def _get_logo(size=(48, 48)):
    """Charge le logo depuis le chemin relatif ou PyInstaller."""
    try:
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "icon256.png")
        if not os.path.exists(path):
            # fallback: chercher dans le dossier parent
            path = os.path.join(os.path.dirname(base), "icon256.png")
        img = Image.open(path)
        return ctk.CTkImage(img, size=size)
    except Exception:
        return None

# ─── DESIGN SYSTEM ────────────────────────────────────────────────────────────
BG_DARK      = "#060609"
BG_PANEL     = "#0c0c14"
BG_CARD      = "#13131f"
ACCENT       = "#8b5cf6"  # Vibrant Violet
ACCENT_GLOW  = "#a78bfa"
ACCENT_MUTED = "#4c1d95"
BORDER       = "#1e1e2e"
TEXT_PRIMARY = "#f8faff"
TEXT_SECONDARY= "#94a3b8"
TEXT_ACCENT  = "#c4b5fd"
SUCCESS      = "#10b981"
DANGER       = "#f43f5e"
WARNING      = "#f59e0b"

ctk.set_appearance_mode("dark")

class GlossyButton(ctk.CTkButton):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, 
                         height=42,
                         corner_radius=12,
                         font=ctk.CTkFont("Segoe UI", 13, "bold"),
                         border_width=1,
                         border_color=BORDER,
                         **kwargs)

class InfoCard(ctk.CTkFrame):
    def __init__(self, parent, label, value="---", icon="◈", **kwargs):
        super().__init__(parent, fg_color=BG_CARD, corner_radius=15, 
                         border_width=1, border_color=BORDER, **kwargs)
        
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=15, pady=(12, 0))

        ctk.CTkLabel(header, text=icon, font=ctk.CTkFont("Segoe UI", 14),
                     text_color=ACCENT_GLOW).pack(side="left")
        
        self.label_lbl = ctk.CTkLabel(header, text=label.upper(), 
                                      font=ctk.CTkFont("Segoe UI", 10, "bold"),
                                      text_color=TEXT_SECONDARY)
        self.label_lbl.pack(side="left", padx=8)
        
        self.value_lbl = ctk.CTkLabel(self, text=value, 
                                      font=ctk.CTkFont("Consolas", 12),
                                      text_color=TEXT_PRIMARY)
        self.value_lbl.pack(anchor="w", padx=15, pady=(2, 12))

    def update_value(self, val):
        self.value_lbl.configure(text=val)

class LoadingPopup(ctk.CTkToplevel):
    def __init__(self, parent, title="CHARGEMENT", message="Opération en cours..."):
        super().__init__(parent)
        self.title("")
        self.geometry("380x200")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        self.overrideredirect(True)
        self.attributes("-topmost", True)

        # Center logic
        parent.update_idletasks()
        px = parent.winfo_x() + parent.winfo_width() // 2 - 190
        py = parent.winfo_y() + parent.winfo_height() // 2 - 100
        self.geometry(f"+{px}+{py}")

        self.border_frame = ctk.CTkFrame(self, fg_color=ACCENT, corner_radius=20)
        self.border_frame.pack(fill="both", expand=True, padx=1, pady=1)

        self.main_frame = ctk.CTkFrame(self.border_frame, fg_color=BG_DARK, corner_radius=19)
        self.main_frame.pack(fill="both", expand=True, padx=2, pady=2)

        # Logo dans le popup
        popup_logo = _get_logo(size=(36, 36))
        if popup_logo:
            ctk.CTkLabel(self.main_frame, image=popup_logo, text="").pack(pady=(18, 0))

        self.title_lbl = ctk.CTkLabel(self.main_frame, text=title, 
                                      font=ctk.CTkFont("Segoe UI", 16, "bold"),
                                      text_color=ACCENT_GLOW)
        self.title_lbl.pack(pady=(8, 5))
        self.msg_lbl = ctk.CTkLabel(self.main_frame, text=message, 
                                   font=ctk.CTkFont("Segoe UI", 12),
                                   text_color=TEXT_SECONDARY)
        self.msg_lbl.pack(pady=(0, 20))

        self.pbar = ctk.CTkProgressBar(self.main_frame, width=280, height=6, 
                                       fg_color=BG_PANEL, progress_color=ACCENT)
        self.pbar.pack()
        self.pbar.set(0)
        self.pbar.configure(mode="indeterminate")
        self.pbar.start()

    def finish(self, success=True, msg="Terminé"):
        self.pbar.stop()
        self.pbar.configure(mode="determinate", progress_color=SUCCESS if success else DANGER)
        self.pbar.set(1)
        self.msg_lbl.configure(text=msg, text_color=SUCCESS if success else DANGER)
        self.after(1000, self.destroy)

class NexusSpoofer(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NEXUS SPOOFER PREMIUM")
        self.geometry("860x600")
        self.resizable(False, False)
        self.configure(fg_color=BG_DARK)
        
        self._build_sidebar()
        self._build_main_content()
        
        self.after(500, lambda: threading.Thread(target=self._refresh_ids, daemon=True).start())

    def _build_sidebar(self):
        self.sidebar = ctk.CTkFrame(self, fg_color=BG_PANEL, width=220, corner_radius=0)
        self.sidebar.pack(side="left", fill="y")
        self.sidebar.pack_propagate(False)

        # Logo
        logo_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        logo_frame.pack(pady=40, padx=20, fill="x")

        logo_img = _get_logo(size=(40, 40))
        if logo_img:
            ctk.CTkLabel(logo_frame, image=logo_img, text="").pack(side="left")
        else:
            ctk.CTkLabel(logo_frame, text="⬡", font=ctk.CTkFont("Segoe UI", 32),
                         text_color=ACCENT_GLOW).pack(side="left")
        ctk.CTkLabel(logo_frame, text=" NEXUS", font=ctk.CTkFont("Segoe UI", 20, "bold"), 
                     text_color=TEXT_PRIMARY).pack(side="left", padx=5)

        # Nav
        self.nav_label = ctk.CTkLabel(self.sidebar, text="DASHBOARD", 
                                      font=ctk.CTkFont("Segoe UI", 10, "bold"),
                                      text_color=ACCENT)
        self.nav_label.pack(anchor="w", padx=30, pady=(20, 10))

        self.btn_refresh = GlossyButton(self.sidebar, text="  ↻   Actualiser", 
                                        fg_color="transparent", hover_color=BG_CARD,
                                        anchor="w", command=self._refresh_ids_thread)
        self.btn_refresh.pack(fill="x", padx=15, pady=5)

        self.btn_backup = GlossyButton(self.sidebar, text="  📥   Sauvegarder", 
                                       fg_color="transparent", hover_color=BG_CARD,
                                       anchor="w", command=self._do_backup_thread)
        self.btn_backup.pack(fill="x", padx=15, pady=5)

        self.btn_restore = GlossyButton(self.sidebar, text="  📤   Restaurer", 
                                        fg_color="transparent", hover_color=BG_CARD,
                                        anchor="w", command=self._do_restore_thread)
        self.btn_restore.pack(fill="x", padx=15, pady=5)

        ctk.CTkFrame(self.sidebar, fg_color=BORDER, height=1).pack(fill="x", padx=25, pady=20)

        # Autostart
        self.auto_btn = GlossyButton(self.sidebar, text="  🚀   Auto-spoof: OFF", 
                                     fg_color="transparent", hover_color=BG_CARD,
                                     anchor="w", command=self._toggle_autostart_thread)
        self.auto_btn.pack(fill="x", padx=15, pady=5)
        self._update_autostart_btn()

        # Update check
        self.update_btn_sidebar = GlossyButton(
            self.sidebar, text="  🔄   Mises à jour",
            fg_color="transparent", hover_color=BG_CARD,
            anchor="w", command=self._check_update_thread)
        self.update_btn_sidebar.pack(fill="x", padx=15, pady=5)

        # Footer avec version
        from version import CURRENT_VERSION
        footer = ctk.CTkLabel(self.sidebar, text=f"v{CURRENT_VERSION} Elite Edition",
                              font=ctk.CTkFont("Segoe UI", 10), text_color=TEXT_SECONDARY)
        footer.pack(side="bottom", pady=20)

    def _build_main_content(self):
        self.main_container = ctk.CTkFrame(self, fg_color="transparent")
        self.main_container.pack(side="right", fill="both", expand=True, padx=30, pady=30)

        # Header section
        header_frame = ctk.CTkFrame(self.main_container, fg_color="transparent")
        header_frame.pack(fill="x", pady=(0, 30))
        
        ctk.CTkLabel(header_frame, text="Identifiants Matériels Actifs", 
                     font=ctk.CTkFont("Segoe UI", 24, "bold"), text_color=TEXT_PRIMARY).pack(side="left")
        
        self.status_pill = ctk.CTkFrame(header_frame, fg_color=ACCENT_MUTED, corner_radius=20)
        self.status_pill.pack(side="right")
        self.status_dot = ctk.CTkLabel(self.status_pill, text="●", text_color=ACCENT_GLOW, font=("", 14))
        self.status_dot.pack(side="left", padx=(12, 5), pady=5)
        self.status_lbl = ctk.CTkLabel(self.status_pill, text="Système Prêt", font=ctk.CTkFont("Segoe UI", 11, "bold"), text_color=ACCENT_GLOW)
        self.status_lbl.pack(side="left", padx=(0, 12), pady=5)

        # Cards Grid
        grid = ctk.CTkFrame(self.main_container, fg_color="transparent")
        grid.pack(fill="x", pady=10)
        
        self.cards = {}
        row1 = ctk.CTkFrame(grid, fg_color="transparent")
        row1.pack(fill="x", pady=5)
        self.cards["CPU"] = InfoCard(row1, "ID Processeur", icon="🧠")
        self.cards["CPU"].pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.cards["BIOS"] = InfoCard(row1, "Version BIOS", icon="📟")
        self.cards["BIOS"].pack(side="left", fill="both", expand=True)

        row2 = ctk.CTkFrame(grid, fg_color="transparent")
        row2.pack(fill="x", pady=5)
        self.cards["Motherboard"] = InfoCard(row2, "Série Carte Mère", icon="🧩")
        self.cards["Motherboard"].pack(side="left", fill="both", expand=True, padx=(0, 10))
        self.cards["smBIOS UUID"] = InfoCard(row2, "smBIOS UUID", icon="🆔")
        self.cards["smBIOS UUID"].pack(side="left", fill="both", expand=True)

        # Spoofer Button Large
        self.spoof_btn = ctk.CTkButton(self.main_container, text="⚡  LANCER LE SPOOFING GLOBAL", 
                                       height=70, corner_radius=18,
                                       fg_color=ACCENT, hover_color=ACCENT_GLOW,
                                       border_width=2, border_color=ACCENT_MUTED,
                                       font=ctk.CTkFont("Segoe UI", 18, "bold"),
                                       command=self._do_spoof_thread)
        self.spoof_btn.pack(fill="x", pady=30)

        # Console
        console_box = ctk.CTkFrame(self.main_container, fg_color=BG_PANEL, corner_radius=15, 
                                   border_width=1, border_color=BORDER)
        console_box.pack(fill="both", expand=True)
        
        ctk.CTkLabel(console_box, text="TERMINAL_LOG_SYSTÈME", font=ctk.CTkFont("Consolas", 10, "bold"),
                     text_color=ACCENT_GLOW).pack(anchor="w", padx=15, pady=10)
        
        self.log_text = ctk.CTkTextbox(console_box, fg_color="transparent", font=ctk.CTkFont("Consolas", 11),
                                      text_color=TEXT_SECONDARY, border_width=0)
        self.log_text.pack(fill="both", expand=True, padx=5, pady=(0, 10))
        self.log_text.configure(state="disabled")

    # ─── LOGIC ────────────────────────────────────────────────────────────────

    def _log(self, msg, type="INFO"):
        colors = {"INFO": TEXT_SECONDARY, "SUCCESS": SUCCESS, "ERROR": DANGER, "WARN": WARNING, "ACCENT": ACCENT_GLOW}
        color = colors.get(type, TEXT_SECONDARY)
        ts = time.strftime("%H:%M:%S")
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{ts}] ", TEXT_SECONDARY)
        self.log_text.insert("end", f"{msg}\n", color)
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_status(self, text, color=ACCENT_GLOW):
        self.status_lbl.configure(text=text.upper(), text_color=color)
        self.status_dot.configure(text_color=color)

    def _update_autostart_btn(self):
        if autostart_installed():
            self.auto_btn.configure(text="  🚀   Auto-spoof: ON", text_color=SUCCESS)
        else:
            self.auto_btn.configure(text="  🚀   Auto-spoof: OFF", text_color=TEXT_SECONDARY)

    def _capture(self, fn, *args):
        lines = []
        orig = builtins.print
        def _p(*a, **k): lines.append(' '.join(str(x) for x in a))
        builtins.print = _p
        try: fn(*args)
        finally: builtins.print = orig
        return lines

    # Thread Wrappers
    def _refresh_ids_thread(self): threading.Thread(target=self._refresh_ids, daemon=True).start()
    def _do_backup_thread(self): threading.Thread(target=self._do_backup, daemon=True).start()
    def _do_spoof_thread(self): threading.Thread(target=self._do_spoof, daemon=True).start()
    def _do_restore_thread(self): threading.Thread(target=self._do_restore, daemon=True).start()
    def _toggle_autostart_thread(self): threading.Thread(target=self._toggle_autostart, daemon=True).start()
    def _check_update_thread(self): threading.Thread(target=self._check_update, daemon=True).start()

    # Core Actions
    def _refresh_ids(self):
        self._set_status("Scan en cours...", WARNING)
        self._log("Lancement de l'analyse matérielle...", "ACCENT")
        try:
            ids = {"CPU": get_cpu(), "BIOS": get_bios(), "Motherboard": get_motherboard(), "smBIOS UUID": get_smbios_uuid()}
            for k, v in ids.items():
                self.cards[k].update_value(v)
            self._log("Analyse terminée. Identifiants synchronisés.", "SUCCESS")
            self._set_status("Système Prêt", SUCCESS)
        except Exception as e:
            self._log(f"Échec de l'analyse : {e}", "ERROR")
            self._set_status("Erreur", DANGER)

    def _do_backup(self):
        self._set_status("Sauvegarde...", WARNING)
        popup = LoadingPopup(self, "BACKUP", "Archivage du profil matériel actuel...")
        try:
            lines = self._capture(backup)
            for l in lines: self._log(l.strip(), "INFO")
            popup.finish(True, "Profil Archivé")
            self._set_status("Backup Sauvé", SUCCESS)
        except Exception as e:
            self._log(f"Échec du backup : {e}", "ERROR")
            popup.finish(False, "Opération Échouée")
            self._set_status("Erreur", DANGER)

    def _do_spoof(self):
        self.spoof_btn.configure(state="disabled", text="⚡  APPLICATION DU PATCH...")
        self._set_status("Patching...", WARNING)
        popup = LoadingPopup(self, "SPOOFER", "Obfuscation matérielle en cours...")
        try:
            lines = self._capture(spoof_all)
            for l in lines: 
                typ = "SUCCESS" if "[+]" in l else "ERROR" if "[-]" in l else "INFO"
                label = l.replace("[+]", "✔").replace("[-]", "✘").replace("[*]", "◈")
                self._log(label.strip(), typ)
            popup.finish(True, "Matériel Spoofé")
            self._log("Spoof terminé. REDÉMARRAGE REQUIS pour les changements Kernel.", "WARN")
            self._set_status("Spoofé (Restart)", SUCCESS)
        except Exception as e:
            self._log(f"Échec du spoofing : {e}", "ERROR")
            popup.finish(False, "Erreur Critique")
            self._set_status("Erreur", DANGER)
        finally:
            self.spoof_btn.configure(state="normal", text="⚡  LANCER LE SPOOFING GLOBAL")
            self._refresh_ids()

    def _do_restore(self):
        self._set_status("Restauration...", WARNING)
        popup = LoadingPopup(self, "RESTAURER", "Retour aux identifiants d'usine...")
        try:
            lines = self._capture(restore)
            for l in lines: self._log(l.strip(), "INFO")
            popup.finish(True, "Profil Restauré")
            self._set_status("État d'Usine", SUCCESS)
        except Exception as e:
            self._log(f"Échec de restauration : {e}", "ERROR")
            popup.finish(False, "Échec Opération")
            self._set_status("Erreur", DANGER)
        finally:
            self._refresh_ids()

    def _toggle_autostart(self):
        if autostart_installed():
            ok, msg = autostart_uninstall()
        else:
            ok, msg = autostart_install()
        self._log(msg, "SUCCESS" if ok else "ERROR")
        self._update_autostart_btn()

    def _check_update(self):
        from updater import check_for_update
        from update_ui import show_update_popup
        self._log("Vérification des mises à jour...", "ACCENT")
        self.update_btn_sidebar.configure(state="disabled", text="  🔄   Vérification...")
        result = check_for_update()
        self.update_btn_sidebar.configure(state="normal", text="  🔄   Mises à jour")
        if result.get("error"):
            self._log(f"Mise à jour : {result['error']}", "WARN")
        elif result.get("available"):
            self._log(f"Nouvelle version disponible : v{result['version']}", "SUCCESS")
            self.after(0, lambda: show_update_popup(self, result))
        else:
            self._log("Application à jour.", "SUCCESS")

if __name__ == "__main__":
    app = NexusSpoofer()
    app.mainloop()
