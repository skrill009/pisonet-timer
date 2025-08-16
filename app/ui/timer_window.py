# timer_window.py
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout, QApplication, QInputDialog, QMessageBox, QLineEdit
)
from PyQt5.QtCore import Qt, QTimer, QTime
from PyQt5.QtGui import QFont
from app.ui.settings_modal import SettingsModal

class MiniTimerWidget(QWidget):
    def __init__(self, time_str):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)

        self.label = QLabel(time_str)
        self.label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self.label.setStyleSheet("color: turquoise;")
        self.label.setAlignment(Qt.AlignCenter)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)
        self.setFixedSize(110, 32)

        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width() - self.width()) // 2, 2)

        self.blink_timer = QTimer(self)
        self.is_blinking = False
        self.blink_state = False

    def start_blinking(self):
        if not self.is_blinking:
            self.is_blinking = True
            self.blink_timer.timeout.connect(self.blink_label)
            self.blink_timer.start(500)

    def stop_blinking(self):
        if self.is_blinking:
            self.blink_timer.stop()
            self.label.setStyleSheet("color: turquoise;")
            self.is_blinking = False
            self.blink_state = False

    def blink_label(self):
        if self.blink_state:
            self.label.setStyleSheet("color: turquoise;")
        else:
            self.label.setStyleSheet("color: red;")
        self.blink_state = not self.blink_state

class OverlayTimerWindow(QWidget):
    def __init__(self, timer_manager, serial_listener):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.drag_position = None

        self.timer_manager = timer_manager
        self.serial_listener = serial_listener  # This will be None for now

        self.init_ui()
        self.mini_timer = None

        screen = QApplication.primaryScreen().availableGeometry()
        x = screen.width() - self.width() - 20
        y = screen.height() - self.height() - 10
        self.move(x, y)

        self.blink_timer = QTimer(self)
        self.is_blinking = False
        self.blink_state = False
        self.admin_password = "admin"  # Default password

    def init_ui(self):
        self.setStyleSheet("background-color: rgba(20, 20, 20, 180); border-radius: 10px;")
        self.label = QLabel(self.timer_manager.get_time_str())
        self.label.setFont(QFont("Segoe UI", 22, QFont.Bold))
        self.label.setStyleSheet("color: turquoise;")
        self.label.setAlignment(Qt.AlignCenter)

        # Status label (placeholder, updated by update_status)
        self.status_label = QLabel()
        self.status_label.setFont(QFont("Segoe UI", 10, QFont.Bold))
        self.status_label.setAlignment(Qt.AlignLeft)
        self.update_status()

        self.minimize_btn = QPushButton("🗕")
        self.settings_btn = QPushButton("⚙")
        self.save_btn = QPushButton("💾")

        for btn in [self.minimize_btn, self.settings_btn, self.save_btn]:
            btn.setFixedSize(32, 32)
            btn.setStyleSheet("background: transparent; color: turquoise; font-size: 20px;")

        self.minimize_btn.clicked.connect(self.minimize_to_taskbar)
        self.settings_btn.clicked.connect(self.open_settings)
        self.save_btn.clicked.connect(self.save_state)

        icon_layout = QHBoxLayout()
        icon_layout.addWidget(self.save_btn)
        icon_layout.addWidget(self.settings_btn)
        icon_layout.addWidget(self.minimize_btn)
        icon_layout.setAlignment(Qt.AlignRight)

        main_layout = QVBoxLayout()
        main_layout.addLayout(icon_layout)
        main_layout.addWidget(self.label)
        main_layout.addWidget(self.status_label)
        main_layout.setContentsMargins(8, 8, 8, 8)

        self.setLayout(main_layout)
        self.setFixedSize(220, 120)

    def update_timer_display(self, time_str):
        self.label.setText(time_str)
        if self.mini_timer:
            self.mini_timer.label.setText(time_str)

    def update_status(self):
        # Mock status for now
        com_status = "Ready"  # Mock value
        coins = self.timer_manager.get_coin_count()
        self.status_label.setText(f"STATUS: {com_status} | Coins: {coins}")

    def start_blinking(self):
        if not self.is_blinking:
            self.is_blinking = True
            self.blink_timer.timeout.connect(self.blink_label)
            self.blink_timer.start(500)

    def stop_blinking(self):
        if self.is_blinking:
            self.blink_timer.stop()
            self.label.setStyleSheet("color: turquoise;")
            self.is_blinking = False
            self.blink_state = False

    def blink_label(self):
        if self.blink_state:
            self.label.setStyleSheet("color: turquoise;")
        else:
            self.label.setStyleSheet("color: red;")
        self.blink_state = not self.blink_state

    def minimize_to_taskbar(self):
        self.hide()
        self.mini_timer = MiniTimerWidget(self.label.text())
        self.mini_timer.show()
        self.mini_timer.mousePressEvent = self.restore_overlay_event

    def restore_overlay_event(self, event):
        self.show()
        if self.mini_timer:
            self.mini_timer.close()
            self.mini_timer = None

    def open_settings(self):
        # QLineEdit must be imported for QLineEdit.Password
        password, ok = QInputDialog.getText(
            self, "Admin Access", "Enter admin password:", QLineEdit.Password
        )
        if ok:
            if password == self.admin_password:
                settings_modal = SettingsModal(self)
                settings_modal.password_changed.connect(self.change_admin_password)
                settings_modal.exec_()
            else:
                QMessageBox.warning(self, "Access Denied", "Incorrect password!")

    def change_admin_password(self, new_password):
        self.admin_password = new_password

    def save_state(self):
        # Placeholder for saving state
        pass

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self.drag_position:
            self.move(event.globalPos() - self.drag_position)
            event.accept()

    def mouseReleaseEvent(self, event):
        self.drag_position = None
        event.accept()
