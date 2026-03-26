"""
Watchdog for the child timer app.

- Keeps the child app running at all times.
- If the child crashes repeatedly (REBOOT_AFTER_FAILURES times), reboots the PC.
- Only stops when data/stop.flag exists (written by the admin Stop button).
- Auto-registers itself in Task Scheduler on first run as Administrator.
"""
import sys, os, time, subprocess, ctypes, json
from datetime import datetime

# ── paths ─────────────────────────────────────────────────────────────────────
ROOT      = os.path.dirname(os.path.abspath(__file__))
PYTHON    = sys.executable
CHILD     = os.path.join(ROOT, "run_child.py")
STOP_FLAG = os.path.join(ROOT, "data", "stop.flag")
LOG_FILE  = os.path.join(ROOT, "data", "watchdog.log")
REG_FLAG  = os.path.join(ROOT, "data", "watchdog_registered.flag")
CONFIG_PATH = os.path.join(ROOT, "data", "child_config.json")

TASK_NAME            = "CafeTimerWatchdog"
RESTART_DELAY        = 5    # seconds between restart attempts
REBOOT_AFTER_FAILURES = 5   # reboot PC after this many consecutive crashes

# ── helpers ───────────────────────────────────────────────────────────────────
def _log(msg: str):
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n"
    print(line, end="")
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass

def _is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        return False


def _load_config() -> dict:
    try:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}


def _dev_mode() -> bool:
    env_val = os.getenv("PISONET_TIMER_DEV_MODE", "0").lower()
    if env_val in ("1", "true", "yes", "on"):
        return True
    return bool(_load_config().get("dev_mode", False))


def _elevate_self():
    """Re-launch this script as Administrator via UAC prompt."""
    params = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", PYTHON, params, None, 1)
    sys.exit(0)

def _task_exists() -> bool:
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", TASK_NAME],
        capture_output=True, text=True
    )
    return result.returncode == 0


def _unregister_task():
    try:
        subprocess.run(["schtasks", "/Delete", "/F", "/TN", TASK_NAME], capture_output=True, text=True)
        _log(f"Task '{TASK_NAME}' removed from Task Scheduler.")
    except Exception as e:
        _log(f"Failed to unregister task: {e}")


def _register_task():
    """Register watchdog in Task Scheduler to run at startup as SYSTEM."""
    if _dev_mode():
        _log("Dev mode detected — skipping Task Scheduler registration and reboot behavior.")
        return False

    cfg = _load_config()
    if not cfg.get("launch_on_startup", True):
        _log("launch_on_startup disabled in config; skipping watchdog Task Scheduler registration.")
        if _task_exists():
            _unregister_task()
        return False

    if _task_exists():
        _log(f"Task '{TASK_NAME}' already registered.")
        return True

    cmd = [
        "schtasks", "/Create", "/F",
        "/TN",    TASK_NAME,
        "/TR",    f'"{PYTHON}" "{os.path.abspath(__file__)}"',
        "/SC",    "ONSTART",
        "/RU",    "SYSTEM",
        "/RL",    "HIGHEST",
        "/DELAY", "0001:00",   # 1-minute delay after boot
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        _log(f"Task '{TASK_NAME}' registered in Task Scheduler.")
        # Write flag so we don't try to register again
        os.makedirs(os.path.dirname(REG_FLAG), exist_ok=True)
        open(REG_FLAG, "w").close()
        return True
    else:
        _log(f"Failed to register task: {result.stderr.strip()}")
        return False

def _reboot() -> bool:
    cfg = _load_config()
    if not cfg.get("watchdog_reboot_enabled", True):
        _log("Watchdog reboot disabled in config; skipping reboot.")
        return False

    if _dev_mode():
        _log("Dev mode active — reboot suppressed after consecutive failures.")
        return False

    _log("Too many consecutive failures — rebooting PC.")
    if sys.platform == "win32":
        subprocess.Popen(["shutdown", "/r", "/t", "10",
                          "/c", "CafeTimer watchdog: restarting PC after repeated app failures."])
    else:
        subprocess.Popen(["shutdown", "-r", "now"])
    return True

# ── main loop ─────────────────────────────────────────────────────────────────
def run():
    if sys.platform == "win32" and not _is_admin():
        _elevate_self()

    _log("Watchdog started.")

    if _dev_mode():
        _log("Dev mode enabled. no reboot or startup registration on this machine.")
    # Auto-register in Task Scheduler if not already done
    _register_task()

    # Clear any leftover stop flag from a previous intentional stop
    if os.path.exists(STOP_FLAG):
        os.remove(STOP_FLAG)
        _log("Cleared previous stop flag.")

    proc             = None
    failure_count    = 0
    last_start_time  = None

    while True:
        # Honour intentional stop
        if os.path.exists(STOP_FLAG):
            _log("Stop flag detected — watchdog exiting.")
            break

        if proc is None or proc.poll() is not None:
            exit_code = proc.poll() if proc else None

            if exit_code is not None:
                _log(f"Child exited with code {exit_code}.")

                if os.path.exists(STOP_FLAG):
                    _log("Stop flag detected after exit — watchdog exiting.")
                    break

                # Count as a failure only if it died quickly (< 30 s)
                if last_start_time and (time.time() - last_start_time) < 30:
                    failure_count += 1
                    _log(f"Quick crash detected. Consecutive failures: {failure_count}/{REBOOT_AFTER_FAILURES}")
                else:
                    failure_count = 0   # ran long enough — reset counter

                if failure_count >= REBOOT_AFTER_FAILURES:
                    if _reboot():
                        # Give reboot command time to execute; watchdog exits
                        time.sleep(30)
                        break
                    _log("Continuing in watchdog loop (dev mode) after suppressed reboot.")
                    failure_count = 0
                    time.sleep(RESTART_DELAY)
                    continue

                _log(f"Restarting in {RESTART_DELAY}s...")
                time.sleep(RESTART_DELAY)

            _log("Launching child app...")
            last_start_time = time.time()
            proc = subprocess.Popen(
                [PYTHON, CHILD],
                cwd=ROOT,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            _log(f"Child PID: {proc.pid}")

        time.sleep(1)

    _log("Watchdog stopped.")

if __name__ == "__main__":
    run()
