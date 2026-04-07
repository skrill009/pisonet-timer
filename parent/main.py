"""
Parent app entry point.
Run this on the admin PC.
"""
import sys
from PyQt5.QtWidgets import QApplication
from shared.db import init_db
from parent.ui.dashboard import DashboardWindow
from parent.heartbeat_server import HeartbeatServer
from parent.user_sync_server import UserSyncServer

def main():
    app = QApplication(sys.argv)
    
    # Set discrete process name for Task Manager obfuscation
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW("Windows Service Host")
        except Exception:
            pass
    
    init_db()

    heartbeat_server = HeartbeatServer(port=9001)
    heartbeat_server.start()

    user_sync_server = UserSyncServer(port=9100)
    user_sync_server.start()

    window = DashboardWindow()
    heartbeat_server.pc_discovered.connect(window.on_pc_discovered)
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
