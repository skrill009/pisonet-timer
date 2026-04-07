"""
Registers the watchdog as a Windows startup task that runs as Administrator.

Run this ONCE as Administrator:
    python install_startup.py

To remove:
    python install_startup.py --uninstall
"""
import sys, os, subprocess, ctypes

TASK_NAME = "CafeTimerWatchdog"
ROOT      = os.path.dirname(os.path.abspath(__file__))
PYTHON    = sys.executable
WATCHDOG  = os.path.join(ROOT, "watchdog.py")

def _is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def _elevate():
    params = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    sys.exit(0)

def install():
    # Build the schtasks command:
    # - Run at system startup
    # - Run as SYSTEM (highest privilege, no UAC prompt, always runs)
    # - Run whether user is logged on or not
    cmd = [
        "schtasks", "/Create", "/F",
        "/TN",  TASK_NAME,
        "/TR",  f'"{PYTHON}" "{WATCHDOG}"',
        "/SC",  "ONSTART",
        "/RU",  "SYSTEM",
        "/RL",  "HIGHEST",
        "/DELAY", "0001:00",   # 1-minute delay after boot so desktop is ready
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"[OK] Task '{TASK_NAME}' registered. Watchdog will start on next boot.")
        print(f"     Python : {PYTHON}")
        print(f"     Script : {WATCHDOG}")
    else:
        print(f"[ERROR] schtasks failed:\n{result.stderr}")

def uninstall():
    cmd = ["schtasks", "/Delete", "/F", "/TN", TASK_NAME]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"[OK] Task '{TASK_NAME}' removed.")
    else:
        print(f"[ERROR] {result.stderr}")

if __name__ == "__main__":
    if not _is_admin():
        _elevate()

    if "--uninstall" in sys.argv:
        uninstall()
    else:
        install()
