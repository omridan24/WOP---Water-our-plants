"""
WOP Backend — Database Layer
Async SQLite database with aiosqlite.
"""

import aiosqlite
from datetime import datetime, timedelta
from typing import Optional
from app.config import settings


_db: Optional[aiosqlite.Connection] = None


async def get_db() -> aiosqlite.Connection:
    """Get the database connection (singleton)."""
    global _db
    if _db is None:
        _db = await aiosqlite.connect(settings.db_path)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def init_db():
    """Create tables if they don't exist."""
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS plants (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            name                TEXT NOT NULL DEFAULT 'New Plant',
            species             TEXT,
            image_path          TEXT,
            ble_address         TEXT,
            ideal_moisture_min  INTEGER DEFAULT 30,
            ideal_moisture_max  INTEGER DEFAULT 70,
            ideal_humidity_min  INTEGER,
            ideal_humidity_max  INTEGER,
            light_preference    TEXT,
            watering_frequency  TEXT,
            notes               TEXT,
            auto_water          BOOLEAN DEFAULT 0,
            created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS sensor_readings (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id        INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
            soil_moisture   INTEGER,
            water_depth     INTEGER,
            pump_active     BOOLEAN DEFAULT 0,
            uptime_seconds  INTEGER,
            recorded_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_readings_plant_time
            ON sensor_readings(plant_id, recorded_at DESC);
    """)

    # Migration: Remove UNIQUE constraint from ble_address if it exists
    # SQLite doesn't support DROP CONSTRAINT, so we check if the table has the UNIQUE constraint
    # by looking at the sqlite_master table SQL definition.
    cursor = await db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='plants'")
    row = await cursor.fetchone()
    if row and "ble_address         TEXT UNIQUE" in row["sql"]:
        # Perform table migration
        await db.executescript("""
            PRAGMA foreign_keys=OFF;
            ALTER TABLE plants RENAME TO plants_old;
            
            CREATE TABLE plants (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                name                TEXT NOT NULL DEFAULT 'New Plant',
                species             TEXT,
                image_path          TEXT,
                ble_address         TEXT,
                ideal_moisture_min  INTEGER DEFAULT 30,
                ideal_moisture_max  INTEGER DEFAULT 70,
                ideal_humidity_min  INTEGER,
                ideal_humidity_max  INTEGER,
                light_preference    TEXT,
                watering_frequency  TEXT,
                notes               TEXT,
                created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            INSERT INTO plants SELECT * FROM plants_old;
            DROP TABLE plants_old;
            PRAGMA foreign_keys=ON;
        """)

    # Migration: Fix sensor_readings foreign key constraint (if it points to plants_old)
    cursor = await db.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='sensor_readings'")
    row = await cursor.fetchone()
    if row and "plants_old" in row["sql"]:
        await db.executescript("""
            PRAGMA foreign_keys=OFF;
            ALTER TABLE sensor_readings RENAME TO sensor_readings_old;
            CREATE TABLE sensor_readings (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                plant_id        INTEGER NOT NULL REFERENCES plants(id) ON DELETE CASCADE,
                soil_moisture   INTEGER,
                water_depth     INTEGER,
                pump_active     BOOLEAN DEFAULT 0,
                uptime_seconds  INTEGER,
                recorded_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            INSERT INTO sensor_readings SELECT * FROM sensor_readings_old;
            DROP TABLE sensor_readings_old;
            CREATE INDEX IF NOT EXISTS idx_readings_plant_time ON sensor_readings(plant_id, recorded_at DESC);
            PRAGMA foreign_keys=ON;
        """)

    await db.commit()

    # Migration: Add auto_water column if it doesn't exist
    cursor = await db.execute("PRAGMA table_info(plants)")
    columns = [row[1] for row in await cursor.fetchall()]
    if "auto_water" not in columns:
        await db.execute("ALTER TABLE plants ADD COLUMN auto_water BOOLEAN DEFAULT 0")
        await db.commit()


async def close_db():
    """Close the database connection."""
    global _db
    if _db:
        await _db.close()
        _db = None


# ─── Plant CRUD ──────────────────────────────────────────────────────

async def create_plant(
    name: str = "New Plant",
    species: str = None,
    image_path: str = None,
    ble_address: str = None,
    ideal_moisture_min: int = 30,
    ideal_moisture_max: int = 70,
    ideal_humidity_min: int = None,
    ideal_humidity_max: int = None,
    light_preference: str = None,
    watering_frequency: str = None,
    notes: str = None,
) -> dict:
    db = await get_db()
    cursor = await db.execute(
        """INSERT INTO plants
           (name, species, image_path, ble_address,
            ideal_moisture_min, ideal_moisture_max,
            ideal_humidity_min, ideal_humidity_max,
            light_preference, watering_frequency, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, species, image_path, ble_address,
         ideal_moisture_min, ideal_moisture_max,
         ideal_humidity_min, ideal_humidity_max,
         light_preference, watering_frequency, notes),
    )
    await db.commit()
    return await get_plant(cursor.lastrowid)


async def get_plant(plant_id: int) -> Optional[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM plants WHERE id = ?", (plant_id,))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def get_all_plants() -> list[dict]:
    db = await get_db()
    cursor = await db.execute("SELECT * FROM plants ORDER BY created_at DESC")
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def update_plant(plant_id: int, **kwargs) -> Optional[dict]:
    # Filter out None values — only update fields that were actually provided
    updates = {k: v for k, v in kwargs.items() if v is not None}
    if not updates:
        return await get_plant(plant_id)

    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [plant_id]

    db = await get_db()
    await db.execute(f"UPDATE plants SET {set_clause} WHERE id = ?", values)
    await db.commit()
    return await get_plant(plant_id)


async def delete_plant(plant_id: int) -> bool:
    db = await get_db()
    cursor = await db.execute("DELETE FROM plants WHERE id = ?", (plant_id,))
    await db.commit()
    return cursor.rowcount > 0


async def get_plants_by_ble_address(ble_address: str) -> list[dict]:
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM plants WHERE ble_address = ?", (ble_address,)
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


# ─── Sensor Readings ────────────────────────────────────────────────

async def store_reading(
    plant_id: int,
    soil_moisture: int,
    water_depth: int,
    pump_active: bool = False,
    uptime_seconds: int = 0,
):
    db = await get_db()
    await db.execute(
        """INSERT INTO sensor_readings
           (plant_id, soil_moisture, water_depth, pump_active, uptime_seconds)
           VALUES (?, ?, ?, ?, ?)""",
        (plant_id, soil_moisture, water_depth, int(pump_active), uptime_seconds),
    )
    await db.commit()


async def get_readings(
    plant_id: int,
    hours: int = 24,
    limit: int = 500,
) -> list[dict]:
    db = await get_db()
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    cursor = await db.execute(
        """SELECT soil_moisture, water_depth, pump_active, uptime_seconds, recorded_at
           FROM sensor_readings
           WHERE plant_id = ? AND recorded_at >= ?
           ORDER BY recorded_at DESC
           LIMIT ?""",
        (plant_id, since, limit),
    )
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def get_latest_reading(plant_id: int) -> Optional[dict]:
    db = await get_db()
    cursor = await db.execute(
        """SELECT soil_moisture, water_depth, pump_active, uptime_seconds, recorded_at
           FROM sensor_readings
           WHERE plant_id = ?
           ORDER BY recorded_at DESC
           LIMIT 1""",
        (plant_id,),
    )
    row = await cursor.fetchone()
    return dict(row) if row else None
