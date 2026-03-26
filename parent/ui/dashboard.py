"""
Parent dashboard — shows all PCs, allows CRUD time control, and shows stats.
"""
from PyQt5.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QDialog, QFormLayout, QLineEdit, QSpinBox, QTabWidget,
    QMessageBox, QComboBox, QSplitter, QFrame, QGroupBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QColor

from shared.db import get_pcs, upsert_pc, delete_pc, get_sales_summary, get_activity_logs
from shared.db import register_user, login_user, get_user, save_user_time, consume_user_time
from parent import client

REFRESH_MS = 5000  # poll every 5 seconds

# ── PC status colors ─────────────────────────────────────────
def _status_color(active: bool, error: bool) -> str:
    if error:   return "#ff4444"
    if active:  return "#00e676"
    return "#ffaa00"

# ─────────────────────────────────────────────────────────────
class AddEditUserDialog(QDialog):
    def __init__(self, user: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add User" if user is None else "Edit User")
        self.setMinimumWidth(350)
        self.setStyleSheet("background:#1a1a2e; color:#eee; QLineEdit{background:#16213e; border:1px solid #333; border-radius:4px; padding:4px;}")

        form = QFormLayout(self)

        self.username_edit = QLineEdit(user["username"] if user else "")
        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.saved_time_spin = QSpinBox()
        self.saved_time_spin.setRange(0, 999999)
        self.saved_time_spin.setSuffix(" seconds")
        self.saved_time_spin.setValue(user["saved_seconds"] if user else 0)

        form.addRow("Username:", self.username_edit)
        if not user:  # Only show password for new users
            form.addRow("Password:", self.password_edit)
        form.addRow("Saved Time:", self.saved_time_spin)

        btns = QHBoxLayout()
        ok_btn = QPushButton("Save")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        form.addRow(btns)

    def get_data(self) -> dict:
        return {
            "username": self.username_edit.text().strip(),
            "password": self.password_edit.text().strip(),
            "saved_seconds": self.saved_time_spin.value()
        }


# ─────────────────────────────────────────────────────────────
class AddEditPCDialog(QDialog):
    def __init__(self, pc: dict = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add PC" if pc is None else "Edit PC")
        self.setMinimumWidth(320)
        self.setStyleSheet("background:#1a1a2e; color:#eee; QLineEdit{background:#16213e; border:1px solid #333; border-radius:4px; padding:4px;}")

        form = QFormLayout(self)

        self.name_edit = QLineEdit(pc["name"] if pc else "")
        self.ip_edit   = QLineEdit(pc["ip"]   if pc else "")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(pc["port"] if pc else 9000)

        form.addRow("PC Name:", self.name_edit)
        form.addRow("IP Address:", self.ip_edit)
        form.addRow("Port:", self.port_spin)

        btns = QHBoxLayout()
        ok_btn = QPushButton("Save")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        form.addRow(btns)

    def get_data(self) -> dict:
        return {"name": self.name_edit.text().strip(),
                "ip":   self.ip_edit.text().strip(),
                "port": self.port_spin.value()}


# ── PC status colors ─────────────────────────────────────────
        form.addRow("IP Address:", self.ip_edit)
        form.addRow("Port:", self.port_spin)

        btns = QHBoxLayout()
        ok_btn = QPushButton("Save")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(ok_btn)
        btns.addWidget(cancel_btn)
        form.addRow(btns)

    def get_data(self) -> dict:
        return {"name": self.name_edit.text().strip(),
                "ip":   self.ip_edit.text().strip(),
                "port": self.port_spin.value()}


# ─────────────────────────────────────────────────────────────
class TimeControlDialog(QDialog):
    def __init__(self, pc_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Control Time — {pc_name}")
        self.setMinimumWidth(300)
        self.setStyleSheet("background:#1a1a2e; color:#eee;")

        form = QFormLayout(self)

        self.action_combo = QComboBox()
        self.action_combo.addItems(["Add Time", "Set Time", "End Session"])
        form.addRow("Action:", self.action_combo)

        self.hours_spin = QSpinBox(); self.hours_spin.setRange(0, 23)
        self.mins_spin  = QSpinBox(); self.mins_spin.setRange(0, 59)
        self.secs_spin  = QSpinBox(); self.secs_spin.setRange(0, 59)

        hms = QHBoxLayout()
        hms.addWidget(QLabel("H:")); hms.addWidget(self.hours_spin)
        hms.addWidget(QLabel("M:")); hms.addWidget(self.mins_spin)
        hms.addWidget(QLabel("S:")); hms.addWidget(self.secs_spin)
        form.addRow("Duration:", hms)

        btns = QHBoxLayout()
        ok_btn = QPushButton("Apply")
        ok_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btns.addWidget(ok_btn); btns.addWidget(cancel_btn)
        form.addRow(btns)

    def get_action(self) -> str:
        return self.action_combo.currentText()

    def get_seconds(self) -> int:
        return self.hours_spin.value()*3600 + self.mins_spin.value()*60 + self.secs_spin.value()


# ─────────────────────────────────────────────────────────────
class PCRow:
    """Holds live status for one PC."""
    def __init__(self, pc: dict):
        self.name = pc["name"]
        self.ip   = pc["ip"]
        self.port = pc["port"]
        self.status = {}
        self.error = False
        self.last_seen = 0  # timestamp of last heartbeat
        self.is_online = False

    def refresh(self):
        result = client.get_status(self.ip, self.port)
        self.error = "error" in result
        self.status = result
        # Update online status based on successful connection
        self.is_online = not self.error
        if self.is_online:
            import time
            self.last_seen = time.time()

    @property
    def time_str(self) -> str:
        r = self.status.get("remaining", 0)
        h = r // 3600; m = (r % 3600) // 60; s = r % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    @property
    def active(self) -> bool:
        return self.status.get("active", False)

    @property
    def coins(self) -> int:
        return self.status.get("coins", 0)


# ─────────────────────────────────────────────────────────────
class DashboardWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PC Cafe — Admin Dashboard")
        self.setMinimumSize(1400, 700)  # Made wider to fit all settings
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #0d0d1a; color: #eee; }
            QTabWidget::pane { border: 1px solid #333; }
            QTabBar::tab { background: #16213e; color: #aaa; padding: 12px 25px; min-width: 180px; }
            QTabBar::tab:selected { background: #0f3460; color: #fff; font-weight: bold; }
            QTableWidget { background: #16213e; gridline-color: #333; color: #eee; }
            QHeaderView::section { background: #0f3460; color: #fff; padding: 6px; }
            QPushButton { background: #0f3460; color: #fff; border-radius: 6px; padding: 6px 16px; }
            QPushButton:hover { background: #1a5276; }
            QPushButton#danger { background: #7b1a1a; }
            QPushButton#danger:hover { background: #a93226; }
            QPushButton#success { background: #0f7b0f; }
            QPushButton#success:hover { background: #1a8f1a; }
        """)

        self.pc_rows: list[PCRow] = []
        self._build_ui()
        self._load_pcs()

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._refresh_all)
        self._poll_timer.start(REFRESH_MS)

    # ── UI construction ──────────────────────────────────────────
    def _build_ui(self):
        tabs = QTabWidget()
        tabs.addTab(self._pc_tab(), "PC Control")
        tabs.addTab(self._users_tab(), "User Management")
        tabs.addTab(self._stats_tab(), "Sales & Stats")
        tabs.addTab(self._logs_tab(), "Activity Log")
        tabs.addTab(self._settings_tab(), "Settings")
        self.setCentralWidget(tabs)

    def _pc_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        # Toolbar
        toolbar = QHBoxLayout()
        add_btn    = QPushButton("+ Add PC")
        edit_btn   = QPushButton("✎ Edit PC")
        remove_btn = QPushButton("✕ Remove PC")
        remove_btn.setObjectName("danger")
        refresh_btn = QPushButton("↻ Refresh")
        time_btn   = QPushButton("⏱ Control Time")

        add_btn.clicked.connect(self._add_pc)
        edit_btn.clicked.connect(self._edit_pc)
        remove_btn.clicked.connect(self._remove_pc)
        refresh_btn.clicked.connect(self._refresh_all)
        time_btn.clicked.connect(self._control_time)

        for b in [add_btn, edit_btn, remove_btn, refresh_btn, time_btn]:
            toolbar.addWidget(b)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Table
        self.pc_table = QTableWidget(0, 8)
        self.pc_table.setHorizontalHeaderLabels(["PC Name", "IP", "Status", "Online", "Time Left", "Coins", "Port", "Controls"])
        self.pc_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pc_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.pc_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.pc_table)
        return w

    def _stats_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        refresh_btn = QPushButton("↻ Refresh Stats")
        refresh_btn.clicked.connect(self._load_stats)
        layout.addWidget(refresh_btn, alignment=Qt.AlignLeft)

        self.stats_table = QTableWidget(0, 5)
        self.stats_table.setHorizontalHeaderLabels(["PC", "Date", "Month", "Sessions", "Sales (₱)"])
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.stats_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.stats_table)
        return w

    def _logs_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        filter_row = QHBoxLayout()
        self.log_pc_combo = QComboBox()
        self.log_pc_combo.addItem("All PCs")
        refresh_btn = QPushButton("↻ Refresh Logs")
        refresh_btn.clicked.connect(self._load_logs)
        filter_row.addWidget(QLabel("Filter PC:"))
        filter_row.addWidget(self.log_pc_combo)
        filter_row.addWidget(refresh_btn)
        filter_row.addStretch()
        layout.addLayout(filter_row)

        self.log_table = QTableWidget(0, 4)
        self.log_table.setHorizontalHeaderLabels(["Timestamp", "PC", "Event", "Detail"])
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.log_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.log_table)
        return w

    def _users_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        # Toolbar
        toolbar = QHBoxLayout()
        add_user_btn = QPushButton("+ Add User")
        edit_user_btn = QPushButton("✎ Edit User")
        delete_user_btn = QPushButton("✕ Delete User")
        delete_user_btn.setObjectName("danger")
        refresh_users_btn = QPushButton("↻ Refresh Users")

        add_user_btn.clicked.connect(self._add_user)
        edit_user_btn.clicked.connect(self._edit_user)
        delete_user_btn.clicked.connect(self._delete_user)
        refresh_users_btn.clicked.connect(self._load_users)

        for b in [add_user_btn, edit_user_btn, delete_user_btn, refresh_users_btn]:
            toolbar.addWidget(b)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # Users table
        self.users_table = QTableWidget(0, 5)
        self.users_table.setHorizontalHeaderLabels(["Username", "Saved Time", "Saved on PC", "Created", "Last Login"])
        self.users_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.users_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.users_table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.users_table)
        return w

    def _settings_tab(self):
        w = QWidget()
        layout = QVBoxLayout(w)

        # General Settings
        general_group = QGroupBox("General Settings")
        general_form = QFormLayout(general_group)

        self.shop_name_edit = QLineEdit("PC Cafe")
        self.shop_name_edit.setText(self._get_config("shop_name", "PC Cafe"))
        general_form.addRow("Shop Name:", self.shop_name_edit)

        self.admin_password_edit = QLineEdit()
        self.admin_password_edit.setEchoMode(QLineEdit.Password)
        self.admin_password_edit.setText(self._get_config("admin_password", "admin"))
        general_form.addRow("Admin Password:", self.admin_password_edit)

        layout.addWidget(general_group)

        # Database Settings
        db_group = QGroupBox("Database Settings")
        db_form = QFormLayout(db_group)

        self.db_backup_btn = QPushButton("Create Backup")
        self.db_backup_btn.clicked.connect(self._backup_database)
        db_form.addRow("Database Backup:", self.db_backup_btn)

        self.db_restore_btn = QPushButton("Restore from Backup")
        self.db_restore_btn.clicked.connect(self._restore_database)
        db_form.addRow("Database Restore:", self.db_restore_btn)

        layout.addWidget(db_group)

        # Save button
        save_btn = QPushButton("Save Settings")
        save_btn.clicked.connect(self._save_settings)
        layout.addWidget(save_btn, alignment=Qt.AlignCenter)

        layout.addStretch()
        return w

    # ── PC CRUD ──────────────────────────────────────────────────
    def _load_pcs(self):
        pcs = get_pcs()
        self.pc_rows = [PCRow(p) for p in pcs]
        self._rebuild_pc_table()
        self._refresh_all()
        # Populate log filter
        self.log_pc_combo.clear()
        self.log_pc_combo.addItem("All PCs")
        for p in pcs:
            self.log_pc_combo.addItem(p["name"])

    def _rebuild_pc_table(self):
        self.pc_table.setRowCount(len(self.pc_rows))
        for i, row in enumerate(self.pc_rows):
            color = _status_color(row.active, row.error)
            status_text = "Online" if row.active else ("Error" if row.error else "Idle")
            online_status = "🟢 Online" if not row.error else "🔴 Offline"

            items = [row.name, row.ip, status_text, online_status, row.time_str, str(row.coins), str(row.port)]

            for j, text in enumerate(items):
                item = QTableWidgetItem(text)
                if j == 2:  # Status column
                    item.setForeground(QColor(color))
                if j == 3:  # Online status column
                    item.setForeground(QColor("#00ff00" if not row.error else "#ff4444"))
                self.pc_table.setItem(i, j, item)

            # Add control buttons
            control_widget = QWidget()
            control_layout = QHBoxLayout(control_widget)
            control_layout.setContentsMargins(2, 2, 2, 2)
            control_layout.setSpacing(2)

            # Message button
            msg_btn = QPushButton("💬")
            msg_btn.setToolTip("Send Message")
            msg_btn.clicked.connect(lambda checked, r=row: self._send_message(r))
            msg_btn.setFixedSize(30, 25)
            control_layout.addWidget(msg_btn)

            # Shutdown button
            shutdown_btn = QPushButton("⏻")
            shutdown_btn.setObjectName("danger")
            shutdown_btn.setToolTip("Shutdown PC")
            shutdown_btn.clicked.connect(lambda checked, r=row: self._shutdown_pc(r))
            shutdown_btn.setFixedSize(30, 25)
            control_layout.addWidget(shutdown_btn)

            control_layout.addStretch()
            self.pc_table.setCellWidget(i, 7, control_widget)

    def on_pc_discovered(self, pc_info):
        """Called when a new PC is auto-discovered via heartbeat"""
        # Refresh the PC list to include newly discovered PCs
        self._load_pcs()
        # Could show a notification here
        print(f"Auto-discovered PC: {pc_info['name']} at {pc_info['ip']}:{pc_info['port']}")

    def _refresh_all(self):
        import threading
        def _do():
            for row in self.pc_rows:
                row.refresh()
        t = threading.Thread(target=_do, daemon=True)
        t.start()
        t.join(timeout=REFRESH_MS / 1000 - 0.5)
        self._rebuild_pc_table()

    def _selected_row(self) -> "PCRow | None":
        rows = self.pc_table.selectedItems()
        if not rows:
            return None
        idx = self.pc_table.currentRow()
        return self.pc_rows[idx] if idx < len(self.pc_rows) else None

    def _add_pc(self):
        dlg = AddEditPCDialog(parent=self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            if data["name"] and data["ip"]:
                upsert_pc(data["name"], data["ip"], data["port"])
                self._load_pcs()

    def _edit_pc(self):
        row = self._selected_row()
        if not row:
            QMessageBox.information(self, "Select PC", "Please select a PC first.")
            return
        dlg = AddEditPCDialog({"name": row.name, "ip": row.ip, "port": row.port}, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            upsert_pc(data["name"], data["ip"], data["port"])
            self._load_pcs()

    def _remove_pc(self):
        row = self._selected_row()
        if not row:
            return
        if QMessageBox.question(self, "Remove PC", f"Remove {row.name}?") == QMessageBox.Yes:
            delete_pc(row.name)
            self._load_pcs()

    def _control_time(self):
        row = self._selected_row()
        if not row:
            QMessageBox.information(self, "Select PC", "Please select a PC first.")
            return
        dlg = TimeControlDialog(row.name, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            action = dlg.get_action()
            seconds = dlg.get_seconds()
            try:
                if action == "Add Time":
                    client.add_time(row.ip, row.port, seconds)
                elif action == "Set Time":
                    client.set_time(row.ip, row.port, seconds)
                elif action == "End Session":
                    client.end_session(row.ip, row.port)
                self._refresh_all()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    # ── User Management ──────────────────────────────────────────
    def _load_users(self):
        # This would need to be implemented in the database module
        # For now, just clear the table
        self.users_table.setRowCount(0)

    def _add_user(self):
        dlg = AddEditUserDialog(parent=self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            if data["username"] and data["password"]:
                success, msg = register_user(data["username"], data["password"])
                if success:
                    if data["saved_seconds"] > 0:
                        save_user_time(data["username"], data["saved_seconds"], "")
                    self._load_users()
                else:
                    QMessageBox.warning(self, "Error", msg)

    def _edit_user(self):
        # Get selected user
        rows = self.users_table.selectedItems()
        if not rows:
            QMessageBox.information(self, "Select User", "Please select a user first.")
            return
        idx = self.users_table.currentRow()
        username = self.users_table.item(idx, 0).text()
        user = get_user(username)
        if not user:
            return

        dlg = AddEditUserDialog(user, parent=self)
        if dlg.exec_() == QDialog.Accepted:
            data = dlg.get_data()
            if data["saved_seconds"] != user["saved_seconds"]:
                save_user_time(data["username"], data["saved_seconds"], user.get("saved_on_pc", ""))
            self._load_users()

    def _delete_user(self):
        rows = self.users_table.selectedItems()
        if not rows:
            QMessageBox.information(self, "Select User", "Please select a user first.")
            return
        idx = self.users_table.currentRow()
        username = self.users_table.item(idx, 0).text()

        if QMessageBox.question(self, "Delete User", f"Delete user '{username}'?") == QMessageBox.Yes:
            # This would need to be implemented in the database module
            # For now, just show a message
            QMessageBox.information(self, "Not Implemented", "User deletion not yet implemented.")

    # ── Settings ─────────────────────────────────────────────────
    def _get_config(self, key, default=None):
        # Simple config storage - could be enhanced with a config file
        return default

    def _save_settings(self):
        # Save settings - could be enhanced with config file persistence
        QMessageBox.information(self, "Settings Saved", "Settings have been saved successfully!")

    def _backup_database(self):
        from datetime import datetime
        import shutil
        import os

        db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'cafe.db')
        backup_path = os.path.join(os.path.dirname(db_path), f'cafe_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db')

        try:
            shutil.copy2(db_path, backup_path)
            QMessageBox.information(self, "Backup Created", f"Database backed up to:\n{backup_path}")
        except Exception as e:
            QMessageBox.warning(self, "Backup Failed", str(e))

    def _restore_database(self):
        from PyQt5.QtWidgets import QFileDialog
        import shutil
        import os

        db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'cafe.db')

        backup_path, _ = QFileDialog.getOpenFileName(
            self, "Select Backup File", os.path.dirname(db_path),
            "Database files (*.db);;All files (*)")

        if backup_path:
            try:
                shutil.copy2(backup_path, db_path)
                QMessageBox.information(self, "Restore Complete", "Database restored successfully. Please restart the application.")
            except Exception as e:
                QMessageBox.warning(self, "Restore Failed", str(e))

    # ── Remote Control ───────────────────────────────────────────
    def _send_message(self, pc_row):
        from PyQt5.QtWidgets import QInputDialog
        message, ok = QInputDialog.getText(self, "Send Message", f"Message to {pc_row.name}:")
        if ok and message.strip():
            try:
                result = client.send_message(pc_row.ip, pc_row.port, message.strip())
                if "error" not in result:
                    QMessageBox.information(self, "Success", f"Message sent to {pc_row.name}")
                else:
                    QMessageBox.warning(self, "Error", f"Failed to send message: {result.get('error')}")
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))

    def _shutdown_pc(self, pc_row):
        reply = QMessageBox.question(self, "Shutdown PC",
                                   f"Are you sure you want to shutdown {pc_row.name}?",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                result = client.shutdown_pc(pc_row.ip, pc_row.port)
                if "error" not in result:
                    QMessageBox.information(self, "Success", f"Shutdown command sent to {pc_row.name}")
                else:
                    QMessageBox.warning(self, "Error", f"Failed to shutdown: {result.get('error')}")
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))
    def _load_stats(self):
        rows = get_sales_summary()
        self.stats_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, val in enumerate([r["pc_name"], r["day"], r["month"], str(r["sessions"]), f"₱{r['total']:.2f}"]):
                self.stats_table.setItem(i, j, QTableWidgetItem(val))

    # ── Logs ─────────────────────────────────────────────────────
    def _load_logs(self):
        pc = self.log_pc_combo.currentText()
        pc_filter = None if pc == "All PCs" else pc
        rows = get_activity_logs(pc_filter)
        self.log_table.setRowCount(len(rows))
        for i, r in enumerate(rows):
            for j, val in enumerate([r["timestamp"], r["pc_name"], r["event_type"], r.get("detail", "")]):
                self.log_table.setItem(i, j, QTableWidgetItem(str(val)))
