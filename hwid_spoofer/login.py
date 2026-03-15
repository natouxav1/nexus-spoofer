"""
Nexus SPOOFER - License screen (Premium V2)
"""
import customtkinter as ctk
import sys, time, os
from PIL import Image
from license import activate

def _get_logo(size=(64, 64)):
    try:
        base = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(base, "icon256.png")
        if not os.path.exists(path):
            path = os.path.join(os.path.dirname(base), "icon256.png")
        img = Image.open(path)
        return ctk.CTkImage(img, size=size)
    except Exception:
        return None

# ─── DESIGN SYSTEM (Sync with gui.py) ─────────────────────────────────────────
BG_DARK      = "#060609"
BG_CARD      = "#13131f"
ACCENT       = "#8b5cf6"
ACCENT_GLOW  = "#a78bfa"
BORDER       = "#1e1e2e"
TEXT_PRIMARY = "#f8faff"
TEXT_SECONDARY= "#94a3b8"
SUCCESS      = "#10b981"
DANGER       = "#f43f5e"

def show_license_screen() -> bool:
    """
    Affiche la fenêtre de licence.
    Retourne True si activée avec succès, False si fermée sans activer.
    """
    result = {"ok": False}

    win = ctk.CTk()
    win.title("NEXUS - ACTIVATION")
    win.geometry("500x400")
    win.resizable(False, False)
    win.configure(fg_color=BG_DARK)

    # Center logic
    win.update_idletasks()
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"+{sw//2 - 250}+{sh//2 - 200}")

    # Main Frame with Glow Border
    container = ctk.CTkFrame(win, fg_color=ACCENT, corner_radius=24)
    container.pack(fill="both", expand=True, padx=2, pady=2)

    main = ctk.CTkFrame(container, fg_color=BG_DARK, corner_radius=22)
    main.pack(fill="both", expand=True, padx=1, pady=1)

    # Header
    logo_img = _get_logo(size=(64, 64))
    if logo_img:
        ctk.CTkLabel(main, image=logo_img, text="").pack(pady=(35, 5))
    else:
        ctk.CTkLabel(main, text="⬡", font=ctk.CTkFont("Segoe UI", 48),
                     text_color=ACCENT_GLOW).pack(pady=(40, 5))
    
    ctk.CTkLabel(main, text="NEXUS SPOOFER", 
                 font=ctk.CTkFont("Segoe UI", 24, "bold"), 
                 text_color=TEXT_PRIMARY).pack()
    
    ctk.CTkLabel(main, text="PORTAIL D'AUTHENTIFICATION", 
                 font=ctk.CTkFont("Segoe UI", 10, "bold"), 
                 text_color=ACCENT).pack(pady=(0, 25))

    # Input Area
    entry_frame = ctk.CTkFrame(main, fg_color="transparent")
    entry_frame.pack(fill="x", padx=60)

    entry = ctk.CTkEntry(
        entry_frame, width=320, height=50, corner_radius=15,
        fg_color=BG_CARD, border_color=BORDER, border_width=1,
        text_color=TEXT_PRIMARY, font=ctk.CTkFont("Consolas", 14),
        placeholder_text="Entrez votre clé...",
        placeholder_text_color=TEXT_SECONDARY,
        justify="center")
    entry.pack(pady=5)

    err_lbl = ctk.CTkLabel(main, text="",
                            font=ctk.CTkFont("Segoe UI", 11),
                            text_color=DANGER)
    err_lbl.pack(pady=(5, 15))

    btn = ctk.CTkButton(
        main, text="VÉRIFIER LA LICENCE", width=320, height=50,
        corner_radius=15, fg_color=ACCENT, hover_color=ACCENT_GLOW,
        font=ctk.CTkFont("Segoe UI", 13, "bold"), text_color="#ffffff")
    btn.pack()

    def _submit():
        key = entry.get().strip()
        if not key:
            err_lbl.configure(text="ACCÈS REFUSÉ : CLÉ REQUISE", text_color=DANGER)
            return
        
        btn.configure(state="disabled", text="VÉRIFICATION...")
        err_lbl.configure(text="")
        win.update()
        
        # Artificial delay for premium feel
        time.sleep(1.2)
        
        ok, msg = activate(key)
        if ok:
            err_lbl.configure(text=f"ACCÈS AUTORISÉ : {msg}", text_color=SUCCESS)
            entry.configure(state="disabled")
            btn.configure(text="AUTHENTIFIÉ", fg_color=SUCCESS)
            win.after(1500, win.destroy)
            result["ok"] = True
        else:
            err_lbl.configure(text=msg.upper(), text_color=DANGER)
            btn.configure(state="normal", text="RÉESSAYER")
            entry.delete(0, "end")

    btn.configure(command=_submit)
    entry.bind("<Return>", lambda e: _submit())
    
    win.protocol("WM_DELETE_WINDOW", win.destroy)
    win.mainloop()
    return result["ok"]
