"""
Nexus Spoofer - Système de mise à jour automatique.

Flux:
  1. check_for_update()  -> compare version locale vs version.json distant
  2. download_update()   -> télécharge le nouvel .exe avec progression
  3. apply_update()      -> remplace l'exe courant et relance

Format attendu du version.json distant:
{
  "version": "2.5.0",
  "changelog": "- Fix spoofing\n- Nouvelle UI",
  "download_url": "https://github.com/.../releases/download/v2.5.0/NexusSpoofer.exe",
  "mandatory": false
}
"""

import os
import sys
import json
import shutil
import tempfile
import threading
import subprocess
import urllib.request
import urllib.error
from typing import Callable, Optional
from version import CURRENT_VERSION, VERSION_CHECK_URL

# ─── VERSION UTILS ────────────────────────────────────────────────────────────

def _parse_version(v: str) -> tuple:
    """Convertit '2.4.1' en (2, 4, 1) pour comparaison."""
    try:
        return tuple(int(x) for x in v.strip().lstrip("v").split("."))
    except Exception:
        return (0, 0, 0)

def is_newer(remote: str, local: str = CURRENT_VERSION) -> bool:
    return _parse_version(remote) > _parse_version(local)

# ─── CHECK ────────────────────────────────────────────────────────────────────

def check_for_update(timeout: int = 8) -> dict:
    """
    Vérifie si une mise à jour est disponible.
    
    Retourne:
        {
            "available": bool,
            "version": str,
            "changelog": str,
            "download_url": str,
            "mandatory": bool,
            "error": str | None
        }
    """
    result = {
        "available": False,
        "version": CURRENT_VERSION,
        "changelog": "",
        "download_url": "",
        "mandatory": False,
        "error": None,
    }

    try:
        req = urllib.request.Request(
            VERSION_CHECK_URL,
            headers={"User-Agent": "NexusSpoofer-Updater/1.0", "Cache-Control": "no-cache"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        remote_version = data.get("version", "0.0.0")
        result["version"]      = remote_version
        result["changelog"]    = data.get("changelog", "")
        result["download_url"] = data.get("download_url", "")
        result["mandatory"]    = data.get("mandatory", False)
        result["available"]    = is_newer(remote_version)

    except urllib.error.URLError as e:
        result["error"] = f"Connexion impossible : {e.reason}"
    except json.JSONDecodeError:
        result["error"] = "Réponse serveur invalide"
    except Exception as e:
        result["error"] = str(e)

    return result

# ─── DOWNLOAD ─────────────────────────────────────────────────────────────────

def download_update(
    url: str,
    on_progress: Optional[Callable[[int], None]] = None,
    on_done: Optional[Callable[[str], None]] = None,
    on_error: Optional[Callable[[str], None]] = None,
) -> None:
    """
    Télécharge le fichier de mise à jour dans un thread séparé.
    
    on_progress(percent: int)  — appelé pendant le téléchargement (0-100)
    on_done(tmp_path: str)     — appelé quand le fichier est prêt
    on_error(message: str)     — appelé en cas d'erreur
    """
    def _worker():
        try:
            tmp_dir  = tempfile.mkdtemp(prefix="nexus_update_")
            filename = url.split("/")[-1] or "NexusSpoofer_update.exe"
            tmp_path = os.path.join(tmp_dir, filename)

            req = urllib.request.Request(
                url,
                headers={"User-Agent": "NexusSpoofer-Updater/1.0"}
            )

            with urllib.request.urlopen(req, timeout=60) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                chunk_size = 65536  # 64 KB

                with open(tmp_path, "wb") as f:
                    while True:
                        chunk = resp.read(chunk_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0 and on_progress:
                            on_progress(int(downloaded / total * 100))

            if on_progress:
                on_progress(100)
            if on_done:
                on_done(tmp_path)

        except Exception as e:
            if on_error:
                on_error(str(e))

    threading.Thread(target=_worker, daemon=True).start()

# ─── APPLY ────────────────────────────────────────────────────────────────────

def apply_update(new_exe_path: str) -> None:
    """
    Remplace l'exécutable courant par le nouveau et relance l'application.
    Utilise un script batch temporaire pour contourner le verrou Windows sur l'exe en cours.
    """
    current_exe = sys.executable if getattr(sys, "frozen", False) else None

    if current_exe is None:
        # Mode dev : on ne peut pas se remplacer soi-même, on ouvre juste le dossier
        os.startfile(os.path.dirname(new_exe_path))
        return

    bat_content = f"""@echo off
timeout /t 2 /nobreak >nul
move /y "{new_exe_path}" "{current_exe}"
start "" "{current_exe}"
del "%~f0"
"""
    bat_path = os.path.join(tempfile.gettempdir(), "nexus_update_apply.bat")
    with open(bat_path, "w") as f:
        f.write(bat_content)

    subprocess.Popen(
        ["cmd.exe", "/c", bat_path],
        creationflags=subprocess.CREATE_NO_WINDOW
    )
    sys.exit(0)

# ─── ASYNC CHECK (pour main.py) ───────────────────────────────────────────────

def check_async(callback: Callable[[dict], None]) -> None:
    """Lance check_for_update() en arrière-plan et appelle callback(result)."""
    threading.Thread(
        target=lambda: callback(check_for_update()),
        daemon=True
    ).start()
