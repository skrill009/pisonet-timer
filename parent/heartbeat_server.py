"""
Parent heartbeat server — listens for child PC heartbeats and auto-discovers them.
"""
import socket, threading, time
from PyQt5.QtCore import QObject, pyqtSignal
from shared.protocol import decode, CMD_HEARTBEAT
from shared.db import upsert_pc

class HeartbeatServer(QObject):
    pc_discovered = pyqtSignal(dict)  # Emitted when a new PC is discovered

    def __init__(self, port=9001, parent=None):
        super().__init__(parent)
        self.port = port
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._running = False
        self._known_pcs = set()  # Track known PCs to avoid duplicate signals

    def start(self):
        self._running = True
        self._thread.start()

    def stop(self):
        self._running = False

    def _serve(self):
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind(("0.0.0.0", self.port))
            srv.settimeout(1.0)  # Allow checking _running flag

            while self._running:
                try:
                    data, addr = srv.recvfrom(4096)
                    msg = decode(data)
                    if msg.get("cmd") == CMD_HEARTBEAT:
                        self._handle_heartbeat(msg, addr[0])
                except socket.timeout:
                    continue
                except Exception as e:
                    print(f"Heartbeat server error: {e}")

    def _handle_heartbeat(self, msg, client_ip):
        pc_name = msg.get("pc_name")
        pc_ip = msg.get("ip", client_ip)
        pc_port = msg.get("port", 9000)
        status = msg.get("status", {})

        # Auto-add PC to database if not already known
        upsert_pc(pc_name, pc_ip, pc_port)

        # Emit signal if this is a new PC or status changed
        pc_key = f"{pc_name}:{pc_ip}:{pc_port}"
        if pc_key not in self._known_pcs:
            self._known_pcs.add(pc_key)
            self.pc_discovered.emit({
                "name": pc_name,
                "ip": pc_ip,
                "port": pc_port,
                "status": status,
                "last_seen": time.time()
            })