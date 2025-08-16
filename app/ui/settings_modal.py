from PyQt5.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QComboBox, QSpinBox, QTableWidget, QTableWidgetItem,
    QCheckBox, QTextEdit
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor, QPalette

class SettingsModal(QDialog):
    password_changed = pyqtSignal(str)  # Signal to notify password change

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Admin Settings")
        self.setMinimumSize(650, 430)
        self.setFont(QFont("Segoe UI", 11))

        # Set a lighter background and dark text for better contrast
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor("#f4f6fa"))
        palette.setColor(QPalette.WindowText, QColor("#222"))
        self.setPalette(palette)

        self.tabs = QTabWidget()
        self.tabs.setFont(QFont("Segoe UI", 12))
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #bfc9d6; border-radius: 8px; }
            QTabBar::tab { background: #e9edf5; color: #222; padding: 10px 28px; border-radius: 8px; font-size: 15px; }
            QTabBar::tab:selected { background: #dbe6f6; font-weight: bold; }
            QLabel { font-size: 14px; color: #222; }
            QPushButton { background: #4f8cff; color: white; border-radius: 6px; padding: 7px 22px; font-weight: bold; }
            QPushButton:hover { background: #6ea8fe; }
            QLineEdit, QSpinBox, QComboBox, QTextEdit { background: #f4f6fa; color: #222; border-radius: 6px; }
            QCheckBox { font-size: 13px; color: #222; }
            QHeaderView::section { background: #e9edf5; color: #222; font-weight: bold; }
        """)

        layout = QVBoxLayout(self)
        layout.addWidget(self.tabs)

        self.tabs.addTab(self._timer_tab(), "Timer Options")
        self.tabs.addTab(self._serial_tab(), "Serial & Pulse Options")
        self.tabs.addTab(self._network_tab(), "Networking & Statistics")
        self.tabs.addTab(self._admin_tab(), "Admin Privileges")

    def _timer_tab(self):
        tab = QWidget()
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFormAlignment(Qt.AlignTop)

        timer_length = QSpinBox()
        timer_length.setRange(1, 180)
        timer_length.setValue(30)
        form.addRow("Default Timer (minutes):", timer_length)

        auto_reset = QCheckBox("Auto-reset timer when coin inserted")
        form.addRow("", auto_reset)

        save_btn = QPushButton("Save Timer Settings")
        form.addRow("", save_btn)

        tab.setLayout(form)
        return tab

    def _serial_tab(self):
        tab = QWidget()
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignRight)
        form.setFormAlignment(Qt.AlignTop)

        com_port = QComboBox()
        com_port.addItems(["COM1", "COM2", "COM3", "COM4"])  # Mock
        form.addRow("COM Port:", com_port)

        pulse_layout = QVBoxLayout()
        for pulse in [1, 5, 10, 20]:
            pulse_row = QHBoxLayout()
            pulse_label = QLabel(f"Time for {pulse} pulse(s):")
            pulse_spin = QSpinBox()
            pulse_spin.setRange(1, 60)
            pulse_spin.setValue(pulse)
            pulse_row.addWidget(pulse_label)
            pulse_row.addWidget(pulse_spin)
            pulse_layout.addLayout(pulse_row)
        form.addRow("Pulse Time Options:", pulse_layout)

        save_btn = QPushButton("Save Serial Settings")
        form.addRow("", save_btn)

        tab.setLayout(form)
        return tab

    def _network_tab(self):
        tab = QWidget()
        vbox = QVBoxLayout()

        stats_label = QLabel("PC Statistics (Mock Data)")
        stats_label.setFont(QFont("Segoe UI", 13, QFont.Bold))
        vbox.addWidget(stats_label)

        table = QTableWidget(3, 4)
        table.setHorizontalHeaderLabels(["PC Name", "Daily Sales", "COM Status", "Timer"])
        for i, pc in enumerate(["PC-01", "PC-02", "PC-03"]):
            table.setItem(i, 0, QTableWidgetItem(pc))
            table.setItem(i, 1, QTableWidgetItem("₱100"))
            table.setItem(i, 2, QTableWidgetItem("Healthy"))
            table.setItem(i, 3, QTableWidgetItem("00:15:00"))
        table.horizontalHeader().setStretchLastSection(True)
        vbox.addWidget(table)

        control_label = QLabel("Remote Control (Mock)")
        control_label.setFont(QFont("Segoe UI", 12))
        vbox.addWidget(control_label)
        control_box = QHBoxLayout()
        control_box.addWidget(QPushButton("Add Time"))
        control_box.addWidget(QPushButton("Edit Time"))
        control_box.addWidget(QPushButton("Remove Time"))
        vbox.addLayout(control_box)

        tab.setLayout(vbox)
        return tab

    def _admin_tab(self):
        tab = QWidget()
        vbox = QVBoxLayout()

        protect_checkbox = QCheckBox("Prevent closing timer (Task Manager/Event Window)")
        protect_checkbox.setChecked(True)
        vbox.addWidget(protect_checkbox)

        admin_checkbox = QCheckBox("Enable Windows Admin Privileges")
        vbox.addWidget(admin_checkbox)

        service_checkbox = QCheckBox("Run as Windows Service")
        vbox.addWidget(service_checkbox)

        notes = QTextEdit()
        notes.setPlaceholderText("Notes or instructions for admin...")
        vbox.addWidget(notes)

        pw_label = QLabel("Change Admin Password:")
        pw_label.setFont(QFont("Segoe UI", 12, QFont.Bold))
        vbox.addWidget(pw_label)

        pw_input = QLineEdit()
        pw_input.setEchoMode(QLineEdit.Password)
        pw_input.setPlaceholderText("Enter new password")
        vbox.addWidget(pw_input)

        pw_btn = QPushButton("Change Password")
        vbox.addWidget(pw_btn)

        def change_password():
            new_pw = pw_input.text()
            if new_pw:
                self.password_changed.emit(new_pw)
                pw_input.clear()
                pw_input.setPlaceholderText("Password changed!")
            else:
                pw_input.setPlaceholderText("Enter a valid password")

        pw_btn.clicked.connect(change_password)

        save_btn = QPushButton("Save Admin Settings")
        vbox.addWidget(save_btn)

        tab.setLayout(vbox)
        return tab

# --- Networking Tab Explanation ---
# For a robust solution, use a lightweight server (e.g., Flask or FastAPI) running on each timer PC.
# Each PC exposes REST endpoints for timer control and status.
# The admin app discovers PCs via UDP broadcast or a static config file.
# The admin app can send requests to add/edit/remove time, and fetch statistics.
# Security: Use authentication tokens and restrict access to local network.
# Statistics can be stored in a local database (SQLite) and fetched via API.
# This approach is scalable, secure, and easy to maintain.