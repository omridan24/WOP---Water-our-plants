"""
WOP Backend — Plants Router
CRUD endpoints for plant management + AI identification.
"""

import os
import uuid
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.config import settings
from app import database as db
from app.models import PlantCreate, PlantUpdate, PlantResponse
from app.plant_identifier import identify_plant
from app.ble_bridge import ble_bridge

logger = logging.getLogger("wop.api.plants")
router = APIRouter(prefix="/api/plants", tags=["plants"])


def _plant_to_response(plant: dict) -> dict:
    """Convert a DB plant row to a response dict with live data."""
    image_url = None
    if plant.get("image_path"):
        filename = os.path.basename(plant["image_path"])
        image_url = f"/api/images/{filename}"

    # Get live BLE data if available
    dev = ble_bridge.get_device_by_plant(plant["id"])
    latest_reading = None
    ble_connected = False

    if dev:
        ble_connected = dev.connected
        if dev.latest_data:
            latest_reading = dev.latest_data.to_dict()

    return {
        "id": plant["id"],
        "name": plant["name"],
        "species": plant.get("species"),
        "image_url": image_url,
        "ble_address": plant.get("ble_address"),
        "ideal_moisture_min": plant.get("ideal_moisture_min", 30),
        "ideal_moisture_max": plant.get("ideal_moisture_max", 70),
        "ideal_humidity_min": plant.get("ideal_humidity_min"),
        "ideal_humidity_max": plant.get("ideal_humidity_max"),
        "light_preference": plant.get("light_preference"),
        "watering_frequency": plant.get("watering_frequency"),
        "notes": plant.get("notes"),
        "created_at": plant.get("created_at"),
        "latest_reading": latest_reading,
        "ble_connected": ble_connected,
    }


@router.get("")
async def list_plants():
    """Get all plants with their latest sensor data."""
    plants = await db.get_all_plants()
    return [_plant_to_response(p) for p in plants]


@router.get("/{plant_id}")
async def get_plant(plant_id: int):
    """Get a single plant with details and recent readings."""
    plant = await db.get_plant(plant_id)
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")

    response = _plant_to_response(plant)

    # Include recent readings for chart
    readings = await db.get_readings(plant_id, hours=24)
    response["recent_readings"] = readings

    return response


@router.post("")
async def create_plant(
    image: Optional[UploadFile] = File(None),
    name: Optional[str] = Form(None),
    ble_address: Optional[str] = Form(None),
):
    """
    Add a new plant. Optionally upload a photo for AI identification.
    If an image is provided, Gemini AI will identify the plant and
    pre-fill care information.
    """
    image_path = None
    ai_data = {}

    # Save uploaded image
    if image and image.filename:
        ext = Path(image.filename).suffix.lower() or ".jpg"
        filename = f"{uuid.uuid4().hex}{ext}"
        image_path = os.path.join(settings.images_dir, filename)

        content = await image.read()
        with open(image_path, "wb") as f:
            f.write(content)

        logger.info("Saved plant image: %s (%d bytes)", filename, len(content))

        # Run AI identification
        identification = await identify_plant(image_path)
        if identification:
            ai_data = identification.model_dump(exclude_none=True)

    # Use AI name if user didn't provide one
    plant_name = name or ai_data.pop("common_name", "New Plant")

    # Merge AI care data with defaults
    plant = await db.create_plant(
        name=plant_name,
        species=ai_data.get("scientific_name"),
        image_path=image_path,
        ble_address=ble_address,
        ideal_moisture_min=ai_data.get("ideal_moisture_min", 30),
        ideal_moisture_max=ai_data.get("ideal_moisture_max", 70),
        ideal_humidity_min=ai_data.get("ideal_humidity_min"),
        ideal_humidity_max=ai_data.get("ideal_humidity_max"),
        light_preference=ai_data.get("light_preference"),
        watering_frequency=ai_data.get("watering_frequency"),
        notes=ai_data.get("care_notes"),
    )

    # Register BLE device if address provided
    if ble_address:
        await ble_bridge.add_device(ble_address, plant["id"])

    return _plant_to_response(plant)


@router.put("/{plant_id}")
async def update_plant(plant_id: int, updates: PlantUpdate):
    """Update plant details."""
    existing = await db.get_plant(plant_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Plant not found")

    update_data = updates.model_dump(exclude_none=True)
    plant = await db.update_plant(plant_id, **update_data)

    # Update BLE bridge if address changed
    if "ble_address" in update_data:
        old_addr = existing.get("ble_address")
        new_addr = update_data["ble_address"]
        if old_addr and old_addr != new_addr:
            await ble_bridge.remove_device(old_addr)
        if new_addr:
            await ble_bridge.add_device(new_addr, plant_id)

    return _plant_to_response(plant)


@router.delete("/{plant_id}")
async def delete_plant(plant_id: int):
    """Delete a plant and its associated BLE connection."""
    plant = await db.get_plant(plant_id)
    if not plant:
        raise HTTPException(status_code=404, detail="Plant not found")

    # Remove BLE connection
    if plant.get("ble_address"):
        await ble_bridge.remove_device(plant["ble_address"])

    # Delete image file
    if plant.get("image_path") and os.path.exists(plant["image_path"]):
        os.remove(plant["image_path"])

    await db.delete_plant(plant_id)
    return {"status": "deleted", "plant_id": plant_id}
