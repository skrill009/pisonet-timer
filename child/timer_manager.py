"""
Child timer manager — handles countdown, coin pulses, session tracking.
"""
import os, json
from datetime import datetime
from PyQt5.QtCore import QTimer, QObject, pyqtSignal

STATE_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'state.json')

class TimerManager(QObject):
    tick_signal   = pyqtSignal(str)   # emits time string every second
    expired_signal = pyqtSignal()     # emits when timer hits 00:00:00
    coin_signal   = pyqtSignal(int)   # emits total coins after insert

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
        self.load_state()

    # ── public API ──────────────────────────────────────────────
    def add_time(self, seconds: int):
        self.remaining += seconds
        self.active = True
        if not self._timer.isActive():
            self._timer.start(1000)
        self.save_state()
        self.tick_signal.emit(self.time_str())

    def set_time(self, seconds: int):
        self.remaining = seconds
        self.active = seconds > 0
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
