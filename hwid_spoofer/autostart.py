"""
Gestion de la tâche planifiée Windows pour le spoof automatique au boot.
"""
import subprocess, os, sys

TASK_NAME   = "NexusSpoofAutostart"
PYTHON_EXE  = sys.executable


def is_installed() -> bool:
    result = subprocess.run(
        f'schtasks /Query /TN "{TASK_NAME}"',
        shell=True, capture_output=True)
    return result.returncode == 0


def install() -> tuple[bool, str]:
    """Crée une tâche planifiée qui lance silent_spoof.py au démarrage (SYSTEM, highest privileges)."""
    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <BootTrigger>
      <Enabled>true</Enabled>
      <Delay>PT10S</Delay>
    </BootTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>S-1-5-18</UserId>
      <RunLevel>HighestAvailable</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <Hidden>true</Hidden>
    <ExecutionTimeLimit>PT2M</ExecutionTimeLimit>
    <Priority>4</Priority>
  </Settings>
  <Actions>
    <Exec>
      <Command>{PYTHON_EXE}</Command>
      <Arguments>--silent</Arguments>
    </Exec>
  </Actions>
</Task>"""

    # Écrire le XML dans un fichier temp
    xml_path = os.path.join(os.environ.get("TEMP", "."), "nexus_task.xml")
    with open(xml_path, "w", encoding="utf-16") as f:
        f.write(xml)

    result = subprocess.run(
        f'schtasks /Create /TN "{TASK_NAME}" /XML "{xml_path}" /F',
        shell=True, capture_output=True, text=True)

    try: os.unlink(xml_path)
    except: pass

    if result.returncode == 0:
        return True, "Autostart installed. Spoof will run 10s after each boot."
    return False, f"Failed: {result.stderr.strip() or result.stdout.strip()}"


def uninstall() -> tuple[bool, str]:
    result = subprocess.run(
        f'schtasks /Delete /TN "{TASK_NAME}" /F',
        shell=True, capture_output=True, text=True)
    if result.returncode == 0:
        return True, "Autostart removed."
    return False, f"Failed: {result.stderr.strip()}"
