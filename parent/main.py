"""
Parent app entry point.
Run this on the admin PC.
"""
import sys
from PyQt5.QtWidgets import QApplication
from shared.db import init_db
from parent.ui.dashboard import DashboardWindow
from parent.heartbeat_server import HeartbeatServer

def main():
    app = QApplication(sys.argv)
    init_db()

    # Start heartbeat server to listen for child PCs
    heartbeat_server = HeartbeatServer(port=9001)
    heartbeat_server.start()

    window = DashboardWindow()
    heartbeat_server.pc_discovered.connect(window.on_pc_discovered)
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
