"""
WOP - Water Our Plants | Backend Server
FastAPI application serving the REST API, WebSocket, and static web dashboard.
Designed to run on a Raspberry Pi 5 in Docker.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response

from app.config import settings
from app import database as db
from app.ble_bridge import ble_bridge
from app.routers import plants, sensors, pump

# ─── Logging ─────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("wop")


# ─── Lifespan (startup / shutdown) ──────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup and shutdown of the application."""
    # Startup
    logger.info("=" * 50)
    logger.info("🌱 WOP - Water Our Plants — Starting up")
    logger.info("=" * 50)

    await db.init_db()
    logger.info("Database initialized: %s", settings.db_path)

    # Register the WebSocket broadcaster as a BLE data callback
    ble_bridge.on_data(sensors.broadcast_sensor_data)

    await ble_bridge.start()

    yield

    # Shutdown
    logger.info("Shutting down...")
    await ble_bridge.stop()
    await db.close_db()
    logger.info("Goodbye 🌿")


# ─── FastAPI App ─────────────────────────────────────────────────────

app = FastAPI(
    title="WOP - Water Our Plants",
    description="Smart plant monitoring and watering system",
    version="2.0.0",
    lifespan=lifespan,
)

# Include API routers
app.include_router(plants.router)
app.include_router(sensors.router)
app.include_router(pump.router)


# ─── Image Serving ──────────────────────────────────────────────────

@app.get("/api/images/{filename}")
async def serve_image(filename: str):
    """Serve uploaded plant images."""
    path = os.path.join(settings.images_dir, filename)
    if not os.path.exists(path):
        return Response(status_code=404, content="Image not found")
    return FileResponse(path)


# ─── BLE Device Discovery ──────────────────────────────────────────

@app.get("/api/ble/scan")
async def scan_ble_devices():
    """Scan for nearby BLE devices and filter for known WOP devices."""
    devices = await ble_bridge.scan_devices()
    wop_devices = [d for d in devices if d["is_wop"]]
    return {"devices": wop_devices}


@app.get("/api/ble/status")
async def ble_status():
    """Get the status of all registered BLE connections."""
    devices = ble_bridge.get_all_devices()
    return {
        "devices": [
            {
                "address": d.address,
                "plant_ids": list(d.plant_ids),
                "connected": d.connected,
                "device_name": d.device_name,
                "has_data": d.latest_data is not None,
            }
            for d in devices
        ]
    }


@app.delete("/api/ble/devices/{address}")
async def delete_ble_device(address: str):
    """Disconnect and remove a BLE device, and unassign it from any plants."""
    dev = ble_bridge.get_device(address)
    if dev:
        # Update database to clear ble_address for associated plants
        for plant_id in list(dev.plant_ids):
            await db.update_plant(plant_id, ble_address=None)
        
        # Remove from bridge
        await ble_bridge.remove_device(address)
    
    return {"status": "deleted", "address": address}


# ─── Static Web Dashboard ──────────────────────────────────────────

# Serve static files (CSS, JS)
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/wop")
@app.get("/wop/{rest_of_path:path}")
async def serve_dashboard(rest_of_path: str = ""):
    """Serve the web dashboard at /wop."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return Response(
        content="<h1>WOP Dashboard</h1><p>Static files not found. Build the frontend first.</p>",
        media_type="text/html",
    )


@app.get("/")
async def root_redirect():
    """Redirect root to the dashboard."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/wop")
