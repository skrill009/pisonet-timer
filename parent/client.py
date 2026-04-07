"""
Parent-side TCP client — sends commands to a child PC and reads status.
"""
import socket
from shared.protocol import encode, decode, CMD_GET_STATUS, CMD_ADD_TIME, CMD_SET_TIME, CMD_END_SESSION, CMD_SHUTDOWN, CMD_SEND_MESSAGE, CMD_SET_SCHEDULE

TIMEOUT = 3  # seconds

def _send(ip: str, port: int, msg: dict) -> dict:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(TIMEOUT)
        s.connect((ip, port))
        s.sendall(encode(msg))
        data = b""
        while b"\n" not in data:
            chunk = s.recv(1024)
            if not chunk:
                break
            data += chunk
    return decode(data)

def get_status(ip: str, port: int = 9000) -> dict:
    try:
        return _send(ip, port, {"cmd": CMD_GET_STATUS})
    except Exception as e:
        return {"error": str(e), "active": False, "remaining": 0, "coins": 0}

def add_time(ip: str, port: int, seconds: int) -> dict:
    return _send(ip, port, {"cmd": CMD_ADD_TIME, "seconds": seconds})

def set_time(ip: str, port: int, seconds: int) -> dict:
    return _send(ip, port, {"cmd": CMD_SET_TIME, "seconds": seconds})

def end_session(ip: str, port: int) -> dict:
    return _send(ip, port, {"cmd": CMD_END_SESSION})

def shutdown_pc(ip: str, port: int) -> dict:
    return _send(ip, port, {"cmd": CMD_SHUTDOWN})

def send_message(ip: str, port: int, message: str, title: str = "Message from Admin") -> dict:
    return _send(ip, port, {"cmd": CMD_SEND_MESSAGE, "message": message, "title": title})

def set_schedule(ip: str, port: int, enabled: bool, opening_hours: str, closing_hours: str, 
                 warning_minutes: int, warning_message: str, closing_message: str = "", 
                 closing_logo_path: str = "") -> dict:
    return _send(ip, port, {
        "cmd": CMD_SET_SCHEDULE,
        "enabled": enabled,
        "opening_hours": opening_hours,
        "closing_hours": closing_hours,
        "warning_minutes": warning_minutes,
        "warning_message": warning_message,
        "closing_message": closing_message,
        "closing_logo_path": closing_logo_path
    })
