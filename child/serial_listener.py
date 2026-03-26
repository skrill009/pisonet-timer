"""
Listens on a serial COM port for coin pulses.
Each pulse triggers timer_manager.add_coin().
Runs in a background thread.
"""
import threading
from PyQt5.QtCore import QObject, pyqtSignal

class SerialListener(QObject):
    coin_inserted = pyqtSignal(int)   # emits pulse count
    status_changed = pyqtSignal(str, bool)  # status text, is_ok

    def __init__(self, port: str, baud: int = 9600, mode: str = "Auto", parent=None):
        super().__init__(parent)
        self.port = port
        self.baud = baud
        self.mode = mode  # Auto, Vout, Vin
        self._running = False
        self._thread = threading.Thread(target=self._listen, daemon=True)

    def start(self):
        self._running = True
        self._thread.start()

    def stop(self):
        self._running = False

    def _listen(self):
        try:
            import serial
            available_ports = [p.device for p in serial.tools.list_ports.comports()] if hasattr(serial, 'tools') else []
            if self.port and self.port not in available_ports:
                self.status_changed.emit(f"Port {self.port} not available", False)
            else:
                self.status_changed.emit("Ready", True)

            with serial.Serial(self.port, self.baud, timeout=1) as ser:
                self.status_changed.emit("Ready", True)
                while self._running:
                    line = ser.readline().decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue

                    # Normalize message type(s)
                    msg = line.upper()
                    pulses = None

                    if self.mode == "VOUT":
                        if msg.startswith("VOUT"):
                            parts = line.split(":", 1)
                            pulses = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
                    elif self.mode == "VIN":
                        if msg.startswith("VIN"):
                            parts = line.split(":", 1)
                            pulses = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
                    else:  # Auto
                        if msg.startswith("PULSE") or msg.startswith("VOUT") or msg.startswith("VIN"):
                            if ":" in line:
                                try:
                                    pulses = int(line.split(":", 1)[1])
                                except ValueError:
                                    pulses = 1
                            else:
                                pulses = 1
                        elif msg.isdigit():
                            pulses = int(msg)

                    if pulses is None:
                        continue

                    self.coin_inserted.emit(pulses)
        except Exception as e:
            print(f"[SerialListener] Error: {e}")
            self.status_changed.emit(f"Error: {e}", False)
