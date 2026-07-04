"""
WOP Backend — Sensors Router
Historical readings and live WebSocket streams.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from pydantic import BaseModel
import time
from app import database as db
from app.ble_bridge import ble_bridge, SensorData
from app import state

logger = logging.getLogger("wop.api.sensors")
router = APIRouter(tags=["sensors"])


@router.get("/api/plants/{plant_id}/readings")
async def get_readings(
    plant_id: int,
    hours: int = Query(default=24, ge=1, le=168, description="Hours of history (max 7 days)"),
    limit: int = Query(default=500, ge=1, le=2000),
):
    """Get historical sensor readings for a plant."""
    plant = await db.get_plant(plant_id)
    if not plant:
        return {"error": "Plant not found"}, 404

    readings = await db.get_readings(plant_id, hours=hours, limit=limit)
    return {
        "plant_id": plant_id,
        "readings": readings,
        "count": len(readings),
    }


class SensorPostData(BaseModel):
    soil_moisture: int
    water_depth: int
    pump_active: bool
    uptime_seconds: int


# Throttle database writes to once per minute per plant
_last_store_time: dict[int, float] = {}

@router.post("/api/devices/{device_id}/readings")
async def post_device_reading(device_id: str, data: SensorPostData):
    """
    Receive live telemetry from ESP32 via Wi-Fi based on MAC address.
    Returns any pending pump commands in the response.
    """
    # Track that this device is active
    state.update_device_seen(device_id)
    
    sensor_data = SensorData(
        soil_moisture=data.soil_moisture,
        water_depth=data.water_depth,
        pump_active=data.pump_active,
        uptime_seconds=data.uptime_seconds,
        timestamp=time.time()
    )
    
    # Find all plants configured to use this device ID
    plants = await db.get_plants_by_ble_address(device_id)
    all_commands = []
    
    for p in plants:
        plant_id = p["id"]
        
        # 1. Store in DB (throttled to 60s)
        now = time.time()
        if now - _last_store_time.get(plant_id, 0) >= 60:
            await db.store_reading(
                plant_id=plant_id,
                soil_moisture=data.soil_moisture,
                water_depth=data.water_depth,
                pump_active=data.pump_active,
                uptime_seconds=data.uptime_seconds,
            )
            _last_store_time[plant_id] = now
            
        # 2. Broadcast to active WebSockets for live UI updates
        await broadcast_sensor_data(plant_id, sensor_data)
        
        # 3. Retrieve any pending commands for this ESP32
        cmds = state.get_and_clear_commands(plant_id)
        all_commands.extend(cmds)
        
    return {
        "status": "ok",
        "commands": all_commands
    }


# ─── WebSocket for Live Data ────────────────────────────────────────

# Track active WebSocket connections per plant
_ws_connections: dict[int, set[WebSocket]] = {}


@router.websocket("/ws/plants/{plant_id}/live")
async def live_sensor_data(websocket: WebSocket, plant_id: int):
    """
    WebSocket endpoint for real-time sensor data.
    Sends a JSON message every time the BLE bridge receives new data
    from the Arduino associated with this plant.
    """
    await websocket.accept()
    logger.info("WebSocket client connected for plant %d", plant_id)

    # Add to connection set
    if plant_id not in _ws_connections:
        _ws_connections[plant_id] = set()
    _ws_connections[plant_id].add(websocket)

    try:
        # Send current data immediately if available
        dev = ble_bridge.get_device_by_plant(plant_id)
        if dev and dev.latest_data:
            await websocket.send_json({
                "type": "sensor_data",
                "plant_id": plant_id,
                "data": dev.latest_data.to_dict(),
                "ble_connected": dev.connected,
            })
        else:
            await websocket.send_json({
                "type": "status",
                "plant_id": plant_id,
                "ble_connected": dev.connected if dev else False,
                "message": "Waiting for sensor data...",
            })

        # Keep the WebSocket alive — data is pushed by the broadcast_data callback
        while True:
            # Wait for pings or client messages (keepalive)
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # Client can send "ping" to keep alive
                if msg == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                # Send a keepalive ping
                await websocket.send_json({"type": "ping"})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected for plant %d", plant_id)
    except Exception as e:
        logger.error("WebSocket error for plant %d: %s", plant_id, e)
    finally:
        _ws_connections.get(plant_id, set()).discard(websocket)
        if plant_id in _ws_connections and not _ws_connections[plant_id]:
            del _ws_connections[plant_id]


async def broadcast_sensor_data(plant_id: int, data: SensorData):
    """
    Called by the BLE bridge when new data arrives.
    Broadcasts to all WebSocket clients watching this plant.
    """
    connections = _ws_connections.get(plant_id, set()).copy()
    if not connections:
        return

    message = {
        "type": "sensor_data",
        "plant_id": plant_id,
        "data": data.to_dict(),
        "ble_connected": True,
    }

    dead = set()
    for ws in connections:
        try:
            await ws.send_json(message)
        except Exception:
            dead.add(ws)

    # Clean up dead connections
    for ws in dead:
        _ws_connections.get(plant_id, set()).discard(ws)
