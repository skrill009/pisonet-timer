"""
Child settings modal — password protected, admin only.
Tabs: Timer Settings | COM Settings | Overlay Settings | Statistics | Admin
"""
from PyQt5.QtWidgets import (
    QDialog, QTabWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QPushButton, QFormLayout, QComboBox,
    QSpinBox, QDoubleSpinBox, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QGroupBox, QSlider, QColorDialog,
    QFileDialog, QTimeEdit
)
from PyQt5.QtCore import Qt, pyqtSignal, QTime
from PyQt5.QtGui import QFont, QColor

STYLE = """
    QDialog   { background:#0d0d1a; color:#eee; }
    QWidget   { background:#0d0d1a; color:#eee; }
    QTabWidget::pane  { border:1px solid #222; border-radius:6px; }
    QTabBar::tab      { background:#16213e; color:#888; padding:9px 22px; border-radius:6px; font-size:13px; }
    QTabBar::tab:selected { background:#0f3460; color:#fff; font-weight:bold; }
    QLabel    { color:#ccc; font-size:13px; }
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
        background:#16213e; color:#eee; border:1px solid #2a2a4a;
        border-radius:4px; padding:5px; font-size:13px; }
    QPushButton { background:#0f3460; color:#fff; border-radius:6px;
                  padding:7px 20px; font-weight:bold; font-size:13px; }
    QPushButton:hover { background:#1a5276; }
    QPushButton#danger { background:#7b1a1a; }
    QPushButton#danger:hover { background:#a93226; }
    QGroupBox { border:1px solid #2a2a4a; border-radius:6px; margin-top:10px;
                color:#888; font-size:12px; padding:8px; }
    QGroupBox::title { subcontrol-origin:margin; left:10px; }
    QCheckBox { color:#ccc; font-size:13px; }
    QTableWidget { background:#16213e; gridline-color:#2a2a4a; color:#eee; }
    QHeaderView::section { background:#0f3460; color:#fff; padding:5px; }
    QSlider::groove:horizontal { background:#2a2a4a; height:6px; border-radius:3px; }
    QSlider::handle:horizontal { background:#00e5ff; width:14px; height:14px;
                                  margin:-4px 0; border-radius:7px; }
"""


class ChildSettingsModal(QDialog):
    settings_saved   = pyqtSignal(dict)
    timer_add_time   = pyqtSignal(int)   # seconds to add
    timer_stop       = pyqtSignal()
    timer_reset      = pyqtSignal()

    def __init__(self, config: dict, db_path: str = "", parent=None):
        super().__init__(parent)
        self.config  = config.copy()
        self.db_path = db_path
        self.setWindowTitle("Settings")
        self.setMinimumSize(1100, 650)  # wider dialog so long labels are shown
        self.setFont(QFont("Segoe UI", 11))
        self.setStyleSheet(STYLE)

        tabs = QTabWidget()
        tabs.setStyleSheet("QTabBar::tab { min-width: 140px; }")
        tabs.addTab(self._timer_tab(),   "Timer Settings")
        tabs.addTab(self._com_tab(),     "COM Settings")
        tabs.addTab(self._overlay_tab(), "Overlay Settings")
        tabs.addTab(self._stats_tab(),   "Statistics")
        tabs.addTab(self._admin_tab(),   "Admin")

        layout = QVBoxLayout(self)
        layout.addWidget(tabs)

    def _init_form_layout(self, form: QFormLayout):
        form.setSpacing(12)
        form.setContentsMargins(20, 20, 20, 10)
        form.setLabelAlignment(Qt.AlignRight)
        form.setRowWrapPolicy(QFormLayout.DontWrapRows)

    # ── Timer Settings ───────────────────────────────────────────
    def _timer_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        self._init_form_layout(form)

        # Speed multiplier (1.0 = normal, 2.0 = double speed for testing)
        self.speed_spin = QDoubleSpinBox()
        self.speed_spin.setRange(0.1, 10.0)
        self.speed_spin.setSingleStep(0.1)
        self.speed_spin.setValue(self.config.get("timer_speed", 1.0))
        self.speed_spin.setToolTip("1.0 = normal speed. 2.0 = timer runs 2x faster (for testing).")
        form.addRow("Timer Speed Multiplier:", self.speed_spin)

        # Timer font size
        self.font_spin = QSpinBox()
        self.font_spin.setRange(10, 120)
        self.font_spin.setValue(self.config.get("timer_font_size", 26))
        form.addRow("Timer Font Size:", self.font_spin)

        # Timer color
        self._timer_color = self.config.get("timer_color", "#00e5ff")
        self.color_btn = QPushButton("Pick Color")
        self.color_preview = QLabel()
        self.color_preview.setFixedSize(32, 24)
        self._update_color_preview()
        self.color_btn.clicked.connect(self._pick_timer_color)
        color_row = QHBoxLayout()
        color_row.addWidget(self.color_btn)
        color_row.addWidget(self.color_preview)
        color_row.addStretch()
        form.addRow("Timer Color:", color_row)

        # Blink threshold
        self.blink_spin = QSpinBox()
        self.blink_spin.setRange(0, 600)
        self.blink_spin.setValue(self.config.get("blink_threshold", 60))
        self.blink_spin.setSuffix(" sec")
        form.addRow("Blink when time left ≤:", self.blink_spin)

        # Standalone mode (no parent)
        self.standalone_check = QCheckBox("Standalone mode (no parent app)")
        self.standalone_check.setChecked(self.config.get("standalone", True))
        form.addRow(self.standalone_check)

        # Parent IP / port
        self.parent_ip_edit = QLineEdit(self.config.get("parent_ip", ""))
        self.parent_ip_edit.setPlaceholderText("e.g. 192.168.1.100")
        form.addRow("Parent App IP:", self.parent_ip_edit)

        self.parent_port_spin = QSpinBox()
        self.parent_port_spin.setRange(1, 65535)
        self.parent_port_spin.setValue(self.config.get("parent_port", 9100))
        form.addRow("Parent App Port:", self.parent_port_spin)

        save = QPushButton("Save Timer Settings")
        save.clicked.connect(self._save_timer)
        form.addRow(save)

        # ── Timer Controls ───────────────────────────────────────
        ctrl_grp = QGroupBox("Timer Controls")
        ctrl_grp.setStyleSheet("QGroupBox { margin-top:16px; }")
        ctrl_layout = QVBoxLayout(ctrl_grp)
        ctrl_layout.setSpacing(10)

        # Add time row
        add_row = QHBoxLayout()
        self.add_time_edit = QTimeEdit()
        self.add_time_edit.setDisplayFormat("HH:mm:ss")
        self.add_time_edit.setTime(QTime(0, 30, 0))   # default 30 min
        self.add_time_edit.setFixedWidth(110)
        add_btn = QPushButton("➕  Add Time")
        add_btn.setStyleSheet("background:#1a4a1a; color:#7fff7f;")
        add_btn.clicked.connect(self._on_add_time)
        add_row.addWidget(QLabel("Add time (HH:mm:ss):"))
        add_row.addWidget(self.add_time_edit)
        add_row.addWidget(add_btn)
        add_row.addStretch()
        ctrl_layout.addLayout(add_row)

        # Stop / Reset row
        action_row = QHBoxLayout()
        stop_btn = QPushButton("⏹  Stop Timer")
        stop_btn.setObjectName("danger")
        stop_btn.setStyleSheet("background:#7b1a1a; color:#ffaaaa;")
        stop_btn.clicked.connect(self._on_stop_timer)
        reset_btn = QPushButton("↺  Reset Timer")
        reset_btn.setStyleSheet("background:#3a2a00; color:#ffd080;")
        reset_btn.clicked.connect(self._on_reset_timer)
        action_row.addWidget(stop_btn)
        action_row.addWidget(reset_btn)
        action_row.addStretch()
        ctrl_layout.addLayout(action_row)

        form.addRow(ctrl_grp)
        return tab

    def _pick_timer_color(self):
        color = QColorDialog.getColor(QColor(self._timer_color), self, "Pick Timer Color")
        if color.isValid():
            self._timer_color = color.name()
            self._update_color_preview()

    def _pick_shop_color(self):
        current_color = QColor(self.shop_color_edit.text()) if self.shop_color_edit.text() else QColor("#00e5ff")
        color = QColorDialog.getColor(current_color, self, "Pick Shop Name Color")
        if color.isValid():
            self.shop_color_edit.setText(color.name())

    def _update_color_preview(self):
        self.color_preview.setStyleSheet(
            f"background:{self._timer_color}; border:1px solid #444; border-radius:3px;")

    def _save_timer(self):
        self.config["timer_speed"]      = self.speed_spin.value()
        self.config["timer_font_size"]  = self.font_spin.value()
        self.config["timer_color"]      = self._timer_color
        self.config["blink_threshold"]  = self.blink_spin.value()
        self.config["standalone"]       = self.standalone_check.isChecked()
        self.config["parent_ip"]        = self.parent_ip_edit.text().strip()
        self.config["parent_port"]      = self.parent_port_spin.value()
        self.settings_saved.emit(self.config)

    def _on_add_time(self):
        t = self.add_time_edit.time()
        seconds = t.hour() * 3600 + t.minute() * 60 + t.second()
        if seconds > 0:
            self.timer_add_time.emit(seconds)

    def _on_stop_timer(self):
        self.timer_stop.emit()

    def _on_reset_timer(self):
        self.timer_reset.emit()
        self.close()

    # ── COM Settings ─────────────────────────────────────────────
    def _com_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        self._init_form_layout(form)

        self.port_combo = QComboBox()
        try:
            from serial.tools import list_ports
            available_ports = [p.device for p in list_ports.comports()]
        except Exception:
            available_ports = []

        if not available_ports:
            available_ports = ["COM1", "COM2", "COM3", "COM4"]

        ports = ["(None)"] + available_ports
        self.port_combo.addItems(ports)
        cur = self.config.get("com_port", "COM1")
        if cur in ports:
            self.port_combo.setCurrentText(cur)
        else:
            # prefer first detected available
            if len(ports) > 1:
                self.port_combo.setCurrentIndex(1)
        form.addRow("COM Port:", self.port_combo)

        self.baud_combo = QComboBox()
        self.baud_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baud_combo.setCurrentText(str(self.config.get("baud_rate", 9600)))
        form.addRow("Baud Rate:", self.baud_combo)

        self.com_mode_combo = QComboBox()
        self.com_mode_combo.addItems(["Auto", "Vout", "Vin"])
        self.com_mode_combo.setCurrentText(self.config.get("com_mode", "Auto"))
        form.addRow("COM Mode:", self.com_mode_combo)
        # Coin pulse → time mapping
        grp = QGroupBox("Coin Pulse → Time Mapping")
        grp_form = QFormLayout(grp)

        self.coin_spins = {}
        coin_map = self.config.get("coin_map", {"1": 1800, "5": 9000, "10": 18000, "20": 36000})
        for pulse_label in ["1 pulse", "5 pulses", "10 pulses", "20 pulses"]:
            key = pulse_label.split()[0]
            spin = QSpinBox()
            spin.setRange(1, 86400)
            spin.setValue(coin_map.get(key, int(key) * 1800))
            spin.setSuffix(" sec")
            self.coin_spins[key] = spin
            grp_form.addRow(f"{pulse_label} =", spin)

        form.addRow(grp)

        save = QPushButton("Save COM Settings")
        save.clicked.connect(self._save_com)
        form.addRow(save)
        return tab

    def _save_com(self):
        self.config["com_port"]  = self.port_combo.currentText()
        self.config["baud_rate"] = int(self.baud_combo.currentText())
        self.config["com_mode"]  = self.com_mode_combo.currentText()
        self.config["coin_map"]  = {k: v.value() for k, v in self.coin_spins.items()}
        self.settings_saved.emit(self.config)

    # ── Overlay Settings ─────────────────────────────────────────
    def _overlay_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        self._init_form_layout(form)

        self.shop_edit = QLineEdit(self.config.get("shop_name", "PC Cafe"))
        form.addRow("Shop Name:", self.shop_edit)

        # Shop name animation options
        self.shop_animation_combo = QComboBox()
        self.shop_animation_combo.addItems([
            "None", "Rainbow", "Pulse", "Glow", "Color Cycle", "Typewriter"
        ])
        self.shop_animation_combo.setCurrentText(self.config.get("shop_animation", "None"))
        form.addRow("Shop Name Animation:", self.shop_animation_combo)

        # Animation speed
        self.shop_anim_speed_spin = QSpinBox()
        self.shop_anim_speed_spin.setRange(100, 2000)
        self.shop_anim_speed_spin.setValue(self.config.get("shop_anim_speed", 500))
        self.shop_anim_speed_spin.setSuffix(" ms")
        self.shop_anim_speed_spin.setToolTip("Animation speed in milliseconds")
        form.addRow("Animation Speed:", self.shop_anim_speed_spin)

        # Primary color for animations
        self.shop_color_edit = QLineEdit(self.config.get("shop_color", "#00e5ff"))
        self.shop_color_edit.setPlaceholderText("#RRGGBB or color name")
        self.shop_color_btn = QPushButton("Pick Color")
        self.shop_color_btn.clicked.connect(self._pick_shop_color)
        color_layout = QHBoxLayout()
        color_layout.addWidget(self.shop_color_edit)
        color_layout.addWidget(self.shop_color_btn)
        form.addRow("Shop Name Color:", color_layout)

        self.pc_edit = QLineEdit(self.config.get("pc_name", "PC-01"))
        form.addRow("PC Name:", self.pc_edit)

        # Animation / Image with file dialog
        anim_layout = QHBoxLayout()
        self.anim_edit = QLineEdit(self.config.get("animation_path", ""))
        self.anim_edit.setPlaceholderText("Path to .gif or image file")
        anim_layout.addWidget(self.anim_edit)
        
        self.anim_btn = QPushButton("Browse...")
        self.anim_btn.clicked.connect(self._browse_animation)
        anim_layout.addWidget(self.anim_btn)
        form.addRow("Animation / Image:", anim_layout)

        # Background type
        self.bg_type_combo = QComboBox()
        self.bg_type_combo.addItems(["Solid Color", "Static Picture", "Live Wallpaper"])
        self.bg_type_combo.setCurrentText(self.config.get("background_type", "Solid Color"))
        form.addRow("Background Type:", self.bg_type_combo)

        # Background path — label + widgets stored so we can show/hide them
        self.bg_label = QLabel("Background File:")
        self.bg_edit = QLineEdit(self.config.get("background_path", ""))
        self.bg_edit.setPlaceholderText("Path to background image/GIF")
        self.bg_btn = QPushButton("Browse...")
        self.bg_btn.clicked.connect(self._browse_background)
        bg_layout = QHBoxLayout()
        bg_layout.addWidget(self.bg_edit)
        bg_layout.addWidget(self.bg_btn)
        form.addRow(self.bg_label, bg_layout)

        # Connect after widgets exist
        self.bg_type_combo.currentTextChanged.connect(self._on_bg_type_changed)
        self._on_bg_type_changed(self.bg_type_combo.currentText())

        self.shutdown_spin = QSpinBox()
        self.shutdown_spin.setRange(10, 3600)
        self.shutdown_spin.setValue(self.config.get("shutdown_countdown", 180))
        self.shutdown_spin.setSuffix(" sec")
        form.addRow("Shutdown Countdown:", self.shutdown_spin)

        save = QPushButton("Save Overlay Settings")
        save.clicked.connect(self._save_overlay)
        form.addRow(save)
        return tab

    def _save_overlay(self):
        self.config["shop_name"]          = self.shop_edit.text().strip()
        self.config["shop_animation"]     = self.shop_animation_combo.currentText()
        self.config["shop_anim_speed"]    = self.shop_anim_speed_spin.value()
        self.config["shop_color"]         = self.shop_color_edit.text().strip()
        self.config["pc_name"]            = self.pc_edit.text().strip()
        self.config["animation_path"]     = self.anim_edit.text().strip()
        self.config["background_type"]    = self.bg_type_combo.currentText()
        self.config["background_path"]    = self.bg_edit.text().strip()
        self.config["shutdown_countdown"] = self.shutdown_spin.value()
        self.settings_saved.emit(self.config)

    def _browse_animation(self):
        import os
        default_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'assets')
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Animation/Image", default_dir,
            "Image files (*.png *.jpg *.jpeg *.gif *.bmp);;All files (*)")
        if file_path:
            self.anim_edit.setText(file_path)

    def _browse_background(self):
        import os
        default_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'assets')
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Background", default_dir,
            "Image/Video files (*.png *.jpg *.jpeg *.gif *.bmp *.mp4 *.avi *.mov);;All files (*)")
        if file_path:
            self.bg_edit.setText(file_path)

    def _on_bg_type_changed(self, bg_type):
        visible = bg_type != "Solid Color"
        self.bg_label.setVisible(visible)
        self.bg_edit.setVisible(visible)
        self.bg_btn.setVisible(visible)

    # ── Statistics ───────────────────────────────────────────────
    def _stats_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(12, 12, 12, 12)

        # Coin log
        coin_label = QLabel("Coin Insertions")
        coin_label.setFont(QFont("Segoe UI", 13, QFont.Bold))
        coin_label.setStyleSheet("color:#00e5ff;")
        layout.addWidget(coin_label)

        self.coin_table = QTableWidget(0, 3)
        self.coin_table.setHorizontalHeaderLabels(["Timestamp", "PC", "Detail"])
        self.coin_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.coin_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.coin_table)

        # User sessions
        user_label = QLabel("User Sessions")
        user_label.setFont(QFont("Segoe UI", 13, QFont.Bold))
        user_label.setStyleSheet("color:#00e5ff;")
        layout.addWidget(user_label)

        self.session_table = QTableWidget(0, 5)
        self.session_table.setHorizontalHeaderLabels(
            ["Username", "PC", "Started", "Ended", "Seconds"])
        self.session_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.session_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.session_table)

        refresh_btn = QPushButton("↻ Refresh")
        refresh_btn.clicked.connect(self._load_stats)
        layout.addWidget(refresh_btn, alignment=Qt.AlignLeft)

        self._load_stats()
        return tab

    def _load_stats(self):
        from shared.db import get_coin_logs, get_conn
        import os

        # Coin logs
        logs = get_coin_logs(self.config.get("pc_name"), path=self.db_path)
        self.coin_table.setRowCount(len(logs))
        for i, r in enumerate(logs):
            for j, v in enumerate([r["timestamp"], r["pc_name"], r.get("detail", "")]):
                self.coin_table.setItem(i, j, QTableWidgetItem(str(v)))

        # Sessions
        conn = get_conn(self.db_path)
        rows = conn.execute(
            "SELECT username, pc_name, started_at, ended_at, total_seconds FROM sessions "
            "WHERE pc_name=? ORDER BY started_at DESC LIMIT 100",
            (self.config.get("pc_name", ""),)
        ).fetchall()
        conn.close()
        self.session_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, v in enumerate([r[0] or "guest", r[1], r[2], r[3] or "-", str(r[4])]):
                self.session_table.setItem(i, j, QTableWidgetItem(str(v)))

    # ── Admin ────────────────────────────────────────────────────
    def _admin_tab(self):
        tab = QWidget()
        form = QFormLayout(tab)
        self._init_form_layout(form)

        self.kw_edit = QLineEdit(self.config.get("admin_keyword", "grefin"))
        form.addRow("Admin Keyword:", self.kw_edit)

        self.server_port_spin = QSpinBox()
        self.server_port_spin.setRange(1024, 65535)
        self.server_port_spin.setValue(self.config.get("server_port", 9000))
        form.addRow("Child Server Port:", self.server_port_spin)

        self.startup_check = QCheckBox("Run child app at Windows startup")
        self.startup_check.setChecked(self.config.get("launch_on_startup", False))
        form.addRow(self.startup_check)

        self.disable_tmgr_check = QCheckBox("Disable Task Manager for current user")
        self.disable_tmgr_check.setChecked(self.config.get("disable_task_manager", False))
        form.addRow(self.disable_tmgr_check)

        self.disable_taskview_check = QCheckBox("Disable Task View (Win+Tab)")
        self.disable_taskview_check.setChecked(self.config.get("disable_task_view", False))
        form.addRow(self.disable_taskview_check)

        self.disable_signout_check = QCheckBox("Disable Windows Sign Out / Log Off")
        self.disable_signout_check.setChecked(self.config.get("disable_signout", False))
        form.addRow(self.disable_signout_check)

        self.disable_reboot_check = QCheckBox("Disable watchdog auto-reboot on repeated failures")
        self.disable_reboot_check.setChecked(not self.config.get("watchdog_reboot_enabled", True))
        form.addRow(self.disable_reboot_check)

        pw_grp = QGroupBox("Change Admin Password")
        pw_form = QFormLayout(pw_grp)
        self.pw_edit = QLineEdit()
        self.pw_edit.setEchoMode(QLineEdit.Password)
        self.pw_edit.setPlaceholderText(f"Current: {'*' * len(self.config.get('admin_password','admin'))}  — type to change")
        self.pw2_edit = QLineEdit()
        self.pw2_edit.setEchoMode(QLineEdit.Password)
        self.pw2_edit.setPlaceholderText("Confirm new password")
        self.pw_msg = QLabel("")
        self.pw_msg.setStyleSheet("color:#ff6060;")
        pw_form.addRow("New Password:", self.pw_edit)
        pw_form.addRow("Confirm:", self.pw2_edit)
        pw_form.addRow(self.pw_msg)
        form.addRow(pw_grp)

        save = QPushButton("Save Admin Settings")
        save.clicked.connect(self._save_admin)
        form.addRow(save)
        return tab

    def _save_admin(self):
        self.config["admin_keyword"] = self.kw_edit.text().strip()
        self.config["server_port"]   = self.server_port_spin.value()
        self.config["launch_on_startup"]    = self.startup_check.isChecked()
        self.config["disable_task_manager"] = self.disable_tmgr_check.isChecked()
        self.config["disable_task_view"]    = self.disable_taskview_check.isChecked()
        self.config["disable_signout"]      = self.disable_signout_check.isChecked()
        self.config["watchdog_reboot_enabled"] = not self.disable_reboot_check.isChecked()

        pw = self.pw_edit.text()
        pw2 = self.pw2_edit.text()
        if pw:
            if pw != pw2:
                self.pw_msg.setText("Passwords do not match.")
                return
            self.config["admin_password"] = pw
            self.pw_msg.setText("")
        self.settings_saved.emit(self.config)
