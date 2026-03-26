"""
Child heartbeat client — sends periodic status updates to parent.
"""
import socket, threading, time
from shared.protocol import encode, CMD_HEARTBEAT

class HeartbeatClient:
    def __init__(self, pc_name, parent_ip, parent_port, child_port=9000, status_callback=None):
        self.pc_name = pc_name
        self.parent_ip = parent_ip
        self.parent_port = parent_port  # Parent heartbeat port (9001)
        self.child_port = child_port    # Child TCP port (9000)
        self.status_callback = status_callback
        self._thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._running = False

    def start(self):
        self._running = True
        self._thread.start()

    def stop(self):
        self._running = False

    def _heartbeat_loop(self):
        while self._running:
            try:
                self._send_heartbeat()
            except Exception as e:
                print(f"Heartbeat error: {e}")
            time.sleep(30)  # Send heartbeat every 30 seconds

    def _send_heartbeat(self):
        status = {}
        if self.status_callback:
            status = self.status_callback()

        msg = {
            "cmd": CMD_HEARTBEAT,
            "pc_name": self.pc_name,
            "ip": self.parent_ip,  # Child's IP (will be overridden by parent)
            "port": self.child_port,
            "status": status
        }

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.sendto(encode(msg), (self.parent_ip, self.parent_port))