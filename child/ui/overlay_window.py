"""
Child overlay UI:
  FullscreenOverlay — shown when no session is active (Insert Coin screen).
  DraggableTimer    — small always-on-top widget during an active session.
"""
import subprocess, sys, os
from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout, QPushButton,
    QApplication, QDialog, QLineEdit, QFormLayout, QMessageBox,
    QStackedWidget, QStackedLayout, QSizePolicy
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QUrl
from PyQt5.QtGui import QFont, QPixmap, QMovie, QPainter, QColor, QPalette, QImage
from PyQt5.QtMultimedia import QMediaPlayer, QMediaContent
from PyQt5.QtMultimediaWidgets import QVideoWidget

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    cv2 = None
    OPENCV_AVAILABLE = False


# ─────────────────────────────────────────────────────────────────────────────
class AdminPasswordDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Admin Access")
        self.setFixedSize(320, 160)
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QDialog   { background:#0d0d1a; color:#eee; }
            QLabel    { color:#ccc; font-size:13px; }
            QLineEdit { background:#16213e; color:#eee; border:1px solid #333;
                        border-radius:4px; padding:6px; font-size:13px; }
            QPushButton { background:#0f3460; color:#fff; border-radius:6px;
                          padding:8px 20px; font-weight:bold; font-size:13px; }
            QPushButton:hover { background:#1a5276; }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)
        layout.addWidget(QLabel("Enter admin password:"))
        self.pw_edit = QLineEdit()
        self.pw_edit.setEchoMode(QLineEdit.Password)
        self.pw_edit.setPlaceholderText("Password")
        self.pw_edit.returnPressed.connect(self._confirm)
        layout.addWidget(self.pw_edit)
        self.msg_label = QLabel("")
        self.msg_label.setStyleSheet("color:#ff6060; font-size:12px;")
        layout.addWidget(self.msg_label)
        btn_row = QHBoxLayout()
        ok_btn = QPushButton("Confirm")
        ok_btn.clicked.connect(self._confirm)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setStyleSheet(
            "background:#1a1a2e; color:#888; border:1px solid #333;"
            "border-radius:6px; padding:8px 20px; font-size:13px;")
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

    def _confirm(self):
        if self.pw_edit.text():
            self.accept()
        else:
            self.msg_label.setText("Please enter a password.")

    def password(self) -> str:
        return self.pw_edit.text()


# ─────────────────────────────────────────────────────────────────────────────
class LoginDialog(QDialog):
    login_success    = pyqtSignal(str, int)
    register_success = pyqtSignal(str)

    def __init__(self, db_path: str, pc_name: str,
                 parent_ip: str = "", parent_port: int = 9000, parent=None):
        super().__init__(parent)
        self.db_path     = db_path
        self.pc_name     = pc_name
        self.parent_ip   = parent_ip
        self.parent_port = parent_port
        self.setWindowTitle("User Login")
        self.setFixedSize(380, 320)
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setStyleSheet("""
            QDialog   { background:#0d0d1a; color:#eee; }
            QLabel    { color:#ccc; font-size:13px; }
            QLineEdit { background:#16213e; color:#eee; border:1px solid #333;
                        border-radius:4px; padding:6px; font-size:13px; }
            QPushButton { background:#0f3460; color:#fff; border-radius:6px;
                          padding:8px 20px; font-weight:bold; font-size:13px; }
            QPushButton:hover { background:#1a5276; }
            QPushButton#reg { background:#1a3a1a; }
            QPushButton#reg:hover { background:#27ae60; }
        """)
        self.stack = QStackedWidget()
        self.stack.addWidget(self._login_page())
        self.stack.addWidget(self._register_page())
        layout = QVBoxLayout(self)
        layout.addWidget(self.stack)

    def _login_page(self):
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(12)
        form.setContentsMargins(24, 20, 24, 12)
        title = QLabel("User Login")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color:#00e5ff;")
        form.addRow(title)
        self.login_user_edit = QLineEdit()
        self.login_user_edit.setPlaceholderText("Username")
        form.addRow("Username:", self.login_user_edit)
        self.login_pw_edit = QLineEdit()
        self.login_pw_edit.setEchoMode(QLineEdit.Password)
        self.login_pw_edit.setPlaceholderText("Password")
        form.addRow("Password:", self.login_pw_edit)
        self.login_msg = QLabel("")
        self.login_msg.setStyleSheet("color:#ff6060;")
        form.addRow(self.login_msg)
        btn_row = QHBoxLayout()
        login_btn = QPushButton("Login")
        login_btn.clicked.connect(self._do_login)
        reg_btn = QPushButton("Register")
        reg_btn.setObjectName("reg")
        reg_btn.clicked.connect(lambda: self.stack.setCurrentIndex(1))
        btn_row.addWidget(login_btn)
        btn_row.addWidget(reg_btn)
        form.addRow(btn_row)
        return page

    def _register_page(self):
        page = QWidget()
        form = QFormLayout(page)
        form.setSpacing(12)
        form.setContentsMargins(24, 20, 24, 12)
        title = QLabel("Create Account")
        title.setFont(QFont("Segoe UI", 16, QFont.Bold))
        title.setStyleSheet("color:#00e5ff;")
        form.addRow(title)
        self.reg_user_edit = QLineEdit()
        self.reg_user_edit.setPlaceholderText("Username")
        form.addRow("Username:", self.reg_user_edit)
        self.reg_pw_edit = QLineEdit()
        self.reg_pw_edit.setEchoMode(QLineEdit.Password)
        self.reg_pw_edit.setPlaceholderText("Password")
        form.addRow("Password:", self.reg_pw_edit)
        self.reg_pw2_edit = QLineEdit()
        self.reg_pw2_edit.setEchoMode(QLineEdit.Password)
        self.reg_pw2_edit.setPlaceholderText("Confirm Password")
        form.addRow("Confirm:", self.reg_pw2_edit)
        self.reg_msg = QLabel("")
        self.reg_msg.setStyleSheet("color:#ff6060;")
        form.addRow(self.reg_msg)
        btn_row = QHBoxLayout()
        reg_btn = QPushButton("Register")
        reg_btn.setObjectName("reg")
        reg_btn.clicked.connect(self._do_register)
        back_btn = QPushButton("Back")
        back_btn.clicked.connect(lambda: self.stack.setCurrentIndex(0))
        btn_row.addWidget(reg_btn)
        btn_row.addWidget(back_btn)
        form.addRow(btn_row)
        return page

    def _do_login(self):
        from shared.db import login_user, consume_user_time
        username = self.login_user_edit.text().strip()
        password = self.login_pw_edit.text()
        if not username or not password:
            self.login_msg.setText("Please fill in all fields.")
            return
        ok, user = login_user(username, password, self.db_path)
        if not ok:
            self.login_msg.setText("Invalid username or password.")
            return
        seconds = consume_user_time(username, self.pc_name, self.db_path)
        if self.parent_ip:
            self._sync_consume_parent(username)
        self.login_success.emit(username, seconds)
        self.accept()

    def _do_register(self):
        from shared.db import register_user
        username = self.reg_user_edit.text().strip()
        password = self.reg_pw_edit.text()
        confirm  = self.reg_pw2_edit.text()
        if not username or not password:
            self.reg_msg.setText("Please fill in all fields.")
            return
        if password != confirm:
            self.reg_msg.setText("Passwords do not match.")
            return
        if len(password) < 4:
            self.reg_msg.setText("Password must be at least 4 characters.")
            return
        ok, msg = register_user(username, password, self.db_path)
        if ok:
            self.register_success.emit(username)
            self.accept()
        else:
            self.reg_msg.setText(msg)

    def _sync_consume_parent(self, username: str):
        try:
            from shared.protocol import encode, CMD_SAVE_USER
            import socket
            msg = {"cmd": CMD_SAVE_USER, "username": username,
                   "seconds": 0, "pc_name": self.pc_name}
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(2)
                s.connect((self.parent_ip, self.parent_port))
                s.sendall(encode(msg))
        except Exception:
            pass


# ─────────────────────────────────────────────────────────────────────────────
class FullscreenOverlay(QWidget):
    admin_requested = pyqtSignal()
    login_success   = pyqtSignal(str, int)
    settings_saved  = pyqtSignal(dict)
    timer_add_time  = pyqtSignal(int)
    timer_stop      = pyqtSignal()
    timer_reset     = pyqtSignal()

    _DEFAULT_WALLPAPER = os.path.normpath(
        os.path.join(os.path.dirname(__file__), '..', '..', 'assets',
                     'luffy_nika_live_wallpaper.mp4'))

    def __init__(self, pc_name: str, shop_name: str = "PC Cafe",
                 admin_keyword: str = "grefin",
                 shutdown_seconds: int = 180,
                 db_path: str = "",
                 parent_ip: str = "",
                 parent_port: int = 9000,
                 config: dict = None,
                 parent=None):
        super().__init__(parent)
        self.pc_name             = pc_name
        self.shop_name           = shop_name
        self.admin_keyword       = admin_keyword
        self.shutdown_seconds    = shutdown_seconds
        self._shutdown_remaining = shutdown_seconds
        self.db_path             = db_path
        self.parent_ip           = parent_ip
        self.parent_port         = parent_port
        self._config             = config or {}
        self._background_type    = (config or {}).get("background_type", "Live Wallpaper")
        self._background_path    = (config or {}).get("background_path", "")

        self._player      = None   # QMediaPlayer for video
        self._gif_movie   = None   # QMovie for gif background

        # Shop name animation
        self._shop_animation_type = (config or {}).get("shop_animation", "None")
        self._shop_anim_speed = (config or {}).get("shop_anim_speed", 500)
        self._shop_base_color = (config or {}).get("shop_color", "#00e5ff")
        self._shop_anim_timer = QTimer(self)
        self._shop_anim_timer.timeout.connect(self._animate_shop_name)
        self._shop_anim_step = 0
        self._shop_full_text = shop_name
        self._shop_display_text = shop_name

        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.SplashScreen)
        # In Windows, this removes taskbar entry; still can't prevent Task Manager kill.
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, False)
        self.setAttribute(Qt.WA_DeleteOnClose, False)
        self._build_ui()

        # dev_mode: disable actual OS shutdown during development/testing
        self.dev_mode = bool((config or {}).get("dev_mode", False) or os.getenv("PISONET_TIMER_DEV_MODE", "0") in ("1", "true", "True", "yes", "YES"))

        self._shutdown_timer = QTimer(self)
        self._shutdown_timer.timeout.connect(self._shutdown_tick)

    # ── UI ───────────────────────────────────────────────────────
    def _build_ui(self):
        # QStackedLayout with StackAll so both layers are visible at once
        stack = QStackedLayout(self)
        stack.setStackingMode(QStackedLayout.StackAll)

        # ── Layer 0: background ──────────────────────────────────
        self._bg_container = QWidget(self)
        self._bg_container.setStyleSheet("background:#0d0d1a;")
        bg_layout = QVBoxLayout(self._bg_container)
        bg_layout.setContentsMargins(0, 0, 0, 0)

        # Video widget — hidden until a video is loaded
        self._video_widget = QVideoWidget(self._bg_container)
        self._video_widget.setStyleSheet("background:#000;")
        self._video_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._video_widget.hide()
        bg_layout.addWidget(self._video_widget)

        # GIF label — hidden until a gif is loaded
        self._gif_label = QLabel(self._bg_container)
        self._gif_label.setScaledContents(True)
        self._gif_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._gif_label.setStyleSheet("background:#000;")
        self._gif_label.hide()
        bg_layout.addWidget(self._gif_label)

        # Static image label
        self._img_label = QLabel(self._bg_container)
        self._img_label.setScaledContents(True)
        self._img_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self._img_label.setStyleSheet("background:#000;")
        self._img_label.hide()
        bg_layout.addWidget(self._img_label)

        stack.addWidget(self._bg_container)

        # ── Layer 1: UI content (transparent background) ─────────
        ui_container = QWidget(self)
        ui_container.setAttribute(Qt.WA_TranslucentBackground)
        ui_container.setStyleSheet("background:transparent;")
        self._build_ui_content(ui_container)
        stack.addWidget(ui_container)

        # Show the UI layer on top
        stack.setCurrentWidget(ui_container)

    def _build_ui_content(self, parent: QWidget):
        root = QVBoxLayout(parent)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Top bar
        top_bar = QHBoxLayout()
        self._pc_label = QLabel(self.pc_name)
        self._pc_label.setFont(QFont("Segoe UI", 13, QFont.Bold))
        self._pc_label.setStyleSheet("color:#031cfc; padding:12px; background:transparent;")
        top_bar.addWidget(self._pc_label)
        top_bar.addStretch()

        self._admin_btn = QPushButton("⚙  Admin")
        self._admin_btn.setFixedSize(110, 36)
        self._admin_btn.setStyleSheet(
            "background:rgba(26,26,46,200); color:#aaa; border:1px solid #2a2a4a;"
            "border-radius:6px; font-size:13px; margin:8px;")
        self._admin_btn.clicked.connect(self._on_admin_clicked)
        top_bar.addWidget(self._admin_btn)

        # Center
        center = QVBoxLayout()
        center.setAlignment(Qt.AlignCenter)
        center.setSpacing(16)

        self._shop_label = QLabel(self.shop_name)
        self._shop_label.setFont(QFont("Segoe UI", 34, QFont.Bold))
        self._shop_label.setStyleSheet("color:#ffffff; background:transparent;")
        self._shop_label.setAlignment(Qt.AlignCenter)

        self._anim_label = QLabel("[ Animation ]")
        self._anim_label.setAlignment(Qt.AlignCenter)
        self._anim_label.setAttribute(Qt.WA_TranslucentBackground)
        self._anim_label.setStyleSheet(
            "color:#aaa; font-size:13px; background:transparent;")
        self._anim_label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        insert_label = QLabel("Insert Coin")
        insert_label.setFont(QFont("Segoe UI", 52, QFont.Bold))
        insert_label.setStyleSheet("color:#f0c040; letter-spacing:4px; background:transparent;")
        insert_label.setAlignment(Qt.AlignCenter)

        self._shutdown_label = QLabel("")
        self._shutdown_label.setFont(QFont("Segoe UI", 16))
        self._shutdown_label.setStyleSheet("color:#ff6060; background:transparent;")
        self._shutdown_label.setAlignment(Qt.AlignCenter)

        self._com_status_label = QLabel("COM Status: Unknown")
        self._com_status_label.setFont(QFont("Segoe UI", 14, QFont.Bold))
        self._com_status_label.setStyleSheet(
            "color:#00ff00; background:rgba(0,0,0,120); border-radius:10px;"
            "padding:6px 14px;")
        self._com_status_label.setAlignment(Qt.AlignCenter)

        center.addWidget(self._shop_label)
        center.addWidget(self._anim_label, alignment=Qt.AlignCenter)
        center.addWidget(insert_label)
        center.addWidget(self._shutdown_label)
        center.addWidget(self._com_status_label, alignment=Qt.AlignCenter)

        # Start shop name animation if enabled
        self._start_shop_animation()

        # Bottom bar
        bottom_bar = QHBoxLayout()
        bottom_bar.setContentsMargins(24, 0, 24, 24)

        self._shutdown_btn = QPushButton("Shutdown")
        self._shutdown_btn.setFixedSize(130, 42)
        self._shutdown_btn.setStyleSheet(
            "background:rgba(58,26,26,200); color:#ff6060; border:2px solid #ff4040;"
            "border-radius:8px; font-size:14px; font-weight:bold;"
        )
        self._shutdown_btn.setToolTip("Shutdown")
        self._shutdown_btn.clicked.connect(self._on_shutdown_clicked)

        self._login_btn = QPushButton("⮕  Login")
        self._login_btn.setFixedSize(130, 42)
        self._login_btn.setStyleSheet(
            "background:rgba(30,58,95,200); color:#aad4ff; border-radius:8px;"
            "font-size:14px; font-weight:bold;")
        self._login_btn.clicked.connect(self._on_login_clicked)

        bottom_bar.addWidget(self._shutdown_btn, alignment=Qt.AlignBottom)
        bottom_bar.addStretch()
        bottom_bar.addWidget(self._login_btn, alignment=Qt.AlignBottom)

        root.addLayout(top_bar)
        root.addLayout(center, stretch=1)
        root.addLayout(bottom_bar)

    # ── background ───────────────────────────────────────────────
    def _stop_background(self):
        if hasattr(self, '_player') and self._player:
            self._player.stop()
            self._player = None
        if hasattr(self, '_video_fallback_timer') and getattr(self, '_video_fallback_timer', None):
            self._video_fallback_timer.stop()
            self._video_fallback_timer = None
        if hasattr(self, '_video_fallback_cap') and getattr(self, '_video_fallback_cap', None):
            self._video_fallback_cap.release()
            self._video_fallback_cap = None
        if self._gif_movie:
            self._gif_movie.stop()
            self._gif_movie = None
        self._video_widget.hide()
        self._gif_label.hide()
        self._img_label.hide()

    def _play_video(self, path: str):
        self._bg_container.setStyleSheet("background:#000;")
        self._video_widget.setGeometry(self._bg_container.rect())
        self._video_widget.show()
        self._video_widget.raise_()

        self._playback_path = path

        self._player = QMediaPlayer(self)
        self._player.setVideoOutput(self._video_widget)
        self._player.setVolume(0)
        self._player.setMedia(QMediaContent(QUrl.fromLocalFile(os.path.abspath(path))))
        self._player.mediaStatusChanged.connect(self._on_video_status)
        self._player.error.connect(self._on_video_error)
        self._player.play()

    def _on_video_status(self, status):
        if status == QMediaPlayer.EndOfMedia and self._player:
            self._player.setPosition(0)
            self._player.play()
        if status in (QMediaPlayer.InvalidMedia, QMediaPlayer.NoMedia):
            self._on_video_error()

    def _on_video_error(self, *args):
        err = "unknown" if not getattr(self, '_player', None) else self._player.errorString()
        print(f"[FullscreenOverlay] QMediaPlayer error: {err}")

        self._stop_background()
        self._bg_container.setStyleSheet("background:#0d0d1a;")

        if hasattr(self, '_playback_path') and self._playback_path.lower().endswith('.mp4'):
            self._play_video_cv(self._playback_path)
            return

        self._img_label.setText("Video unavailable")
        self._img_label.setStyleSheet("color:#fff; font-size:24px; background:#0d0d1a;")
        self._img_label.show()

    def _play_video_cv(self, path: str):
        if not OPENCV_AVAILABLE:
            print("[FullscreenOverlay] OpenCV not installed; cannot play MP4.")
            self._bg_container.setStyleSheet("background:#0d0d1a;")
            return

        cap = cv2.VideoCapture(path)
        if not cap.isOpened():
            print(f"[FullscreenOverlay] OpenCV cannot open {path}")
            cap.release()
            self._bg_container.setStyleSheet("background:#0d0d1a;")
            return

        self._video_fallback_cap = cap
        fps = cap.get(cv2.CAP_PROP_FPS) or 24
        self._video_fallback_timer = QTimer(self)
        self._video_fallback_timer.timeout.connect(self._play_video_cv_frame)
        self._video_fallback_timer.start(max(20, int(1000 / fps)))

        self._bg_container.setStyleSheet("background:#000;")
        self._img_label.show()
        self._img_label.raise_()

    def _play_video_cv_frame(self):
        cap = getattr(self, '_video_fallback_cap', None)
        if not cap:
            return

        ret, frame = cap.read()
        if not ret:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            return

        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, c = frame.shape
        qimg = QImage(frame.data, w, h, w * c, QImage.Format_RGB888)
        pix = QPixmap.fromImage(qimg).scaled(
            self._bg_container.size(), Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        self._img_label.setPixmap(pix)

    def _apply_background(self):
        self._stop_background()
        bg_type = self._background_type
        path    = self._background_path

        if bg_type == "Solid Color":
            self._bg_container.setStyleSheet("background:#0d0d1a;")

        elif bg_type == "Static Picture":
            if path and os.path.exists(path):
                pix = QPixmap(path)
                if not pix.isNull():
                    self._img_label.setPixmap(pix)
                    self._img_label.show()
                    self._bg_container.setStyleSheet("background:#000;")
            else:
                self._bg_container.setStyleSheet("background:#0d0d1a;")

        elif bg_type == "Live Wallpaper":
            if not path or not os.path.exists(path):
                path = self._DEFAULT_WALLPAPER
            if path and os.path.exists(path):
                ext = path.lower().rsplit('.', 1)[-1]
                if ext in ('mp4', 'avi', 'mov', 'mkv', 'webm'):
                    self._play_video_cv(path)  # Use OpenCV by default for better reliability
                elif ext == 'gif':
                    self._play_gif(path)
                else:
                    pix = QPixmap(path)
                    if not pix.isNull():
                        self._img_label.setPixmap(pix)
                        self._img_label.show()
            else:
                self._bg_container.setStyleSheet("background:#0d0d1a;")


    def _play_gif(self, path: str):
        self._bg_container.setStyleSheet("background:#000;")
        self._gif_movie = QMovie(path)
        self._gif_label.setMovie(self._gif_movie)
        self._gif_label.show()
        self._gif_movie.start()

    # ── public API ───────────────────────────────────────────────
    def show_and_lock(self):
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen)
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        self._apply_background()
        self._reset_shutdown()

        if self.dev_mode:
            self._shutdown_label.setText("Dev mode active: automatic shutdown is disabled")
        else:
            self._shutdown_timer.start(1000)

    def hide_overlay(self):
        self._shutdown_timer.stop()
        self._stop_background()
        self.hide()

    def pause_shutdown(self):
        self._shutdown_timer.stop()

    def resume_shutdown(self):
        if not self.isHidden():
            self._shutdown_timer.start(1000)

    def reset_shutdown(self):
        self._reset_shutdown()

    def set_animation(self, path: str):
        if not path:
            return
        if path.lower().endswith(".gif"):
            movie = QMovie(path)
            movie.start()
            # Wait for the first frame to load
            movie.jumpToFrame(0)
            pixmap = movie.currentPixmap()
            if not pixmap.isNull():
                gif_size = pixmap.size()
                self._anim_label.setFixedSize(gif_size)
            else:
                # Fallback to a reasonable size if dimensions can't be determined
                self._anim_label.setFixedSize(240, 190)
            self._anim_label.setMovie(movie)
            movie.start()
        else:
            pix = QPixmap(path)
            if not pix.isNull():
                # Use the actual image size
                img_size = pix.size()
                self._anim_label.setFixedSize(img_size)
                self._anim_label.setPixmap(pix)
            else:
                # Fallback for invalid images
                self._anim_label.setFixedSize(240, 190)

    def set_com_status(self, status: str, ok: bool = True):
        self._com_status_label.setText(f"COM Status: {status}")
        if ok:
            self._com_status_label.setStyleSheet(
                "color:#00ff00; background:rgba(0, 80, 0, 180); border-radius:10px; padding:6px 14px;")
        else:
            self._com_status_label.setStyleSheet(
                "color:#ff5555; background:rgba(100, 0, 0, 180); border-radius:10px; padding:6px 14px;")

    # ── shutdown countdown ───────────────────────────────────────
    def _reset_shutdown(self):
        self._shutdown_remaining = self.shutdown_seconds
        self._update_shutdown_label()

    def _shutdown_tick(self):
        self._shutdown_remaining -= 1
        self._update_shutdown_label()
        if self._shutdown_remaining <= 0:
            self._shutdown_timer.stop()
            self._do_shutdown()

    def _update_shutdown_label(self):
        r = self._shutdown_remaining
        self._shutdown_label.setText(
            "Shutting down..." if r <= 0 else f"Shutting down in  {r}s")

    def _do_shutdown(self):
        if self.dev_mode:
            print("[FullscreenOverlay] dev_mode enabled, skipping OS shutdown")
            self._shutdown_label.setText("Dev mode: shutdown suppressed")
            return

        if sys.platform == "win32":
            subprocess.Popen(["shutdown", "/s", "/t", "0"])
        else:
            subprocess.Popen(["shutdown", "-h", "now"])

    # ── Shop name animation ──────────────────────────────────────
    def _start_shop_animation(self):
        self._shop_anim_timer.stop()
        self._shop_full_text = self.shop_name
        self._shop_display_text = self.shop_name
        self._shop_anim_step = 0

        if self._shop_animation_type == "None":
            self._shop_label.setStyleSheet(f"color:{self._shop_base_color}; background:transparent;")
            self._shop_label.setText(self._shop_full_text)
            return

        self._shop_anim_timer.setInterval(self._shop_anim_speed)
        self._shop_anim_timer.start()

    def _animate_shop_name(self):
        if self._shop_animation_type == "Rainbow":
            self._animate_rainbow()
        elif self._shop_animation_type == "Pulse":
            self._animate_pulse()
        elif self._shop_animation_type == "Glow":
            self._animate_glow()
        elif self._shop_animation_type == "Color Cycle":
            self._animate_color_cycle()
        elif self._shop_animation_type == "Typewriter":
            self._animate_typewriter()

    def _animate_rainbow(self):
        colors = ["#ff0000", "#ff8000", "#ffff00", "#80ff00", "#00ff00", "#00ff80", "#00ffff", "#0080ff", "#0000ff", "#8000ff", "#ff00ff", "#ff0080"]
        color = colors[self._shop_anim_step % len(colors)]
        self._shop_label.setStyleSheet(f"color:{color}; background:transparent;")
        self._shop_anim_step += 1

    def _animate_pulse(self):
        # Pulse between base color and white
        intensity = abs((self._shop_anim_step % 20) - 10) / 10.0  # 0 to 1
        if intensity < 0.5:
            color = self._mix_colors(self._shop_base_color, "#ffffff", intensity * 2)
        else:
            color = self._mix_colors("#ffffff", self._shop_base_color, (intensity - 0.5) * 2)
        self._shop_label.setStyleSheet(f"color:{color}; background:transparent;")
        self._shop_anim_step += 1

    def _animate_glow(self):
        # Glow effect with text shadow
        intensity = (self._shop_anim_step % 20) / 19.0  # 0 to 1
        glow_color = self._lighten_color(self._shop_base_color, 0.5)
        shadow = f"text-shadow: 0 0 {int(10 * intensity)}px {glow_color};"
        self._shop_label.setStyleSheet(f"color:{self._shop_base_color}; background:transparent; {shadow}")
        self._shop_anim_step += 1

    def _animate_color_cycle(self):
        # Cycle through different colors
        colors = ["#ff4444", "#44ff44", "#4444ff", "#ffff44", "#ff44ff", "#44ffff"]
        color = colors[self._shop_anim_step % len(colors)]
        self._shop_label.setStyleSheet(f"color:{color}; background:transparent;")
        self._shop_anim_step += 1

    def _animate_typewriter(self):
        # Typewriter effect
        if self._shop_anim_step < len(self._shop_full_text):
            self._shop_display_text = self._shop_full_text[:self._shop_anim_step + 1]
            self._shop_label.setText(self._shop_display_text)
            self._shop_anim_step += 1
        else:
            # Pause at full text, then restart
            if self._shop_anim_step > len(self._shop_full_text) + 10:  # Pause for 10 cycles
                self._shop_anim_step = 0
                self._shop_display_text = ""
            else:
                self._shop_anim_step += 1

    def _mix_colors(self, color1, color2, ratio):
        """Mix two colors with given ratio (0-1)"""
        c1 = QColor(color1)
        c2 = QColor(color2)
        r = int(c1.red() * (1 - ratio) + c2.red() * ratio)
        g = int(c1.green() * (1 - ratio) + c2.green() * ratio)
        b = int(c1.blue() * (1 - ratio) + c2.blue() * ratio)
        return f"#{r:02x}{g:02x}{b:02x}"

    def _lighten_color(self, color, factor):
        """Lighten a color by factor (0-1)"""
        c = QColor(color)
        r = min(255, int(c.red() + (255 - c.red()) * factor))
        g = min(255, int(c.green() + (255 - c.green()) * factor))
        b = min(255, int(c.blue() + (255 - c.blue()) * factor))
        return f"#{r:02x}{g:02x}{b:02x}"

    def _on_shutdown_clicked(self):
        msg = QMessageBox()
        msg.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        msg.setWindowTitle("Shutdown")
        msg.setText("⏻  Shutdown button was pressed.\n\nConfirm to shut down this PC.")
        msg.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg.setDefaultButton(QMessageBox.No)
        msg.button(QMessageBox.Yes).setText("Shut Down")
        msg.button(QMessageBox.No).setText("Cancel")
        if msg.exec_() == QMessageBox.Yes:
            self._do_shutdown()

    # ── admin ────────────────────────────────────────────────────
    def _on_admin_clicked(self):
        self.pause_shutdown()
        pw_dlg = AdminPasswordDialog()
        if pw_dlg.exec_() != QDialog.Accepted:
            self.reset_shutdown()
            self.resume_shutdown()
            return
        if pw_dlg.password() != self._config.get("admin_password", "admin"):
            err = QMessageBox()
            err.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
            err.setWindowTitle("Access Denied")
            err.setText("Incorrect password.")
            err.exec_()
            self.reset_shutdown()
            self.resume_shutdown()
            return

        from child.ui.settings_modal import ChildSettingsModal
        modal = ChildSettingsModal(self._config, db_path=self.db_path)
        modal.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        modal.settings_saved.connect(self._on_settings_saved)
        modal.timer_add_time.connect(self._on_timer_add_time)
        modal.timer_stop.connect(self._on_timer_stop)
        modal.timer_reset.connect(self._on_timer_reset)
        modal.exec_()

        self.reset_shutdown()
        self.resume_shutdown()

    def _on_settings_saved(self, new_cfg: dict):
        self._config.update(new_cfg)
        self.shop_name        = new_cfg.get("shop_name", self.shop_name)
        self.pc_name          = new_cfg.get("pc_name", self.pc_name)
        self.admin_keyword    = new_cfg.get("admin_keyword", self.admin_keyword)
        self.shutdown_seconds = new_cfg.get("shutdown_countdown", self.shutdown_seconds)
        self._background_type = new_cfg.get("background_type", self._background_type)
        self._background_path = new_cfg.get("background_path", self._background_path)
        self.dev_mode         = bool(new_cfg.get("dev_mode", self.dev_mode))

        # Update shop animation settings
        self._shop_animation_type = new_cfg.get("shop_animation", "None")
        self._shop_anim_speed = new_cfg.get("shop_anim_speed", 500)
        self._shop_base_color = new_cfg.get("shop_color", "#00e5ff")

        self._shop_label.setText(self.shop_name)
        self._pc_label.setText(self.pc_name)
        self._apply_background()
        self._start_shop_animation()  # Restart animation with new settings
        if new_cfg.get("animation_path"):
            self.set_animation(new_cfg["animation_path"])
        self.settings_saved.emit(new_cfg)

    def _on_timer_add_time(self, seconds: int):
        self.timer_add_time.emit(seconds)

    def _on_timer_stop(self):
        self.timer_stop.emit()

    def _on_timer_reset(self):
        self.timer_reset.emit()

    # ── login ────────────────────────────────────────────────────
    def _on_login_clicked(self):
        self._shutdown_timer.stop()
        dlg = LoginDialog(self.db_path, self.pc_name, self.parent_ip, self.parent_port)
        dlg.login_success.connect(self._on_login_result)
        dlg.register_success.connect(
            lambda u: QMessageBox.information(None, "Registered",
                f"Account '{u}' created. You can now log in."))
        dlg.exec_()
        if not self.isHidden():
            self._shutdown_timer.start(1000)

    def _on_login_result(self, username: str, seconds: int):
        self.login_success.emit(username, seconds)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Update video scaling when window is resized
        if hasattr(self, '_video_fallback_cap') and self._video_fallback_cap and self._img_label.isVisible():
            # Force a frame update to rescale the video
            self._play_video_cv_frame()

    def closeEvent(self, event):
        event.ignore()

    def force_close(self):
        self._shutdown_timer.stop()
        self.closeEvent = lambda e: e.accept()
        self.close()


# ─────────────────────────────────────────────────────────────────────────────
class DraggableTimer(QWidget):
    settings_requested = pyqtSignal()

    def __init__(self, pc_name: str, config: dict = None, parent=None):
        super().__init__(parent)
        self.pc_name     = pc_name
        self._config     = config or {}
        self._drag_pos   = None
        self._mini       = False
        self._drag_moved = False
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool | Qt.SplashScreen)
        self.setWindowFlag(Qt.WindowCloseButtonHint, False)
        self.setWindowFlag(Qt.WindowMinimizeButtonHint, False)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowTitle(f"{self.pc_name} Timer")
        self._build_ui()
        self._position_default()


    def _build_ui(self):
        self.setStyleSheet("background:rgba(13,13,26,210); border-radius:10px;")
        self.setFixedSize(220, 110)

        self.time_label = QLabel("00:00:00")
        self.time_label.setFont(QFont("Segoe UI", 26, QFont.Bold))
        self.time_label.setStyleSheet("color:#00e5ff;")
        self.time_label.setAlignment(Qt.AlignCenter)

        self.status_label = QLabel(f"{self.pc_name}  |  Coins: 0")
        self.status_label.setFont(QFont("Segoe UI", 9))
        self.status_label.setStyleSheet("color:#888;")
        self.status_label.setAlignment(Qt.AlignCenter)

        self._com_status_label = QLabel("COM: Unknown")
        self._com_status_label.setFont(QFont("Segoe UI", 8))
        self._com_status_label.setStyleSheet("color:#aaaaaa;")
        self._com_status_label.setAlignment(Qt.AlignCenter)

        self._settings_btn = QPushButton("⚙")
        self._settings_btn.setFixedSize(28, 28)
        self._settings_btn.setStyleSheet(
            "background:transparent; color:#00e5ff; font-size:16px;")
        self._settings_btn.clicked.connect(self._on_settings_clicked)

        self._mini_btn = QPushButton("🗕")
        self._mini_btn.setFixedSize(28, 28)
        self._mini_btn.setStyleSheet(
            "background:transparent; color:#00e5ff; font-size:16px;")
        self._mini_btn.clicked.connect(self._go_mini)

        top = QHBoxLayout()
        top.addStretch()
        top.addWidget(self._settings_btn)
        top.addWidget(self._mini_btn)
        top.setContentsMargins(0, 4, 4, 0)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 0, 8, 8)
        layout.addLayout(top)
        layout.addWidget(self.time_label)
        layout.addWidget(self.status_label)
        layout.addWidget(self._com_status_label)

    # ── public ───────────────────────────────────────────────────
    def update_time(self, time_str: str):
        self.time_label.setText(time_str)
        self.setWindowTitle(f"{self.pc_name} Timer  |  {time_str}")

    def update_status(self, coins: int, username: str = ""):
        user_part = f"  [{username}]" if username else ""
        self.status_label.setText(f"{self.pc_name}{user_part}  |  Coins: {coins}")

    def set_com_status(self, status: str, ok: bool = True):
        self._com_status_label.setText(f"COM: {status}")
        if ok:
            self._com_status_label.setStyleSheet("color:#00ff00;")
        else:
            self._com_status_label.setStyleSheet("color:#ff5555;")

    def start_blink(self):
        if not hasattr(self, '_blink_timer') or not self._blink_timer.isActive():
            self._blink_state = False
            self._blink_timer = QTimer(self)
            self._blink_timer.timeout.connect(self._blink)
            self._blink_timer.start(500)

    def stop_blink(self):
        if hasattr(self, '_blink_timer'):
            self._blink_timer.stop()
        self.time_label.setStyleSheet("color:#00e5ff;")

    # ── settings requested from draggable timer ───────────────────────
    def _on_settings_clicked(self):
        # Password challenge is handled by the main overlay (_on_admin_clicked)
        # to avoid double prompts when triggered from draggable and overlay.
        self.settings_requested.emit()

    # ── mini mode ────────────────────────────────────────────────
    def _go_mini(self):
        if self._mini:
            return
        self._mini = True
        self.setFixedSize(160, 32)
        self.setStyleSheet("background:rgba(13,13,26,200); border-radius:8px;")
        self.status_label.hide()
        self._settings_btn.hide()
        self._mini_btn.hide()
        self.time_label.setFont(QFont("Segoe UI", 13, QFont.Bold))
        screen = QApplication.primaryScreen().availableGeometry()
        self.move((screen.width() - 160) // 2, 0)

    def _go_normal(self):
        if not self._mini:
            return
        self._mini = False
        self.setFixedSize(220, 110)
        self.setStyleSheet("background:rgba(13,13,26,210); border-radius:10px;")
        self.status_label.show()
        self._settings_btn.show()
        self._mini_btn.show()
        self.time_label.setFont(QFont("Segoe UI", 26, QFont.Bold))
        self._position_default()

    def _position_default(self):
        screen = QApplication.primaryScreen().availableGeometry()
        self.move(screen.width() - 230, screen.height() - 120)

    # ── mouse events ─────────────────────────────────────────────
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_pos   = e.globalPos() - self.frameGeometry().topLeft()
            self._drag_moved = False

    def mouseMoveEvent(self, e):
        if e.buttons() == Qt.LeftButton and self._drag_pos and not self._mini:
            self._drag_moved = True
            self.move(e.globalPos() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton:
            if self._mini and not self._drag_moved:
                self._go_normal()
        self._drag_pos   = None
        self._drag_moved = False

    # ── blink ────────────────────────────────────────────────────
    def _blink(self):
        self._blink_state = not self._blink_state
        self.time_label.setStyleSheet(
            f"color:{'#ff4444' if self._blink_state else '#00e5ff'};")

    def closeEvent(self, e):
        e.ignore()
