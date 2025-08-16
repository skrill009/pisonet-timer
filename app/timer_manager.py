import os
import json
from PyQt5.QtCore import QTime, QTimer

class TimerManager:
    def __init__(self, initial_minutes=30, state_path=None):
        self.state_path = state_path or os.path.join(os.path.dirname(__file__), '../data/state.json')
        self.remaining_time = QTime(0, initial_minutes, 0)
        self.coin_count = 0
        self.timer = QTimer()
        self.timer.timeout.connect(self._tick)
        self.callbacks = []  # Functions to call on timer update
        self.load_state()

    def start(self):
        self.timer.start(1000)

    def stop(self):
        self.timer.stop()

    def reset(self, minutes=30):
        self.remaining_time = QTime(0, minutes, 0)
        self.coin_count = 0
        self.save_state()
        self._notify()

    def add_coin(self, value=1):
        self.coin_count += value
        self.save_state()
        self._notify()

    def get_time_str(self):
        return self.remaining_time.toString("hh:mm:ss")

    def get_coin_count(self):
        return self.coin_count

    def register_callback(self, func):
        self.callbacks.append(func)

    def _tick(self):
        self.remaining_time = self.remaining_time.addSecs(-1)
        self.save_state()
        self._notify()

    def _notify(self):
        for func in self.callbacks:
            func(self.get_time_str())

    def save_state(self):
        state = {
            "remaining_time": self.remaining_time.toString("hh:mm:ss"),
            "coin_count": self.coin_count
        }
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, "w") as f:
            json.dump(state, f)

    def load_state(self):
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r") as f:
                    state = json.load(f)
                time_str = state.get("remaining_time", "00:30:00")
                h, m, s = map(int, time_str.split(":"))
                self.remaining_time = QTime(h, m, s)
                self.coin_count = state.get("coin_count", 0)
            except Exception:
                self.remaining_time = QTime(0, 30, 0)
                self.coin_count = 0
        else:
            self.remaining_time = QTime(0, 30, 0)
            self.coin_count = 0