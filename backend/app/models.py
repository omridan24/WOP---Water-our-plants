"""
WOP Backend — Pydantic Models
Request/response schemas for the API.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


# ─── Sensor Data (from Arduino protocol) ────────────────────────────

class SensorReading(BaseModel):
    """A single parsed WOP:DATA: packet."""
    soil_moisture: int = Field(ge=0, le=1023, description="Raw analog 0-1023")
    water_depth: int = Field(ge=0, le=100, description="Depth in mm (0-100)")
    pump_active: bool = False
    uptime_seconds: int = 0
    timestamp: datetime = Field(default_factory=datetime.now)

    @property
    def soil_moisture_pct(self) -> float:
        return round((self.soil_moisture / 1023) * 100, 1)

    @property
    def water_depth_pct(self) -> float:
        return round((self.water_depth / 100) * 100, 1)  # 0-100mm → percentage


# ─── Plant ───────────────────────────────────────────────────────────

class PlantCreate(BaseModel):
    """Payload for creating a new plant (name is optional — AI will fill it)."""
    name: Optional[str] = None
    species: Optional[str] = None
    ble_address: Optional[str] = None
    ideal_moisture_min: int = 30
    ideal_moisture_max: int = 70
    ideal_humidity_min: Optional[int] = None
    ideal_humidity_max: Optional[int] = None
    light_preference: Optional[str] = None
    watering_frequency: Optional[str] = None
    notes: Optional[str] = None


class PlantUpdate(BaseModel):
    """Partial update for a plant."""
    name: Optional[str] = None
    species: Optional[str] = None
    ble_address: Optional[str] = None
    ideal_moisture_min: Optional[int] = None
    ideal_moisture_max: Optional[int] = None
    ideal_humidity_min: Optional[int] = None
    ideal_humidity_max: Optional[int] = None
    light_preference: Optional[str] = None
    watering_frequency: Optional[str] = None
    notes: Optional[str] = None


class PlantResponse(BaseModel):
    """Full plant object returned by the API."""
    id: int
    name: str
    species: Optional[str] = None
    image_url: Optional[str] = None
    ble_address: Optional[str] = None
    ideal_moisture_min: int = 30
    ideal_moisture_max: int = 70
    ideal_humidity_min: Optional[int] = None
    ideal_humidity_max: Optional[int] = None
    light_preference: Optional[str] = None
    watering_frequency: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None
    # Live data (populated when available)
    latest_reading: Optional[SensorReading] = None
    ble_connected: bool = False


# ─── Plant Identification (AI response) ─────────────────────────────

class PlantIdentification(BaseModel):
    """Structured response from Gemini plant identification."""
    common_name: str = "Unknown Plant"
    scientific_name: Optional[str] = None
    ideal_moisture_min: int = 30
    ideal_moisture_max: int = 70
    ideal_humidity_min: Optional[int] = None
    ideal_humidity_max: Optional[int] = None
    light_preference: Optional[str] = None
    watering_frequency: Optional[str] = None
    care_notes: Optional[str] = None


# ─── Pump Command ───────────────────────────────────────────────────

class PumpCommand(BaseModel):
    action: str = Field(pattern="^(on|off)$", description="'on' or 'off'")


# ─── BLE Device Info ────────────────────────────────────────────────

class BLEDeviceInfo(BaseModel):
    """Discovered BLE device."""
    name: str
    address: str
    rssi: Optional[int] = None
    connected: bool = False
    plant_id: Optional[int] = None  # If assigned to a plant


# ─── Sensor History Query ───────────────────────────────────────────

class SensorHistoryResponse(BaseModel):
    plant_id: int
    readings: list[dict]
    count: int
