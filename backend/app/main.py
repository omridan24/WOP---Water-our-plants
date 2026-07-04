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
from app import state
from app.routers import plants, sensors, pump

# ─── Logging ─────────────────────────────────────────────────────────

log_dir = Path(settings.db_path).parent
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "wop.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
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

    # BLE is disabled for ESP32 Wi-Fi bridge
    # ble_bridge.on_data(sensors.broadcast_sensor_data)
    # await ble_bridge.start()

    yield

    # Shutdown
    logger.info("Shutting down...")
    # await ble_bridge.stop()
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


# ─── Device Discovery ──────────────────────────────────────────

@app.get("/api/ble/scan")
async def scan_ble_devices():
    """Scan for active devices currently sending telemetry via Wi-Fi."""
    active_devices = state.get_active_devices()
    devices = [
        {"name": f"ESP32 ({addr[-5:]})", "address": addr, "is_wop": True}
        for addr in active_devices
    ]
    return {"devices": devices}


@app.get("/api/ble/status")
async def ble_status():
    """Get the status of all registered devices."""
    active_devices = state.get_active_devices()
    
    # We need to return all devices the system knows about (from active AND from DB)
    all_plants = await db.get_all_plants()
    assigned_addresses = {}
    for p in all_plants:
        addr = p.get("ble_address")
        if addr:
            assigned_addresses.setdefault(addr, []).append(p["id"])
            
    # Combine active + assigned
    all_addresses = set(active_devices) | set(assigned_addresses.keys())
    
    devices_out = []
    for addr in all_addresses:
        devices_out.append({
            "address": addr,
            "plant_ids": assigned_addresses.get(addr, []),
            "connected": addr in active_devices,
            "device_name": f"ESP32 ({addr[-5:]})",
            "has_data": addr in active_devices
        })
        
    return {"devices": devices_out}


@app.delete("/api/ble/devices/{address}")
async def delete_ble_device(address: str):
    """Unassign a device from all plants."""
    plants = await db.get_plants_by_ble_address(address)
    for p in plants:
        await db.update_plant(p["id"], ble_address=None)
    
    if address in state.active_devices:
        del state.active_devices[address]
        
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
