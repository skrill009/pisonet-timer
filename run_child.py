"""
Launch the child (timer) app.
Auto-elevates to Administrator on Windows if not already running as admin.
The watchdog calls this directly, so elevation is handled here.
"""
import sys, os, ctypes

def _is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False

def _elevate():
    """Re-launch this script with UAC elevation."""
    script = os.path.abspath(__file__)
    params = f'"{script}"'
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
    sys.exit(0)

if sys.platform == "win32" and not _is_admin():
    _elevate()

# ── clear stop flag if we were restarted by watchdog (not by Stop button) ────
STOP_FLAG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "stop.flag")
# The watchdog already removes the flag before launching us, so nothing to do here.

from child.main import main
main()
