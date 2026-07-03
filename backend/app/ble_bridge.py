"""
WOP Backend — BLE Bridge Service
Manages Bluetooth Low Energy connections to multiple Arduino + HM-11 units.
Designed for Linux (Raspberry Pi) where bleak works reliably.

Each connected device maps to one plant. The bridge:
  - Scans for HM-11 modules on startup
  - Maintains persistent connections with auto-reconnect
  - Parses the WOP:DATA: protocol
  - Stores readings in the database at configurable intervals
  - Broadcasts live data to WebSocket subscribers
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Callable

from bleak import BleakClient, BleakScanner

from app.config import settings
from app import database as db

logger = logging.getLogger("wop.ble")


@dataclass
class SensorData:
    """Parsed sensor reading from an Arduino."""
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
        return round((self.water_depth / 100) * 100, 1)

    def to_dict(self) -> dict:
        return {
            "soil_moisture": self.soil_moisture,
            "soil_moisture_pct": self.soil_moisture_pct,
            "water_depth": self.water_depth,
            "water_depth_pct": self.water_depth_pct,
            "pump_active": self.pump_active,
            "uptime_seconds": self.uptime_seconds,
            "timestamp": self.timestamp,
        }


@dataclass
class DeviceConnection:
    """Tracks state for a single BLE device connection."""
    address: str
    plant_ids: set[int] = field(default_factory=set)
    client: Optional[BleakClient] = None
    connected: bool = False
    latest_data: Optional[SensorData] = None
    rx_buffer: str = ""
    last_store_time: float = 0.0
    device_name: str = ""
    _reconnect_task: Optional[asyncio.Task] = field(default=None, repr=False)


class BLEBridge:
    """
    Manages BLE connections to multiple WOP Arduino devices.
    Runs as a background asyncio task alongside FastAPI.
    """

    def __init__(self):
        self._devices: dict[str, DeviceConnection] = {}  # keyed by BLE address
        self._running = False
        self._scan_task: Optional[asyncio.Task] = None
        self._on_data_callbacks: list[Callable] = []
        self._store_interval = settings.sensor_history_interval

    # ─── Lifecycle ───────────────────────────────────────────────────

    async def start(self):
        """Start the BLE bridge (called on FastAPI startup)."""
        self._running = True
        logger.info("BLE Bridge starting...")

        # Load plants with BLE addresses from DB and connect
        plants = await db.get_all_plants()
        for plant in plants:
            if plant.get("ble_address"):
                await self.add_device(plant["ble_address"], plant["id"])

        # Start background scanner for new devices
        self._scan_task = asyncio.create_task(self._periodic_scan())
        logger.info("BLE Bridge started. Monitoring %d device(s).", len(self._devices))

    async def stop(self):
        """Stop all connections and background tasks."""
        self._running = False
        if self._scan_task:
            self._scan_task.cancel()

        for dev in self._devices.values():
            if dev._reconnect_task:
                dev._reconnect_task.cancel()
            if dev.client and dev.client.is_connected:
                try:
                    await dev.client.disconnect()
                except Exception:
                    pass

        self._devices.clear()
        logger.info("BLE Bridge stopped.")

    # ─── Device Management ───────────────────────────────────────────

    async def add_device(self, address: str, plant_id: int = None):
        """Register a device and start connecting to it. Supports multiple plants per device."""
        if address in self._devices:
            if plant_id:
                self._devices[address].plant_ids.add(plant_id)
            return

        dev = DeviceConnection(address=address)
        if plant_id:
            dev.plant_ids.add(plant_id)
            
        self._devices[address] = dev
        dev._reconnect_task = asyncio.create_task(self._connect_loop(dev))
        logger.info("Added BLE device %s (plant_ids=%s)", address, dev.plant_ids)

    async def remove_plant_from_device(self, address: str, plant_id: int):
        """Remove a plant from a device. If no plants remain, optionally disconnect (we keep connected for now)."""
        dev = self._devices.get(address)
        if dev and plant_id in dev.plant_ids:
            dev.plant_ids.remove(plant_id)
            logger.info("Removed plant %d from BLE device %s", plant_id, address)

    async def remove_device(self, address: str):
        """Disconnect and remove a device."""
        dev = self._devices.pop(address, None)
        if dev:
            if dev._reconnect_task:
                dev._reconnect_task.cancel()
            if dev.client and dev.client.is_connected:
                try:
                    await dev.client.disconnect()
                except Exception:
                    pass
            logger.info("Removed BLE device %s", address)

    def get_device(self, address: str) -> Optional[DeviceConnection]:
        return self._devices.get(address)

    def get_device_by_plant(self, plant_id: int) -> Optional[DeviceConnection]:
        for dev in self._devices.values():
            if plant_id in dev.plant_ids:
                return dev
        return None

    def get_all_devices(self) -> list[DeviceConnection]:
        return list(self._devices.values())

    # ─── Data Callbacks ──────────────────────────────────────────────

    def on_data(self, callback: Callable):
        """Register a callback for live sensor data (used by WebSocket broadcaster)."""
        self._on_data_callbacks.append(callback)

    def remove_on_data(self, callback: Callable):
        self._on_data_callbacks = [c for c in self._on_data_callbacks if c != callback]

    async def _notify_data(self, plant_id: int, data: SensorData):
        """Notify all registered callbacks of new data."""
        for cb in self._on_data_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(plant_id, data)
                else:
                    cb(plant_id, data)
            except Exception as e:
                logger.error("Data callback error: %s", e)

    # ─── Scanning ────────────────────────────────────────────────────

    async def scan_devices(self, timeout: float = None) -> list[dict]:
        """Scan for nearby BLE devices and return a list."""
        timeout = timeout or settings.ble_scan_timeout
        try:
            devices = await BleakScanner.discover(timeout=timeout)
            result = []
            for d in devices:
                result.append({
                    "name": d.name or "Unknown",
                    "address": d.address,
                    "rssi": getattr(d, "rssi", None),
                    "is_wop": d.name and any(
                        n.lower() in d.name.lower()
                        for n in settings.ble_known_names
                    ),
                })
            return result
        except Exception as e:
            logger.error("BLE scan error: %s", e)
            return []

    async def _periodic_scan(self):
        """Periodically scan for disconnected devices and try to reconnect."""
        while self._running:
            try:
                await asyncio.sleep(settings.ble_reconnect_interval)
            except asyncio.CancelledError:
                return

    # ─── Connection Loop ─────────────────────────────────────────────

    async def _connect_loop(self, dev: DeviceConnection):
        """Persistent connection loop for a single device. Reconnects on failure."""
        while self._running:
            if dev.connected:
                await asyncio.sleep(5)
                continue

            try:
                logger.info("Connecting to %s...", dev.address)
                client = BleakClient(
                    dev.address,
                    disconnected_callback=lambda _c, _d=dev: self._handle_disconnect(_d),
                )
                await client.connect(timeout=15.0)

                if client.is_connected:
                    dev.client = client
                    dev.connected = True

                    # Try to read device name
                    try:
                        dev.device_name = (
                            client._device_info
                            if hasattr(client, "_device_info")
                            else dev.address
                        )
                    except Exception:
                        dev.device_name = dev.address

                    logger.info("Connected to %s", dev.address)

                    # Subscribe to notifications
                    await client.start_notify(
                        settings.hm11_char_uuid,
                        lambda sender, data, _d=dev: asyncio.ensure_future(
                            self._handle_rx(_d, data)
                        ),
                    )

                    # Stay alive while connected
                    while self._running and dev.connected and client.is_connected:
                        await asyncio.sleep(1)

                    # Clean disconnect
                    if client.is_connected:
                        try:
                            await client.stop_notify(settings.hm11_char_uuid)
                            await client.disconnect()
                        except Exception:
                            pass

            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.warning("Connection to %s failed: %s", dev.address, e)

            dev.connected = False
            dev.client = None

            if self._running:
                logger.info("Will retry %s in %ds...", dev.address, int(settings.ble_reconnect_interval))
                try:
                    await asyncio.sleep(settings.ble_reconnect_interval)
                except asyncio.CancelledError:
                    return

    def _handle_disconnect(self, dev: DeviceConnection):
        """Called by bleak when a device disconnects unexpectedly."""
        dev.connected = False
        dev.client = None
        logger.warning("Device %s disconnected unexpectedly", dev.address)

    # ─── Data Reception ──────────────────────────────────────────────

    async def _handle_rx(self, dev: DeviceConnection, data: bytearray):
        """Handle incoming BLE notification data. Buffer until newline."""
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            return

        dev.rx_buffer += text

        while "\n" in dev.rx_buffer:
            line, dev.rx_buffer = dev.rx_buffer.split("\n", 1)
            line = line.strip()
            if not line:
                continue

            if line.startswith("WOP:DATA:"):
                await self._parse_and_dispatch(dev, line)
            else:
                logger.debug("[%s] %s", dev.address, line)

    async def _parse_and_dispatch(self, dev: DeviceConnection, line: str):
        """Parse a WOP:DATA: line, store it, and broadcast to subscribers."""
        try:
            payload = line.replace("WOP:DATA:", "")
            parts = payload.split(",")
            if len(parts) >= 4:
                sensor = SensorData(
                    soil_moisture=int(parts[0]),
                    water_depth=int(parts[1]),
                    pump_active=parts[2] == "1",
                    uptime_seconds=int(parts[3]),
                )
                dev.latest_data = sensor

                # Store in database at configured interval
                now = time.time()
                if dev.plant_ids and (now - dev.last_store_time) >= self._store_interval:
                    dev.last_store_time = now
                    for p_id in dev.plant_ids:
                        await db.store_reading(
                            plant_id=p_id,
                            soil_moisture=sensor.soil_moisture,
                            water_depth=sensor.water_depth,
                            pump_active=sensor.pump_active,
                            uptime_seconds=sensor.uptime_seconds,
                        )

                # Broadcast to WebSocket subscribers
                for p_id in dev.plant_ids:
                    await self._notify_data(p_id, sensor)

        except (ValueError, IndexError) as e:
            logger.error("Parse error: %s | line: %s", e, line)

    # ─── Sending Commands ────────────────────────────────────────────

    async def send_command(self, address: str, command: str) -> bool:
        """Send a command to an Arduino via BLE."""
        dev = self._devices.get(address)
        if not dev or not dev.connected or not dev.client:
            logger.warning("Cannot send to %s — not connected", address)
            return False

        try:
            payload = f"{command}\n".encode("utf-8")
            await dev.client.write_gatt_char(
                settings.hm11_char_uuid, payload, response=False
            )
            logger.info("Sent '%s' to %s", command, address)
            return True
        except Exception as e:
            logger.error("Write error to %s: %s", address, e)
            return False

    async def send_command_to_plant(self, plant_id: int, command: str) -> bool:
        """Send a command to the Arduino associated with a plant."""
        dev = self.get_device_by_plant(plant_id)
        if not dev:
            logger.warning("No BLE device for plant %d", plant_id)
            return False
        return await self.send_command(dev.address, command)


# Singleton instance
ble_bridge = BLEBridge()
