"""
Child app entry point — runs on each cafe PC.
"""
import sys, os, ctypes, subprocess
try:
    import winreg
except ImportError:
    winreg = None
from PyQt5.QtWidgets import QApplication, QMessageBox

from child import config as cfg_module
from child.timer_manager import TimerManager
from child.server import ChildServer
from child.serial_listener import SerialListener
from child.heartbeat_client import HeartbeatClient
from child.ui.overlay_window import FullscreenOverlay, DraggableTimer
from shared.db import (
    init_db, log_activity, start_session, end_session,
    save_user_time, consume_user_time, DB_PATH
)

# Path to the clean-stop sentinel file.
# Watchdog checks this: if present, the app was stopped intentionally → don't restart.
STOP_FLAG = os.path.join(os.path.dirname(__file__), '..', 'data', 'stop.flag')
REG_FLAG  = os.path.join(os.path.dirname(__file__), '..', 'data', 'watchdog_registered.flag')
WATCHDOG  = os.path.join(os.path.dirname(__file__), '..', 'watchdog.py')


def _set_registry_dword(path: str, name: str, value: int):
    if sys.platform != "win32" or winreg is None:
        return
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, path)
        if value is None:
            try:
                winreg.DeleteValue(key, name)
            except OSError:
                pass
        else:
            winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, value)
        winreg.CloseKey(key)
    except Exception:
        pass


def _configure_system_policies(cfg: dict):
    if sys.platform != "win32" or winreg is None:
        return

    # Task Manager hide/disable
    if cfg.get("disable_task_manager", False):
        _set_registry_dword(r"Software\Microsoft\Windows\CurrentVersion\Policies\System", "DisableTaskMgr", 1)
    else:
        _set_registry_dword(r"Software\Microsoft\Windows\CurrentVersion\Policies\System", "DisableTaskMgr", 0)

    # Task view hide + Win+Tab lock
    if cfg.get("disable_task_view", False):
        _set_registry_dword(r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ShowTaskViewButton", 0)
        _set_registry_dword(r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer", "NoWinKeys", 1)
    else:
        _set_registry_dword(r"Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ShowTaskViewButton", 1)
        _set_registry_dword(r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer", "NoWinKeys", 0)

    # Log off / sign out disable
    if cfg.get("disable_signout", False):
        _set_registry_dword(r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer", "NoLogoff", 1)
    else:
        _set_registry_dword(r"Software\Microsoft\Windows\CurrentVersion\Policies\Explorer", "NoLogoff", 0)


def _configure_startup_registration(cfg: dict):
    if sys.platform != "win32":
        return
    # Use existing install_startup utility; requires admin privileges
    install_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'install_startup.py')
    if cfg.get("launch_on_startup", False):
        try:
            subprocess.run([sys.executable, install_script], check=False)
        except Exception:
            pass
    else:
        try:
            subprocess.run([sys.executable, install_script, "--uninstall"], check=False)
        except Exception:
            pass


def _ensure_watchdog():
    """
    If running as Administrator and the watchdog task hasn't been registered yet,
    launch watchdog.py once so it self-registers in Task Scheduler.
    The watchdog will then manage the child app from that point on.
    """
    try:
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    except Exception:
        is_admin = False

    if not is_admin:
        return   # can't register without admin rights — skip silently

    if os.path.exists(REG_FLAG):
        return   # already registered

    # Check if task already exists in scheduler
    result = subprocess.run(
        ["schtasks", "/Query", "/TN", "CafeTimerWatchdog"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        # Task exists — just write the flag so we don't check again
        os.makedirs(os.path.dirname(REG_FLAG), exist_ok=True)
        open(REG_FLAG, "w").close()
        return

    # Launch watchdog once — it will register itself and then start watching
    python = sys.executable
    subprocess.Popen(
        [python, WATCHDOG],
        cwd=os.path.dirname(WATCHDOG),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )

def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    init_db()

    config   = cfg_module.load()
    pc_name  = config["pc_name"]
    db_path  = DB_PATH

    # Apply Windows policies and startup registration when settings are loaded
    _configure_system_policies(config)
    _configure_startup_registration(config)

    # ── Timer manager ────────────────────────────────────────────
    tm = TimerManager(pc_name, seconds_per_coin=config["coin_map"].get("1", 1800))

    # Wire periodic DB-save callbacks so every 30 s the user's time is persisted
    tm._db_save_cb = save_user_time
    tm._log_cb     = log_activity

    # ── TCP server ───────────────────────────────────────────────
    server = ChildServer(tm, port=config["server_port"])
    server.start()

    # ── Heartbeat client ─────────────────────────────────────────
    if not config.get("standalone", False) and config.get("parent_ip"):
        heartbeat = HeartbeatClient(
            pc_name=pc_name,
            parent_ip=config["parent_ip"],
            parent_port=config.get("parent_port", 9100),
            child_port=config["server_port"],
            status_callback=lambda: tm.status()
        )
        heartbeat.start()

    # ── UI ───────────────────────────────────────────────────────
    overlay = FullscreenOverlay(
        pc_name          = pc_name,
        shop_name        = config["shop_name"],
        admin_keyword    = config["admin_keyword"],
        shutdown_seconds = config["shutdown_countdown"],
        db_path          = db_path,
        parent_ip        = config["parent_ip"] if not config["standalone"] else "",
        parent_port      = config.get("parent_port", 9100),
        config           = config,
    )
    draggable = DraggableTimer(pc_name, config=config)

    if config.get("animation_path"):
        overlay.set_animation(config["animation_path"])

    # ── Serial listener ──────────────────────────────────────────
    serial = SerialListener(
        config["com_port"],
        config.get("baud_rate", 9600),
        mode=config.get("com_mode", "Auto")
    )
    serial.status_changed.connect(overlay.set_com_status)
    serial.status_changed.connect(draggable.set_com_status)
    serial.start()

    # ── Session state ────────────────────────────────────────────
    session_id   = [None]
    # Restore username from persisted state (covers blackout recovery)
    current_user = [tm.username if tm.username else None]

    # ── Coin serial → timer ──────────────────────────────────────
    def on_coin_serial(pulses: int):
        coin_map = config.get("coin_map", {"1": 1800})
        seconds  = coin_map.get(str(pulses), pulses * 1800)
        tm.add_coin_seconds(seconds, pulses)

    serial.coin_inserted.connect(on_coin_serial)

    # ── Timer signals ────────────────────────────────────────────
    def on_coin(coins: int):
        log_activity(pc_name, "COIN_INSERTED", f"total_coins={coins}")
        if session_id[0] is None:
            session_id[0] = start_session(pc_name, current_user[0] or "")
        draggable.update_status(coins, current_user[0] or "")
        _show_session()

    def on_tick(time_str: str):
        draggable.update_time(time_str)
        # Apply speed multiplier (extra ticks)
        speed = config.get("timer_speed", 1.0)
        if speed > 1.0:
            extra = int(speed) - 1
            for _ in range(extra):
                tm._tick()
        # Blink threshold
        if 0 < tm.remaining <= config.get("blink_threshold", 60):
            draggable.start_blink()

    def on_expired():
        log_activity(pc_name, "SESSION_EXPIRED")
        if session_id[0] is not None:
            coins  = tm.coins
            amount = coins * (config["coin_map"].get("1", 1800) / 1800)
            end_session(session_id[0], 0, coins, amount)
            session_id[0] = None
        current_user[0] = None
        draggable.stop_blink()
        draggable.hide()
        overlay.show_and_lock()

    tm.tick_signal.connect(on_tick)
    tm.expired_signal.connect(on_expired)
    tm.coin_signal.connect(on_coin)

    # ── Login from overlay ───────────────────────────────────────
    def on_login_success(username: str, seconds: int):
        current_user[0] = username
        tm.username = username          # persist username in state
        tm.save_state()
        log_activity(pc_name, "USER_LOGIN", f"username={username}, loaded_seconds={seconds}")
        if seconds > 0:
            tm.add_time(seconds)
            if session_id[0] is None:
                session_id[0] = start_session(pc_name, username)
            _show_session()
        else:
            QMessageBox.information(None, "Welcome",
                f"Welcome, {username}!\nInsert a coin to start your session.")

    overlay.login_success.connect(on_login_success)

    # ── Timer controls from settings modal ───────────────────────
    def on_admin_add_time(seconds: int):
        tm.add_time(seconds)
        log_activity(pc_name, "ADMIN_ADD_TIME", f"seconds={seconds}")
        _show_session()

    def on_admin_stop():
        log_activity(pc_name, "ADMIN_STOP_TIMER")
        # Write stop flag so watchdog knows this was intentional
        os.makedirs(os.path.dirname(STOP_FLAG), exist_ok=True)
        open(STOP_FLAG, "w").close()
        app.quit()

    def on_admin_reset():
        log_activity(pc_name, "ADMIN_RESET_TIMER")
        tm.username = ""
        tm.set_time(0)
        tm.coins = 0
        tm.active = False
        tm._timer.stop()
        tm.save_state()
        if session_id[0] is not None:
            end_session(session_id[0], 0, 0, 0)
            session_id[0] = None
        current_user[0] = None
        draggable.stop_blink()
        draggable.hide()
        overlay.show_and_lock()

    overlay.timer_add_time.connect(on_admin_add_time)
    overlay.timer_stop.connect(on_admin_stop)
    overlay.timer_reset.connect(on_admin_reset)

    # ── Show session (hide overlay, show draggable) ───────────────
    def _show_session():
        overlay.hide_overlay()
        draggable.update_time(tm.time_str())
        draggable.update_status(tm.coins, current_user[0] or "")
        draggable.show()

    # ── Parent commands ──────────────────────────────────────────
    def handle_command(msg):
        from shared.protocol import CMD_ADD_TIME, CMD_SET_TIME, CMD_END_SESSION, CMD_SHUTDOWN, CMD_SEND_MESSAGE
        cmd = msg.get("cmd")
        if cmd == CMD_ADD_TIME:
            tm.add_time(msg["seconds"])
            log_activity(pc_name, "ADMIN_ADD_TIME", f"seconds={msg['seconds']}")
            _show_session()
        elif cmd == CMD_SET_TIME:
            tm.set_time(msg["seconds"])
            log_activity(pc_name, "ADMIN_SET_TIME", f"seconds={msg['seconds']}")
            _show_session()
        elif cmd == CMD_END_SESSION:
            tm.end_session()
            log_activity(pc_name, "ADMIN_END_SESSION")
        elif cmd == CMD_SHUTDOWN:
            log_activity(pc_name, "REMOTE_SHUTDOWN")
            # Write stop flag and shutdown
            os.makedirs(os.path.dirname(STOP_FLAG), exist_ok=True)
            open(STOP_FLAG, "w").close()
            # Perform system shutdown
            if sys.platform == "win32":
                subprocess.run(["shutdown", "/s", "/t", "0"])
            else:
                subprocess.run(["shutdown", "-h", "now"])
        elif cmd == CMD_SEND_MESSAGE:
            title = msg.get("title", "Message from Admin")
            message = msg.get("message", "")
            log_activity(pc_name, "ADMIN_MESSAGE", f"title={title}, message={message}")
            # Show message dialog
            QMessageBox.information(None, title, message)

    server.command_received.connect(handle_command)

    # ── Settings saved (from overlay admin button) ───────────────
    def on_settings_saved(new_cfg: dict):
        config.update(new_cfg)
        cfg_module.save(config)
        _configure_system_policies(config)
        _configure_startup_registration(config)
        tm.seconds_per_coin = config["coin_map"].get("1", 1800)
        serial.port = config["com_port"]
        draggable._config = config   # keep password in sync
        from PyQt5.QtGui import QFont as _QFont
        draggable.time_label.setFont(
            _QFont("Segoe UI", config["timer_font_size"], _QFont.Bold))
        draggable.time_label.setStyleSheet(f"color:{config['timer_color']};")

    overlay.settings_saved.connect(on_settings_saved)

    # ── Admin button on draggable timer ──────────────────────────
    def open_settings_from_draggable():
        overlay._on_admin_clicked()

    draggable.settings_requested.connect(open_settings_from_draggable)

    # ── Save user time on session end (if logged in) ─────────────
    def save_time_for_user():
        if current_user[0] and tm.remaining > 0:
            save_user_time(current_user[0], tm.remaining, pc_name, db_path)
            log_activity(pc_name, "USER_TIME_SAVED",
                         f"username={current_user[0]}, seconds={tm.remaining}, "
                         f"time={tm.time_str()}")

    app.aboutToQuit.connect(save_time_for_user)

    # ── Initial state ────────────────────────────────────────────
    if tm.active and tm.remaining > 0:
        # Restored from state (blackout recovery)
        if current_user[0]:
            log_activity(pc_name, "SESSION_RESTORED",
                         f"username={current_user[0]}, remaining={tm.time_str()}")
        draggable.update_time(tm.time_str())
        draggable.update_status(tm.coins, current_user[0] or "")
        draggable.show()
    else:
        overlay.show_and_lock()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
