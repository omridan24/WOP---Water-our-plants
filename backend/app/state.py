"""
WOP Backend — Shared State
Holds in-memory state for devices (e.g., queued commands).
"""

from typing import Dict, List
import time

# Keyed by plant_id, holds a list of pending string commands (e.g., "PUMP_ON", "PUMP_OFF")
queued_commands: Dict[int, List[str]] = {}

def queue_command(plant_id: int, command: str):
    if plant_id not in queued_commands:
        queued_commands[plant_id] = []
    queued_commands[plant_id].append(command)

def get_and_clear_commands(plant_id: int) -> List[str]:
    if plant_id in queued_commands:
        cmds = queued_commands[plant_id]
        queued_commands[plant_id] = []
        return cmds
    return []

# Active ESP32 devices mapping MAC address to last_seen timestamp
active_devices: Dict[str, float] = {}

def update_device_seen(device_id: str):
    active_devices[device_id] = time.time()

def get_active_devices() -> List[str]:
    now = time.time()
    # Return devices seen in the last 5 minutes
    return [addr for addr, last_seen in active_devices.items() if now - last_seen < 300]

