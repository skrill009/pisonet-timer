"""
Child app entry point — runs on each cafe PC.
"""
import sys, os, ctypes, subprocess
try:
    import winreg
except ImportError:
    winreg = None
from PyQt5.QtWidgets import QApplication, QMessageBox
from PyQt5.QtCore import Qt


def _msg(title: str, text: str):
    """Show an always-on-top information popup."""
    box = QMessageBox()
    box.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
    box.setWindowTitle(title)
    box.setText(text)
    box.exec_()

from child import config as cfg_module
from child.timer_manager import TimerManager
from child.server import ChildServer
from child.serial_listener import SerialListener
from child.heartbeat_client import HeartbeatClient
from child.ui.overlay_window import FullscreenOverlay, DraggableTimer, LoginDialog
from shared.db import (
    init_db, log_activity, start_session, end_session,
    save_user_time, consume_user_time, DB_PATH
)

# Path to the clean-stop sentinel file.
# Watchdog checks this: if present, the app was stopped intentionally → don't restart.
STOP_FLAG = os.path.join(os.path.dirname(__file__), '..', 'data', 'stop.flag')
REG_FLAG  = os.path.join(os.path.dirname(__file__), '..', 'data', 'watchdog_registered.flag')
WATCHDOG  = os.path.join(os.path.dirname(__file__), '..', 'watchdog.py')


def _sync_user_time_to_parent(parent_ip: str, parent_port: int, username: str, seconds: int, pc_name: str):
    if not parent_ip or seconds < 0 or not username:
        return
    try:
        from shared.protocol import encode, CMD_SAVE_USER
        import socket
        msg = {"cmd": CMD_SAVE_USER, "username": username, "seconds": seconds, "pc_name": pc_name}
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(3)
            s.connect((parent_ip, int(parent_port)))
            s.sendall(encode(msg))
    except Exception:
        pass


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
    
    # Set discrete process name for Task Manager obfuscation
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW("Windows Service Host")
        except Exception:
            pass
    
    init_db()

    config   = cfg_module.load()
    pc_name  = config["pc_name"]
    app_name = config.get("app_name", "Grefin Timer")
    db_path  = DB_PATH

    # Apply Windows policies and startup registration when settings are loaded
    _configure_system_policies(config)
    _configure_startup_registration(config)

    # ── Timer manager ────────────────────────────────────────────
    tm = TimerManager(pc_name, seconds_per_coin=config["coin_map"].get("1", 1800))

    # Wire periodic DB-save callbacks so every 30 s the user's time is persisted
    tm._db_save_cb = save_user_time
    tm._log_cb     = log_activity
    tm.set_voice_file(config.get("voice_file_30s", ""))
    
    # Configure schedule settings
    warning_time_str = config.get("warning_time", "30:00")
    try:
        warning_minutes = int(warning_time_str.split(":")[0])
    except Exception:
        warning_minutes = 30
    
    tm.set_schedule_config(
        enabled=config.get("schedule_enabled", False),
        opening_hours=config.get("opening_hours", "09:00"),
        closing_hours=config.get("closing_hours", "23:00"),
        warning_minutes=warning_minutes,
        warning_message=config.get("warning_message", "⚠ Shop is closing soon!"),
        closing_message=config.get("closing_message", "Sorry, we are now closed!"),
        closing_logo_path=config.get("closing_logo_path", "")
    )

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
        app_name         = app_name,
        logo_path        = config.get("logo_path", ""),
    )
    draggable = DraggableTimer(pc_name, config=config, app_name=app_name)

    if config.get("animation_path"):
        overlay.set_animation(config["animation_path"])

    # ── Serial listener ──────────────────────────────────────────
    serial = SerialListener(
        config["com_port"],
        config.get("baud_rate", 9600),
        mode=config.get("com_mode", "Auto")
    )
    
    # Set timer manager reference for shop status checks
    overlay.set_timer_manager(tm)
    serial.set_timer_manager(tm)
    
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

    def on_coin_rejected(warning_msg: str):
        """Handle coin rejection when shop is closed."""
        log_activity(pc_name, "COIN_REJECTED", f"reason={warning_msg}")
        overlay.show_schedule_warning(warning_msg)
        draggable.show_schedule_warning(warning_msg)

    serial.coin_inserted.connect(on_coin_serial)
    serial.coin_rejected.connect(on_coin_rejected)

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
        tm.username = ""
        tm.save_state()
        current_user[0] = None
        draggable.stop_blink()
        draggable.hide()
        overlay.show_logged_out()
        overlay.show_and_lock()

    tm.tick_signal.connect(on_tick)
    tm.expired_signal.connect(on_expired)
    tm.coin_signal.connect(on_coin)
    
    # ── Schedule warning signals ─────────────────────────────────
    def on_schedule_warning(message: str):
        overlay.show_schedule_warning(message)
        draggable.show_schedule_warning(message)
    
    tm.schedule_warning_signal.connect(on_schedule_warning)

    # ── Shop closed signals ──────────────────────────────────────
    def on_shop_closed(
        closing_message: str,
        closing_logo_path: str,
        username_before: str,
        remaining_before: int,
        coins_before: int,
    ):
        log_activity(pc_name, "SHOP_CLOSED", f"closing_message={closing_message}")
        if username_before and remaining_before > 0:
            _sync_user_time_to_parent(
                config.get("parent_ip", ""),
                config.get("parent_port", 9100),
                username_before,
                remaining_before,
                pc_name,
            )
        if session_id[0] is not None:
            amount = coins_before * (config["coin_map"].get("1", 1800) / 1800)
            end_session(session_id[0], 0, coins_before, amount)
            session_id[0] = None
        current_user[0] = None
        draggable.stop_blink()
        draggable.hide()
        draggable.update_status(0, "")
        overlay.show_logged_out()
        overlay._on_shop_closed(closing_message, closing_logo_path)
        overlay.set_com_closing_message(closing_message)
        overlay.show_and_lock()

    tm.shop_closed_signal.connect(on_shop_closed)

    # ── Login from overlay ───────────────────────────────────────
    def on_login_success(username: str, seconds: int):
        current_user[0] = username
        tm.username = username
        tm.save_state()
        overlay.show_logged_in(username)
        log_activity(pc_name, "USER_LOGIN", f"username={username}, loaded_seconds={seconds}")
        # Add the user's saved bank on top of any time already on the timer
        # (covers the case: guest has 5 min running → logs in → gets their 22 min added)
        if seconds > 0:
            tm.add_time(seconds)
        if session_id[0] is None and tm.remaining > 0:
            session_id[0] = start_session(pc_name, username)
        if tm.remaining > 0:
            _show_session()
        else:
            _msg("Welcome", f"Welcome, {username}!\nInsert a coin to start your session.")

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

        # End DB session record
        if session_id[0] is not None:
            end_session(session_id[0], 0, tm.coins,
                        tm.coins * (config["coin_map"].get("1", 1800) / 1800))
            session_id[0] = None

        # Clear timer state
        tm.username = ""
        tm.set_time(0)
        tm.coins = 0
        tm.active = False
        tm.save_state()
        current_user[0] = None

        # Hide everything — only the settings dialog remains visible
        draggable.stop_blink()
        draggable.hide()
        overlay.show_logged_out()
        overlay.hide_overlay()

    def on_admin_reset():
        log_activity(pc_name, "ADMIN_RESET_TIMER")
        tm.username = ""
        tm.set_time(0)
        tm.coins = 0
        tm.active = False
        tm._timer.stop()
        tm._beep_player.stop()
        tm._voice_player.stop()
        tm.save_state()
        if session_id[0] is not None:
            end_session(session_id[0], 0, 0, 0)
            session_id[0] = None
        current_user[0] = None
        draggable.stop_blink()
        draggable.hide()
        overlay.show_logged_out()
        overlay.show_and_lock()

    overlay.timer_add_time.connect(on_admin_add_time)
    overlay.timer_stop.connect(on_admin_stop)
    overlay.timer_reset.connect(on_admin_reset)

    # ── Run Timer from admin modal ────────────────────────────────
    def on_admin_run_timer():
        # Remove stop flag so watchdog knows the app is running intentionally
        if os.path.exists(STOP_FLAG):
            try:
                os.remove(STOP_FLAG)
            except Exception:
                pass

        if tm.active and tm.remaining > 0:
            # Time is still on the clock — resume the session
            if current_user[0]:
                overlay.show_logged_in(current_user[0])
            _show_session()
        else:
            # No time remaining — show the overlay screen so user can insert coin / log in
            overlay.show_and_lock()

    overlay.timer_run.connect(on_admin_run_timer)

    # ── Show session (hide overlay, show draggable) ───────────────
    def _show_session():
        overlay.hide_overlay()
        draggable.update_time(tm.time_str())
        draggable.update_status(tm.coins, current_user[0] or "")
        draggable.show()

    # ── Parent commands ──────────────────────────────────────────
    def handle_command(msg):
        from shared.protocol import CMD_ADD_TIME, CMD_SET_TIME, CMD_END_SESSION, CMD_SHUTDOWN, CMD_SEND_MESSAGE, CMD_SET_SCHEDULE
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
            _msg(title, message)
        elif cmd == CMD_SET_SCHEDULE:
            # Update schedule configuration from parent
            tm.set_schedule_config(
                enabled=msg.get("enabled", False),
                opening_hours=msg.get("opening_hours", "09:00"),
                closing_hours=msg.get("closing_hours", "23:00"),
                warning_minutes=msg.get("warning_minutes", 30),
                warning_message=msg.get("warning_message", "⚠ Shop is closing soon!"),
                closing_message=msg.get("closing_message", "Sorry, we are now closed!"),
                closing_logo_path=msg.get("closing_logo_path", "")
            )
            log_activity(pc_name, "ADMIN_SCHEDULE_UPDATE", f"enabled={msg.get('enabled')}")

    server.command_received.connect(handle_command)

    # ── Settings saved (from overlay admin button) ───────────────
    def on_settings_saved(new_cfg: dict):
        config.update(new_cfg)
        cfg_module.save(config)
        _configure_system_policies(config)
        _configure_startup_registration(config)
        tm.seconds_per_coin = config["coin_map"].get("1", 1800)
        tm.set_voice_file(config.get("voice_file_30s", ""))
        
        # Update schedule configuration
        warning_time_str = config.get("warning_time", "30:00")
        try:
            warning_minutes = int(warning_time_str.split(":")[0])
        except Exception:
            warning_minutes = 30
        
        tm.set_schedule_config(
            enabled=config.get("schedule_enabled", False),
            opening_hours=config.get("opening_hours", "09:00"),
            closing_hours=config.get("closing_hours", "23:00"),
            warning_minutes=warning_minutes,
            warning_message=config.get("warning_message", "⚠ Shop is closing soon!"),
            closing_message=config.get("closing_message", "Sorry, we are now closed!"),
            closing_logo_path=config.get("closing_logo_path", "")
        )
        
        serial.port = config["com_port"]
        draggable._config = config
        draggable.apply_timer_config(config)

    overlay.settings_saved.connect(on_settings_saved)

    # ── Admin button on draggable timer ──────────────────────────
    def open_settings_from_draggable():
        overlay._on_admin_clicked()

    draggable.settings_requested.connect(open_settings_from_draggable)

    def _save_session_time_and_sync(username: str):
        if not username or tm.remaining <= 0:
            return
        save_user_time(username, tm.remaining, pc_name, db_path)
        _sync_user_time_to_parent(
            config.get("parent_ip", ""),
            config.get("parent_port", 9100),
            username,
            tm.remaining,
            pc_name,
        )
        log_activity(
            pc_name, "USER_TIME_SAVED",
            f"username={username}, seconds={tm.remaining}, time={tm.time_str()}",
        )

    def on_save_time_requested():
        if current_user[0] and tm.remaining > 0:
            _save_session_time_and_sync(current_user[0])
            # Reset timer state
            tm.username = ""
            tm.set_time(0)
            tm.coins = 0
            tm.active = False
            tm.save_state()
            if session_id[0] is not None:
                end_session(session_id[0], 0, 0, 0)
                session_id[0] = None
            current_user[0] = None
            draggable.stop_blink()
            draggable.hide()
            overlay.show_logged_out()
            msg = QMessageBox()
            msg.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
            msg.setWindowTitle("Time Saved")
            msg.setText("Time saved successfully!\nYou can continue your session later by logging in.")
            msg.exec_()
            overlay.show_and_lock()
            return
        dlg = LoginDialog(
            db_path, pc_name,
            config.get("parent_ip", "") if not config.get("standalone") else "",
            config.get("parent_port", 9100),
        )

        def after_login(username: str, seconds: int):
            on_login_success(username, seconds)
            if current_user[0] and tm.remaining > 0:
                _save_session_time_and_sync(current_user[0])
                tm.username = ""
                tm.set_time(0)
                tm.coins = 0
                tm.active = False
                tm.save_state()
                if session_id[0] is not None:
                    end_session(session_id[0], 0, 0, 0)
                    session_id[0] = None
                current_user[0] = None
                draggable.stop_blink()
                draggable.hide()
                overlay.show_logged_out()
                msg = QMessageBox()
                msg.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
                msg.setWindowTitle("Time Saved")
                msg.setText("Time saved! Log in again to continue your session.")
                msg.exec_()
                overlay.show_and_lock()

        dlg.login_success.connect(after_login)
        dlg.exec_()

    draggable.save_time_requested.connect(on_save_time_requested)

    # ── Logout handler ───────────────────────────────────────────
    def on_logout():
        if current_user[0] and tm.remaining > 0:
            # Save remaining time additively to the user's bank
            save_user_time(current_user[0], tm.remaining, pc_name, db_path)
            _sync_user_time_to_parent(
                config.get("parent_ip", ""),
                config.get("parent_port", 9100),
                current_user[0],
                tm.remaining,
                pc_name,
            )
            log_activity(pc_name, "USER_LOGOUT",
                         f"username={current_user[0]}, saved_seconds={tm.remaining}")
        # End the DB session record
        if session_id[0] is not None:
            coins  = tm.coins
            amount = coins * (config["coin_map"].get("1", 1800) / 1800)
            end_session(session_id[0], 0, coins, amount)
            session_id[0] = None
        # Clear timer state so the clock stops
        tm.username = ""
        tm.set_time(0)
        tm.coins = 0
        tm.active = False
        tm.save_state()
        current_user[0] = None
        draggable.stop_blink()
        draggable.hide()
        overlay.show_logged_out()
        overlay.show_and_lock()

    overlay.logout_requested.connect(on_logout)

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
            # Logged-in user had session — save their time, clear timer, show overlay
            log_activity(pc_name, "SESSION_RESTORED_TO_DB",
                         f"username={current_user[0]}, remaining={tm.time_str()}")
            save_user_time(current_user[0], tm.remaining, pc_name, db_path)
            tm.username = ""
            tm.set_time(0)
            tm.coins = 0
            tm.active = False
            tm.save_state()
            current_user[0] = None
            overlay.show_and_lock()
        else:
            # Guest session — restore normally
            log_activity(pc_name, "SESSION_RESTORED", f"remaining={tm.time_str()}")
            draggable.update_time(tm.time_str())
            draggable.update_status(tm.coins, "")
            draggable.show()
    else:
        overlay.show_and_lock()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
