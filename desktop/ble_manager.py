"""
WOP - Water Our Plants | BLE Connection Manager
Handles Bluetooth Low Energy communication with the Arduino via Grove BLE (HM-11).
Uses the 'bleak' library for cross-platform BLE support.
"""

import asyncio
import platform
import sys
import threading
import traceback
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from bleak import BleakClient, BleakScanner

# On Windows, tkinter runs in STA mode which conflicts with bleak's WinRT backend.
# Uninitialize STA so bleak can use MTA in its own threads.
if platform.system() == "Windows":
    try:
        from bleak.backends.winrt.util import uninitialize_sta
        uninitialize_sta()
    except ImportError:
        pass  # Older bleak version or non-Windows

# HM-11 GATT UUIDs (standard for HM-10/HM-11 modules)
HM11_SERVICE_UUID = "0000ffe0-0000-1000-8000-00805f9b34fb"
HM11_CHAR_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

# Device names to search for (HM-11 defaults to "HMSoft")
KNOWN_DEVICE_NAMES = ["HMSoft", "WOP", "WOP-BLE", "Grove-BLE"]


@dataclass
class SensorData:
    """Shared data class — identical to serial_manager.SensorData."""
    soil_moisture: int = 0
    water_depth: int = 0
    pump_active: bool = False
    uptime_seconds: int = 0
    timestamp: float = field(default_factory=time.time)

    @property
    def soil_moisture_pct(self) -> float:
        return round((self.soil_moisture / 1023) * 100, 1)

    @property
    def water_depth_pct(self) -> float:
        return round((self.water_depth / 1023) * 100, 1)


class BLEManager:
    """
    Manages BLE connection to the WOP Arduino via an HM-11 module.

    Provides the same callback interface as SerialManager so the UI code
    can use either connection method interchangeably.
    """

    def __init__(self):
        self.connected: bool = False
        self.device_name: str = ""
        self.latest_data: Optional[SensorData] = None

        self._client: Optional[BleakClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False

        # Incoming data buffer (BLE packets are max ~20 bytes, so lines arrive split)
        self._rx_buffer: str = ""

        # Callbacks
        self._on_data: Optional[Callable[[SensorData], None]] = None
        self._on_connect: Optional[Callable[[str], None]] = None
        self._on_disconnect: Optional[Callable[[], None]] = None
        self._on_raw: Optional[Callable[[str], None]] = None

    # --- Callback registration (same API as SerialManager) ---

    def on_data(self, callback: Callable[[SensorData], None]):
        self._on_data = callback

    def on_connect(self, callback: Callable[[str], None]):
        self._on_connect = callback

    def on_disconnect(self, callback: Callable[[], None]):
        self._on_disconnect = callback

    def on_raw_message(self, callback: Callable[[str], None]):
        self._on_raw = callback

    # --- Scanning ---

    @staticmethod
    async def _scan_devices(timeout: float = 5.0) -> list[dict]:
        """Scan for nearby BLE devices and return a list of dicts."""
        devices = await BleakScanner.discover(timeout=timeout)
        result = []
        for d in devices:
            result.append({
                "name": d.name or "Unknown",
                "address": d.address,
                "rssi": d.rssi if hasattr(d, "rssi") else None,
            })
        return result

    def scan(self, timeout: float = 5.0) -> list[dict]:
        """Synchronous wrapper — scans for BLE devices."""
        return asyncio.run(self._scan_devices(timeout))

    @staticmethod
    async def _find_wop_device(timeout: float = 8.0):
        """Scan and return the first device matching known WOP/HMSoft names."""
        device = await BleakScanner.find_device_by_filter(
            lambda d, ad: d.name is not None and any(
                name.lower() in d.name.lower() for name in KNOWN_DEVICE_NAMES
            ),
            timeout=timeout,
        )
        return device

    # --- Connection ---

    def connect(self, address: Optional[str] = None):
        """
        Start BLE connection in a background thread.
        If address is None, auto-scans for a WOP device.
        """
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(
            target=self._run_event_loop,
            args=(address,),
            daemon=True,
        )
        self._thread.start()

    def _run_event_loop(self, address: Optional[str]):
        """Create a new asyncio event loop for BLE operations."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_and_listen(address))
        except Exception as e:
            err_msg = f"BLE event loop error: {type(e).__name__}: {e}"
            print(err_msg)
            traceback.print_exc()
            if self._on_raw:
                self._on_raw(err_msg)
        finally:
            self._loop.close()
            self._loop = None
            self._running = False
            if self.connected:
                self.connected = False
                if self._on_disconnect:
                    self._on_disconnect()

    async def _connect_and_listen(self, address: Optional[str]):
        """Core async: find device, connect, subscribe to notifications."""
        # Step 1: Find the device
        found_device = None  # The BLEDevice object from scanner
        if address:
            device_label = address
        else:
            if self._on_raw:
                self._on_raw("BLE: Scanning for WOP device...")
            found_device = await self._find_wop_device()
            if not found_device:
                if self._on_raw:
                    self._on_raw("BLE: No WOP device found. Make sure the Grove BLE module is powered.")
                return
            device_label = f"{found_device.name} ({found_device.address})"
            address = found_device.address
            if self._on_raw:
                self._on_raw(f"BLE: Found {device_label}")

        # Step 2: Connect
        # On Windows, we try different address types since the HM-11 may use
        # either public or random addressing depending on firmware.
        def on_disconnected(_client):
            self.connected = False
            if self._on_raw:
                self._on_raw("BLE: Disconnected")
            if self._on_disconnect:
                self._on_disconnect()
            self._running = False

        # Use the BLEDevice object if we have it (Windows needs the metadata),
        # otherwise fall back to the address string.
        connect_target = found_device if found_device else address

        # Try connection with different address types (Windows-specific fix)
        address_types = ["public", "random"] if platform.system() == "Windows" else [None]
        last_error = None

        for addr_type in address_types:
            try:
                kwargs = {}
                if platform.system() == "Windows" and addr_type:
                    kwargs["winrt"] = {"address_type": addr_type}
                    
                self._client = BleakClient(
                    connect_target,
                    disconnected_callback=on_disconnected,
                    **kwargs
                )
                if self._on_raw:
                    type_label = addr_type or "default"
                    self._on_raw(f"BLE: Attempting connection (address_type={type_label})...")
                await self._client.connect(timeout=15.0)
                if self._client.is_connected:
                    break  # Success!
            except Exception as e:
                last_error = e
                err_detail = repr(e) if not str(e) else str(e)
                if self._on_raw:
                    self._on_raw(f"BLE: Attempt with {addr_type or 'default'} failed — {err_detail}")
                continue

        if not self._client or not self._client.is_connected:
            if self._on_raw:
                err_detail = repr(last_error) if last_error and not str(last_error) else str(last_error)
                self._on_raw(f"BLE: All connection attempts failed — {err_detail}")
                self._on_raw("BLE: TIP — Try pairing 'HMSoft' in Windows Bluetooth Settings first, then retry.")
            return

        self.connected = True
        self.device_name = device_label

        if self._on_raw:
            self._on_raw(f"BLE: Connected to {self.device_name}")
        if self._on_connect:
            self._on_connect(f"BLE: {self.device_name}")

        # Step 3: Subscribe to notifications on FFE1
        try:
            await self._client.start_notify(HM11_CHAR_UUID, self._handle_rx)
        except Exception as e:
            if self._on_raw:
                self._on_raw(f"BLE: Failed to subscribe to notifications — {e}")
            await self._client.disconnect()
            return

        # Step 4: Keep alive until disconnected or stopped
        try:
            while self._running and self._client.is_connected:
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass
        finally:
            if self._client.is_connected:
                await self._client.stop_notify(HM11_CHAR_UUID)
                await self._client.disconnect()

    def _handle_rx(self, _sender, data: bytearray):
        """
        Called for each BLE notification (incoming data from Arduino).
        BLE packets are max ~20 bytes, so a single WOP:DATA: line may
        arrive across multiple notifications. Buffer until newline.
        """
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            return

        self._rx_buffer += text

        # Process all complete lines in the buffer
        while "\n" in self._rx_buffer:
            line, self._rx_buffer = self._rx_buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue

            if self._on_raw:
                self._on_raw(line)

            if line.startswith("WOP:DATA:"):
                self._parse_data(line)

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
            print(f"BLE parse error: {e} | line: {line}")

    # --- Sending commands ---

    def send_command(self, command: str):
        """Send a command string to the Arduino over BLE."""
        if not self.connected or not self._client or not self._loop:
            return

        async def _write():
            try:
                payload = f"{command}\n".encode("utf-8")
                # HM-11 FFE1 characteristic — write without response for speed
                await self._client.write_gatt_char(
                    HM11_CHAR_UUID, payload, response=False
                )
            except Exception as e:
                print(f"BLE write error: {e}")

        asyncio.run_coroutine_threadsafe(_write(), self._loop)

    # --- Disconnect ---

    def disconnect(self):
        """Disconnect from the BLE device."""
        self._running = False
        if self._loop and self._client:
            future = asyncio.run_coroutine_threadsafe(
                self._safe_disconnect(), self._loop
            )
            try:
                future.result(timeout=3.0)
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=3.0)

    async def _safe_disconnect(self):
        """Async disconnect helper."""
        if self._client and self._client.is_connected:
            try:
                await self._client.stop_notify(HM11_CHAR_UUID)
            except Exception:
                pass
            await self._client.disconnect()
