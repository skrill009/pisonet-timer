"""
Child timer manager — handles countdown, coin pulses, session tracking.
"""
import os, json
from datetime import datetime, time, timedelta
from PyQt5.QtCore import QTimer, QObject, pyqtSignal
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtCore import QUrl

STATE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'state.json')

class TimerManager(QObject):
    tick_signal   = pyqtSignal(str)   # emits time string every second
    expired_signal = pyqtSignal()     # emits when timer hits 00:00:00
    coin_signal   = pyqtSignal(int)   # emits total coins after insert
    schedule_warning_signal = pyqtSignal(str)  # emits warning message when schedule warning triggered
    # message, logo path, username before clear ("" if guest), remaining sec, coins
    shop_closed_signal = pyqtSignal(str, str, str, int, int)

    def __init__(self, pc_name: str, seconds_per_coin: int = 1800, parent=None):
        super().__init__(parent)
        self.pc_name = pc_name
        self.seconds_per_coin = seconds_per_coin
        self.remaining = 0
        self.coins = 0
        self.active = False
        self.username = ""          # current logged-in user (empty = guest)
        self._db_save_cb = None     # optional callable(username, remaining, pc_name)
        self._log_cb = None         # optional callable(pc_name, event, detail)
        self._tick_count = 0        # used to throttle DB saves to every 30s
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._beep_player = QMediaPlayer(self)
        self._voice_player = QMediaPlayer(self)
        self._beep_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'beep.mp3')
        self._voice_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'no_more_time.wav')  # default
        self._beep_playing = False
        self._voice_played = False
        
        # Schedule settings
        self._schedule_enabled = False
        self._opening_hours = "09:00"
        self._closing_hours = "23:00"
        self._warning_minutes = 30
        self._warning_message = "⚠ Shop is closing soon!"
        self._closing_message = "Sorry, we are now closed!"
        self._closing_logo_path = os.path.join(os.path.dirname(__file__), '..', 'assets', 'closing_logo.jpg')  # default
        self._schedule_warning_shown = False  # Track if we've already shown this warning
        self._shop_closed_processed = False  # Track if we've already processed shop closing
        
        self.load_state()

    # ── Schedule configuration ───────────────────────────────────
    def set_schedule_config(self, enabled: bool, opening_hours: str, closing_hours: str, 
                           warning_minutes: int, warning_message: str, closing_message: str = "", 
                           closing_logo_path: str = ""):
        """Update schedule configuration."""
        self._schedule_enabled = enabled
        self._opening_hours = opening_hours
        self._closing_hours = closing_hours
        self._warning_minutes = warning_minutes
        self._warning_message = warning_message
        self._closing_message = closing_message
        self._closing_logo_path = closing_logo_path
        self._schedule_warning_shown = False  # Reset when config changes
        self._shop_closed_processed = False  # Reset when config changes

    def _parse_time(self, time_str: str) -> time:
        """Parse time string in HH:MM format."""
        try:
            parts = time_str.split(":")
            return time(int(parts[0]), int(parts[1]))
        except Exception:
            return time(9, 0)  # Default to 09:00

    def _check_schedule_warning(self) -> bool:
        """Check if we should show a schedule closing warning."""
        if not self._schedule_enabled:
            self._schedule_warning_shown = False  # Reset when schedule is disabled
            return False

        now = datetime.now().time()
        closing_time = self._parse_time(self._closing_hours)
        opening_time = self._parse_time(self._opening_hours)

        closing_dt = datetime.combine(datetime.today(), closing_time)
        warning_dt = closing_dt - timedelta(minutes=self._warning_minutes)
        warning_time = warning_dt.time()

        # Check if current time is between warning time and closing time
        # and we haven't already shown the warning
        if warning_time <= now < closing_time and not self._schedule_warning_shown:
            self._schedule_warning_shown = True
            return True

        # Reset the warning flag after closing time (for next day)
        if now < opening_time or now >= closing_time:
            self._schedule_warning_shown = False

        return False

    def _check_shop_closed(self) -> bool:
        """Check if the shop is currently closed (outside opening/closing hours)."""
        if not self._schedule_enabled:
            self._shop_closed_processed = False  # Reset when schedule is disabled
            return False

        now = datetime.now().time()
        opening_time = self._parse_time(self._opening_hours)
        closing_time = self._parse_time(self._closing_hours)

        # Check if current time is outside opening hours (shop is closed)
        is_closed = now < opening_time or now >= closing_time
        
        # If shop is closed but we haven't processed it yet, and timer is active
        if is_closed and not self._shop_closed_processed and self.active and self.remaining > 0:
            self._shop_closed_processed = True
            return True
        
        # Reset the flag when shop is open
        if not is_closed:
            self._shop_closed_processed = False

        return False

    def _handle_shop_closure(self):
        """Save logged-in time to DB, log guest unused time, clear session, emit signal."""
        user_before = (self.username or "").strip()
        rem = self.remaining
        coins_before = self.coins

        if user_before:
            if self._db_save_cb:
                try:
                    self._db_save_cb(user_before, rem, self.pc_name)
                except Exception:
                    pass
        else:
            if self._log_cb:
                try:
                    self._log_cb(
                        self.pc_name,
                        "SHOP_CLOSED_UNUSED_TIME",
                        f"unused_time={self.time_str()}, remaining_seconds={rem}",
                    )
                except Exception:
                    pass

        self.remaining = 0
        self.coins = 0
        self.username = ""
        self.active = False
        self._timer.stop()
        self.save_state()
        self.shop_closed_signal.emit(
            self._closing_message,
            self._closing_logo_path,
            user_before,
            rem,
            coins_before,
        )

    def is_shop_open(self) -> bool:
        """Check if the shop is currently open (simple check, not tied to session state)."""
        if not self._schedule_enabled:
            return True  # If schedule is disabled, shop is always open
        
        now = datetime.now().time()
        opening_time = self._parse_time(self._opening_hours)
        closing_time = self._parse_time(self._closing_hours)
        
        # Shop is open if between opening and closing times
        return opening_time <= now < closing_time

    def get_closing_time_str(self) -> str:
        """Return the closing time as a formatted string."""
        return self._closing_hours

    def get_warning_message_with_time(self) -> str:
        """Return warning message with closing time included."""
        return f"Sorry we are now closing at {self.get_closing_time_str()}. Coinslot is locked."

    # ── public API ──────────────────────────────────────────────
    def add_time(self, seconds: int):
        self.remaining += seconds
        self.active = True
        self._voice_played = False  # reset for new session
        if not self._timer.isActive():
            self._timer.start(1000)
        self.save_state()
        self.tick_signal.emit(self.time_str())

    def set_time(self, seconds: int):
        self.remaining = seconds
        self.active = seconds > 0
        self._voice_played = False  # reset
        if self.active and not self._timer.isActive():
            self._timer.start(1000)
        elif not self.active:
            self._timer.stop()
        self.save_state()
        self.tick_signal.emit(self.time_str())

    def add_coin(self, pulses: int = 1):
        self.coins += pulses
        self.add_time(pulses * self.seconds_per_coin)
        self.coin_signal.emit(self.coins)

    def add_coin_seconds(self, seconds: int, pulses: int = 1):
        """Add time using explicit seconds (from coin_map) instead of seconds_per_coin."""
        self.coins += pulses
        self.add_time(seconds)
        self.coin_signal.emit(self.coins)

    def end_session(self):
        self.remaining = 0
        self.coins = 0
        self.active = False
        self._voice_played = False  # reset
        self._timer.stop()
        self.save_state()
        self.expired_signal.emit()

    def time_str(self) -> str:
        h = self.remaining // 3600
        m = (self.remaining % 3600) // 60
        s = self.remaining % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def status(self) -> dict:
        return {
            "pc_name": self.pc_name,
            "remaining": self.remaining,
            "active": self.active,
            "coins": self.coins,
            "time_str": self.time_str()
        }
    def set_voice_file(self, path: str):
        self._voice_path = path

    def _play_beep(self):
        if not self._beep_playing and os.path.exists(self._beep_path):
            self._beep_player.setMedia(QMediaContent(QUrl.fromLocalFile(self._beep_path)))
            self._beep_player.play()
            self._beep_playing = True
            self._beep_player.mediaStatusChanged.connect(self._on_beep_finished)

    def _on_beep_finished(self, status):
        if status == QMediaPlayer.EndOfMedia:
            self._beep_playing = False

    def _play_voice(self):
        if not self._voice_played and os.path.exists(self._voice_path):
            self._voice_player.setMedia(QMediaContent(QUrl.fromLocalFile(self._voice_path)))
            self._voice_player.play()
            self._voice_played = True
    # ── persistence ─────────────────────────────────────────────
    def save_state(self):
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        with open(STATE_PATH, "w") as f:
            json.dump({
                "remaining": self.remaining,
                "coins":     self.coins,
                "active":    self.active,
                "username":  self.username,
                "saved_at":  datetime.now().isoformat(),
            }, f)

    def load_state(self):
        if os.path.exists(STATE_PATH):
            try:
                with open(STATE_PATH) as f:
                    s = json.load(f)
                self.remaining = s.get("remaining", 0)
                self.coins     = s.get("coins", 0)
                self.active    = s.get("active", False)
                self.username  = s.get("username", "")
                if self.active and self.remaining > 0:
                    self._timer.start(1000)
            except Exception:
                pass

    # ── internal ────────────────────────────────────────────────
    def _tick(self):
        if self.remaining > 0:
            self.remaining -= 1
            self._tick_count += 1
            self.save_state()
            self.tick_signal.emit(self.time_str())

            # Check if shop is closed and stop session if needed
            if self._check_shop_closed():
                self._handle_shop_closure()
                return

            # Check for schedule warning
            if self._check_schedule_warning():
                self.schedule_warning_signal.emit(self.get_warning_message_with_time())

            # Play beep if <= 1 minute
            if self.remaining <= 60:
                self._play_beep()

            # Play voice at exactly 30 seconds
            if self.remaining == 30:
                self._play_voice()

            # Every 30 s: persist user time to DB and log current time
            if self._tick_count % 30 == 0:
                if self._db_save_cb and self.username:
                    try:
                        self._db_save_cb(self.username, self.remaining, self.pc_name)
                    except Exception:
                        pass
                if self._log_cb:
                    try:
                        self._log_cb(self.pc_name, "TIMER_TICK_SAVE",
                                     f"username={self.username or 'guest'}, "
                                     f"remaining={self.time_str()}")
                    except Exception:
                        pass

            if self.remaining == 0:
                self.active = False
                self._timer.stop()
                self.expired_signal.emit()
