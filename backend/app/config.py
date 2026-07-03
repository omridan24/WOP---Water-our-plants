"""
WOP Backend — Configuration
Loads settings from environment variables with sensible defaults.
"""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    db_path: str = os.getenv("WOP_DB_PATH", "data/wop.db")

    # Image storage
    images_dir: str = os.getenv("WOP_IMAGES_DIR", "data/images")

    # Gemini AI
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = "gemini-2.5-flash"

    # BLE
    ble_scan_timeout: float = 10.0
    ble_reconnect_interval: float = 15.0
    ble_known_names: list[str] = ["HMSoft", "WOP", "WOP-BLE", "Grove-BLE"]
    hm11_service_uuid: str = "0000ffe0-0000-1000-8000-00805f9b34fb"
    hm11_char_uuid: str = "0000ffe1-0000-1000-8000-00805f9b34fb"

    # Server
    host: str = "0.0.0.0"
    port: int = 8080

    # Data collection
    sensor_history_interval: int = 60  # Store a reading every N seconds (not every 2s push)

    class Config:
        env_prefix = "WOP_"


settings = Settings()

# Ensure directories exist
Path(settings.images_dir).mkdir(parents=True, exist_ok=True)
Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
