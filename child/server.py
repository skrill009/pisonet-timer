"""
Child TCP server — listens for commands from the parent app.
Runs in a background QThread so it doesn't block the UI.
"""
import json, socket, threading
from PyQt5.QtCore import QObject, pyqtSignal
from shared.protocol import encode, decode, CMD_ADD_TIME, CMD_SET_TIME, CMD_END_SESSION, CMD_GET_STATUS, CMD_SHUTDOWN, CMD_SEND_MESSAGE, CMD_SET_SCHEDULE, RESP_STATUS, RESP_OK, RESP_ERROR

class ChildServer(QObject):
    command_received = pyqtSignal(dict)   # forwarded to main thread

    def __init__(self, timer_manager, host="0.0.0.0", port=9000, parent=None):
        super().__init__(parent)
        self.tm = timer_manager
        self.host = host
        self.port = port
        self._thread = threading.Thread(target=self._serve, daemon=True)

    def start(self):
        self._thread.start()

    def _serve(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((self.host, self.port))
            srv.listen(5)
            while True:
                try:
                    conn, _ = srv.accept()
                    threading.Thread(target=self._handle, args=(conn,), daemon=True).start()
                except Exception:
                    break

    def _handle(self, conn: socket.socket):
        with conn:
            try:
                data = b""
                while b"\n" not in data:
                    chunk = conn.recv(1024)
                    if not chunk:
                        return
                    data += chunk
                msg = decode(data)
                cmd = msg.get("cmd")

                if cmd == CMD_GET_STATUS:
                    resp = {"type": RESP_STATUS, **self.tm.status()}
                    conn.sendall(encode(resp))

                elif cmd == CMD_ADD_TIME:
                    self.command_received.emit({"cmd": CMD_ADD_TIME, "seconds": msg.get("seconds", 0)})
                    conn.sendall(encode({"type": RESP_OK}))

                elif cmd == CMD_SET_TIME:
                    self.command_received.emit({"cmd": CMD_SET_TIME, "seconds": msg.get("seconds", 0)})
                    conn.sendall(encode({"type": RESP_OK}))

                elif cmd == CMD_END_SESSION:
                    self.command_received.emit({"cmd": CMD_END_SESSION})
                    conn.sendall(encode({"type": RESP_OK}))

                elif cmd == CMD_SHUTDOWN:
                    self.command_received.emit({"cmd": CMD_SHUTDOWN})
                    conn.sendall(encode({"type": RESP_OK}))

                elif cmd == CMD_SEND_MESSAGE:
                    self.command_received.emit({
                        "cmd": CMD_SEND_MESSAGE,
                        "message": msg.get("message", ""),
                        "title": msg.get("title", "Message from Admin")
                    })
                    conn.sendall(encode({"type": RESP_OK}))

                elif cmd == CMD_SET_SCHEDULE:
                    self.command_received.emit({
                        "cmd": CMD_SET_SCHEDULE,
                        "enabled": msg.get("enabled", False),
                        "opening_hours": msg.get("opening_hours", "09:00"),
                        "closing_hours": msg.get("closing_hours", "23:00"),
                        "warning_minutes": msg.get("warning_minutes", 30),
                        "warning_message": msg.get("warning_message", "⚠ Shop is closing soon!"),
                        "closing_message": msg.get("closing_message", "Sorry, we are now closed!"),
                        "closing_logo_path": msg.get("closing_logo_path", "")
                    })
                    conn.sendall(encode({"type": RESP_OK}))

                else:
                    conn.sendall(encode({"type": RESP_ERROR, "msg": "Unknown command"}))
            except Exception as e:
                try:
                    conn.sendall(encode({"type": RESP_ERROR, "msg": str(e)}))
                except Exception:
                    pass
