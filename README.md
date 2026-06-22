# WOP - Water Our Plants 🌱

Smart plant watering system using Arduino + Python desktop app.

## Project Structure

```
WOP---Water-our-plants/
├── arduino/
│   └── wop_basic/
│       └── wop_basic.ino       # Arduino sketch (upload to your board)
├── desktop/
│   ├── main.py                 # Desktop GUI app
│   ├── serial_manager.py       # Serial communication handler
│   └── requirements.txt        # Python dependencies
└── README.md
```

## Quick Start

### 1. Arduino Setup
1. Open `arduino/wop_basic/wop_basic.ino` in Arduino IDE
2. Upload to your Arduino board
3. The sketch sends simulated sensor data until you wire real sensors

### 2. Desktop App Setup
```bash
cd desktop
pip install -r requirements.txt
python main.py
```

### 3. Connect
- Click **Auto-Detect & Connect** to find the Arduino automatically
- Or select a COM port manually and click **Connect to Port**

## WOP Serial Protocol

The Arduino and desktop app communicate using a simple text protocol:

| Direction | Message | Description |
|-----------|---------|-------------|
| Arduino → PC | `WOP:HELLO` | Handshake on startup |
| Arduino → PC | `WOP:DATA:soil,depth,pump,uptime` | Sensor data packet |
| Arduino → PC | `WOP:ACK:command` | Command acknowledged |
| PC → Arduino | `PING` | Connection test |
| PC → Arduino | `PUMP_ON` / `PUMP_OFF` | Pump control |
| PC → Arduino | `STATUS` | Request immediate data |

## Roadmap

- [x] Phase 1: USB Serial connection + basic stats
- [ ] Phase 2: Real sensors (soil moisture sensor, water depth sensor)
- [ ] Phase 3: Bluetooth (HC-05 or HM-10 module)
- [ ] Phase 4: Water pump relay control
- [ ] Phase 5: Automatic watering schedules
