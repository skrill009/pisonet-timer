# app/main.py
import sys
from PyQt5.QtWidgets import QApplication
from app.ui.timer_window import OverlayTimerWindow
from app.timer_manager import TimerManager

def main():
    app = QApplication(sys.argv)

    timer_manager = TimerManager()

    # Pass None or a mock for serial_listener
    timer_window = OverlayTimerWindow(timer_manager, None)
    timer_window.show()

    # Connect timer updates to UI
    timer_manager.register_callback(timer_window.update_timer_display)

    timer_manager.start()

    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
