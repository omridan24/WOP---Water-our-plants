# WOP - Water Our Plants 🌱

WOP (v2) is a smart plant watering system combining Arduino sensor hardware with a modern Raspberry Pi-hosted backend and web dashboard. 

## Features
- **BLE Wireless Communication**: Arduinos communicate wirelessly to the Raspberry Pi over Bluetooth Low Energy (using HM-11 modules).
- **Web Dashboard**: Responsive dark-themed UI accessible from anywhere on your local network (phones, tablets, desktop).
- **AI Plant Identification**: Upload a photo of a plant to have Google's Gemini AI automatically identify it and suggest ideal moisture, humidity, and light conditions.
- **Live Real-time Telemetry**: WebSocket integration updates the dashboard gauges instantly when new sensor readings arrive.
- **Historical Data**: Integrated SQLite database stores sensor history with beautiful interactive charts using Chart.js.
- **Remote Pump Control**: Trigger your plant's water pump directly from the web interface.

## Project Structure

```
WOP---Water-our-plants/
├── arduino/
│   └── wop_basic/
│       └── wop_basic.ino       # Arduino sketch (unchanged from v1, uses Grove BLE)
├── backend/                    # The Raspberry Pi 5 backend service
│   ├── app/                    # FastAPI application
│   │   ├── static/             # Web dashboard (HTML, CSS, JS)
│   │   ├── routers/            # API endpoints (plants, sensors, pump)
│   │   ├── main.py             # Entry point
│   │   ├── ble_bridge.py       # BLE connection manager
│   │   ├── database.py         # SQLite setup
│   │   ├── models.py           # Data schemas
│   │   └── plant_identifier.py # Gemini AI integration
│   ├── Dockerfile
│   ├── docker-compose.yml
│   └── requirements.txt
└── desktop/                    # (Deprecated v1) Old Windows desktop app
```

## Quick Start (Raspberry Pi 5)

WOP v2 is designed to run in Docker on a Raspberry Pi. It relies on the Pi's built-in Bluetooth to connect to your plants.

### 1. Prerequisites
- Raspberry Pi (preferably Pi 4 or 5) running a modern Linux OS (like Raspberry Pi OS).
- Docker and Docker Compose installed.
- (Optional) A free Google Gemini API key for plant identification.

### 2. Run the Backend
```bash
cd backend

# Optional: Export your Gemini API key (or put it in a .env file)
export GEMINI_API_KEY="your_api_key_here"

# Start the Docker container (uses host networking and privileged mode for BLE access)
docker compose up -d
```

### 3. Access the Dashboard
Open a web browser on any device on your local network and navigate to:
`http://<your-raspberry-pi-ip>:8080/wop`

### 4. Connect a Plant
1. Make sure your Arduino + HM-11 is powered on.
2. In the Web Dashboard, click **Add Plant**.
3. Upload a photo of the plant (the AI will identify it).
4. Click **Scan** next to the BLE address field to find and select your Arduino's Bluetooth module (usually named "HMSoft").
5. Save the plant. The dashboard will connect and start streaming live data!

## WOP Serial Protocol

The backend and Arduino communicate over a simple text protocol transmitted via BLE.

| Direction | Message | Description |
|-----------|---------|-------------|
| Arduino → Pi | `WOP:HELLO` | Handshake |
| Arduino → Pi | `WOP:DATA:soil,depth,pump,uptime` | Sensor data packet |
| Arduino → Pi | `WOP:ACK:command` | Command acknowledged |
| Pi → Arduino | `PING` | Connection test |
| Pi → Arduino | `PUMP_ON` / `PUMP_OFF` | Pump control |
| Pi → Arduino | `STATUS` | Request immediate data |

## Roadmap

- [x] Phase 1: USB Serial connection + basic desktop stats
- [x] Phase 2: Real sensors (soil moisture sensor, water depth sensor)
- [x] Phase 3: Web Backend & BLE bridge on Raspberry Pi
- [x] Phase 4: AI Plant Identification via camera upload
- [ ] Phase 5: Automatic watering schedules & alerting rules
- [ ] Phase 6: Optional Home Assistant integration via MQTT auto-discovery
