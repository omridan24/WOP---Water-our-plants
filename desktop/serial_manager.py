"""
WOP - Water Our Plants | Serial Connection Manager
Handles auto-detection and communication with the Arduino.
"""

import serial
import serial.tools.list_ports
import threading
import time
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class SensorData:
    soil_moisture: int = 0        # 0-1023 raw analog
    water_depth: int = 0          # 0-1023 raw analog
    pump_active: bool = False
    uptime_seconds: int = 0
    timestamp: float = field(default_factory=time.time)

    @property
    def soil_moisture_pct(self) -> float:
        """Convert raw analog (0-1023) to percentage."""
        return round((self.soil_moisture / 1023) * 100, 1)

    @property
    def water_depth_pct(self) -> float:
        """Convert raw analog (0-1023) to percentage."""
        return round((self.water_depth / 1023) * 100, 1)


class SerialManager:
    WOP_HANDSHAKE = "WOP:HELLO"
    BAUD_RATE = 9600
    
    def __init__(self):
        self.connection: Optional[serial.Serial] = None
        self.port_name: str = ""
        self.connected: bool = False
        self.latest_data: Optional[SensorData] = None
        self._read_thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._on_data: Optional[Callable[[SensorData], None]] = None
        self._on_connect: Optional[Callable[[str], None]] = None
        self._on_disconnect: Optional[Callable[[], None]] = None
        self._on_raw: Optional[Callable[[str], None]] = None
    
    def on_data(self, callback: Callable[[SensorData], None]):
        self._on_data = callback
    
    def on_connect(self, callback: Callable[[str], None]):
        self._on_connect = callback
    
    def on_disconnect(self, callback: Callable[[], None]):
        self._on_disconnect = callback

    def on_raw_message(self, callback: Callable[[str], None]):
        self._on_raw = callback

    @staticmethod
    def list_ports() -> list[dict]:
        """List all available COM ports with details."""
        ports = []
        for port in serial.tools.list_ports.comports():
            ports.append({
                "device": port.device,
                "description": port.description,
                "hwid": port.hwid,
                "vid": port.vid,
                "pid": port.pid,
            })
        return ports

    def auto_detect(self) -> Optional[str]:
        """Try to find a WOP Arduino by attempting handshake on each port."""
        for port_info in serial.tools.list_ports.comports():
            port = port_info.device
            try:
                test = serial.Serial(port, self.BAUD_RATE, timeout=3)
                time.sleep(2)  # Wait for Arduino reset after serial open
                
                # Read any handshake message
                deadline = time.time() + 4
                while time.time() < deadline:
                    if test.in_waiting:
                        line = test.readline().decode("utf-8", errors="ignore").strip()
                        if self.WOP_HANDSHAKE in line:
                            test.close()
                            return port
                test.close()
            except (serial.SerialException, OSError):
                continue
        return None

    def connect(self, port: str) -> bool:
        """Connect to a specific COM port."""
        try:
            self.connection = serial.Serial(port, self.BAUD_RATE, timeout=1)
            time.sleep(2)  # Wait for Arduino reset
            self.port_name = port
            self.connected = True
            
            # Start reading thread
            self._running = True
            self._read_thread = threading.Thread(target=self._read_loop, daemon=True)
            self._read_thread.start()
            
            if self._on_connect:
                self._on_connect(port)
            return True
        except (serial.SerialException, OSError) as e:
            print(f"Connection failed: {e}")
            return False

    def disconnect(self):
        """Close the serial connection."""
        self._running = False
        if self._read_thread:
            self._read_thread.join(timeout=2)
        if self.connection and self.connection.is_open:
            self.connection.close()
        self.connected = False
        self.port_name = ""
        if self._on_disconnect:
            self._on_disconnect()

    def send_command(self, command: str):
        """Send a command string to the Arduino."""
        if self.connection and self.connection.is_open:
            self.connection.write(f"{command}\n".encode("utf-8"))

    def _read_loop(self):
        """Background thread: read serial lines and parse WOP protocol."""
        while self._running:
            try:
                if self.connection and self.connection.in_waiting:
                    line = self.connection.readline().decode("utf-8", errors="ignore").strip()
                    if not line:
                        continue
                    
                    if self._on_raw:
                        self._on_raw(line)
                    
                    if line.startswith("WOP:DATA:"):
                        self._parse_data(line)
                else:
                    time.sleep(0.05)
            except (serial.SerialException, OSError):
                self._running = False
                self.connected = False
                if self._on_disconnect:
                    self._on_disconnect()
                break

    def _parse_data(self, line: str):
        """Parse a WOP:DATA: line into SensorData."""
        try:
            payload = line.replace("WOP:DATA:", "")
            parts = payload.split(",")
            if len(parts) >= 4:
                data = SensorData(
                    soil_moisture=int(parts[0]),
                    water_depth=int(parts[1]),
                    pump_active=parts[2] == "1",
                    uptime_seconds=int(parts[3]),
                )
                self.latest_data = data
                if self._on_data:
                    self._on_data(data)
        except (ValueError, IndexError) as e:
            print(f"Parse error: {e} | line: {line}")
