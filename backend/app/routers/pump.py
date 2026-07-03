"""
WOP Backend — Pump Router
Endpoints for controlling the water pump on each Arduino.
"""

import logging
from fastapi import APIRouter, HTTPException

from app import database as db
from app.models import PumpCommand
from app.ble_bridge import ble_bridge

logger = logging.getLogger("wop.api.pump")
router = APIRouter(prefix="/api/plants", tags=["pump"])


@router.post("/{plant_id}/pump")
async def control_pump(plant_id: int, command: PumpCommand):
    """
    Turn the water pump on or off for a specific plant.
    Sends PUMP_ON or PUMP_OFF to the Arduino over BLE.
    """
    plant = await db.get_plant(plant_id)
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")

    if not plant.get("ble_address"):
        raise HTTPException(
            status_code=400,
            detail="No BLE device assigned to this plant",
        )

    dev = ble_bridge.get_device_by_plant(plant_id)
    if not dev or not dev.connected:
        raise HTTPException(
            status_code=503,
            detail="BLE device not connected",
        )

    arduino_cmd = "PUMP_ON" if command.action == "on" else "PUMP_OFF"
    success = await ble_bridge.send_command_to_plant(plant_id, arduino_cmd)

    if not success:
        raise HTTPException(
            status_code=500,
            detail="Failed to send command to Arduino",
        )

    logger.info("Pump %s for plant %d (%s)", command.action.upper(), plant_id, plant["name"])

    return {
        "status": "ok",
        "plant_id": plant_id,
        "pump_action": command.action,
    }


@router.post("/{plant_id}/ping")
async def ping_device(plant_id: int):
    """
    Send a PING command to the Arduino to test BLE connectivity.
    """
    plant = await db.get_plant(plant_id)
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")

    success = await ble_bridge.send_command_to_plant(plant_id, "PING")
    return {
        "status": "ok" if success else "failed",
        "plant_id": plant_id,
    }
