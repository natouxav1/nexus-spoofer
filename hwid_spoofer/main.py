import ctypes
import sys
import os

# Ensure local imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

from license import check_saved
from login import show_license_screen
from spoofer import spoof_all
from updater import check_async

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def main():
    # 0. Handle silent mode (for autostart task)
    if "--silent" in sys.argv:
        if is_admin():
            spoof_all()
        sys.exit()

    # 1. Admin elevation check
    if not is_admin():
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable,
            f'"{os.path.abspath(__file__)}"', None, 1)
        sys.exit()

    # 2. License check
    valid, key, msg = check_saved()

    if not valid:
        activated = show_license_screen()
        if not activated:
            sys.exit()

    # 3. Launch Main GUI
    try:
        from gui import NexusSpoofer
        from update_ui import show_update_popup

        app = NexusSpoofer()

        # Vérification de mise à jour en arrière-plan après démarrage
        def _on_update_check(result):
            if result.get("available"):
                app.after(0, lambda: show_update_popup(app, result))

        check_async(_on_update_check)

        app.mainloop()
    except Exception as e:
        input(f"CRITICAL ERROR: {e}\nPress Enter to exit...")

if __name__ == "__main__":
    main()
