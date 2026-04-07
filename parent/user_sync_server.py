"""TCP server on parent — receives SAVE_USER from child PCs and mirrors saved time into parent DB."""
import socket
import threading

from shared.protocol import decode, CMD_SAVE_USER
from shared.db import save_user_time


class UserSyncServer:
    def __init__(self, port: int = 9100):
        self.port = port
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._running = False

    def start(self):
        self._running = True
        self._thread.start()

    def stop(self):
        self._running = False

    def _serve(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                srv.bind(("0.0.0.0", self.port))
            except OSError as e:
                print(f"[UserSyncServer] bind failed on port {self.port}: {e}")
                return
            srv.listen(8)
            srv.settimeout(1.0)
            while self._running:
                try:
                    conn, _ = srv.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()

    def _handle_client(self, conn: socket.socket):
        try:
            conn.settimeout(5.0)
            buf = b""
            while b"\n" not in buf:
                chunk = conn.recv(4096)
                if not chunk:
                    return
                buf += chunk
                if len(buf) > 65536:
                    return
            msg = decode(buf)
            if msg.get("cmd") == CMD_SAVE_USER:
                username = msg.get("username") or ""
                seconds = int(msg.get("seconds", 0))
                pc_name = msg.get("pc_name") or ""
                if username:
                    save_user_time(username, seconds, pc_name)
        except Exception as e:
            print(f"[UserSyncServer] handle error: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass
