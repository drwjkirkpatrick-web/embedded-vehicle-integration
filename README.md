# 🚗 Embedded Vehicle Integration

A **local-first, DIY smart-car system** built on a **Raspberry Pi**.  
Bring any vehicle — from a 1996 Toyota to a 2025 modern CAN-bus car — into the connected era without sending your data to the cloud, without subscription fees, and without giving up ownership of your telemetry.

---

## What This Does

This system turns a Raspberry Pi 4/5 into a vehicle telemetry computer.  It plugs into your car via:

- **OBD-II port** (1996+) for real-time engine data
- **GPIO pins** for relays, sensors, switches, and LEDs
- **USB** for GPS, cameras, microphones, and LTE modems
- **I2C/SPI** for IMUs, ADCs, and thermal cameras
- **HDMI** for dashboard displays

Everything runs **on the Pi**.  No cloud dependency.  No vendor lock-in.

---

## Modules Overview

| Module | What It Does |
|--------|-------------|
| **Core** | Async event bus, config, logging, shared types |
| **OBD** | Reads RPM, speed, coolant, DTCs, clears CELs via ELM327 adapter |
| **GPS** | Real-time location, trip tracking, geofences, "find my car" |
| **IMU** | Motion detection: collisions, hard braking, towing, cornering |
| **GPIO** | Relay control (fuel pump, headlights, block heater, dome light), ADC |
| **Camera** | Dual-camera rolling buffer, event-locked video, AES-256 encryption |
| **Audio** | Voice assistant: wake word, speech-to-text, LLM query, TTS alerts |
| **Storage** | SQLite database, disk monitoring, trip summaries, M.2 health |
| **Display** | HDMI dashboard, CEC control, touch/SWC input, CAN bridge |
| **Telegram** | Remote alerts, commands, snapshots, location sharing |
| **Modern Vehicle** | Multi-CAN bus, UDS diagnostics, radar fusion, TPMS, air quality |
| **New Sensors** | LTE modem, rain sensor, ultrasonic parking, RTK GPS, thermal camera |
| **Security** | Anti-theft immobilizer, encryption vault, OBD intrusion detection |
| **API** | FastAPI REST server for dashboards, mobile apps, diagnostics |
| **Vehicle** | Engine start/stop control, health monitor, maintenance tracking |

---

## Benefits of a Local DIY Smart Car System

### 🔒 Privacy First
- **Your data stays on your Pi.**  No telemetry sent to manufacturers, insurance companies, or advertisers.
- Video, GPS tracks, OBD logs, and voice queries never leave the vehicle unless *you* choose to share them.

### 💰 No Subscriptions
- No $20/month "connected car" fees.
- No cellular plan required (optional LTE for remote access).
- Open-source software — free forever.

### 🔧 Works With *Any* Car
- OBD-II: every gasoline vehicle sold in the US since 1996.
- Modern CAN/UDS: 2008+ vehicles with multi-bus support.
- GPIO relays work on vehicles with *no* electronics at all.

### 🛠️ Fully Hackable
- Want to log a PID your manufacturer hides?  Add it.
- Want to auto-roll windows when it rains?  Wire a relay.
- Want to train a custom ML model on your driving style?  The data is yours.

### 🌐 Offline-Capable
- GPS, OBD, IMU, camera, and voice all work without internet.
- LLM queries can route to a **local model** (Ollama/Llama.cpp) over your phone hotspot when needed.

### 🚀 Expandable
- Add new sensors via I2C, SPI, or USB.
- Write new modules in Python — the event bus makes integration trivial.
- 3D-print enclosures, wire custom PCBs, or just use breadboards.

---

## Hardware Shopping List (Minimal Setup)

| Item | Purpose | Est. Cost |
|------|---------|-----------|
| Raspberry Pi 4/5 (4 GB+) | Main computer | $55 |
| 32 GB+ microSD / M.2 NVMe HAT | Storage | $25 |
| ELM327 Bluetooth/USB adapter | OBD-II interface | $15 |
| u-blox NEO-M8N USB GPS | Location tracking | $20 |
| MPU-6050 I2C module | Motion/collision detection | $5 |
| Relay board (8-channel) | GPIO relay control | $10 |
| Pi Camera Module 3 | Video recording | $35 |
| USB microphone | Voice assistant input | $10 |
| HDMI display (1024×600) | Dashboard | $40 |
| **Total** | | **~$215** |

---

## Quick Start

### 1. Flash Raspberry Pi OS (64-bit)

```bash
# Enable I2C, SPI, camera, serial in raspi-config
sudo raspi-config
```

### 2. Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y \
    python3-pip python3-venv \
    portaudio19-dev libasound2-dev \
    i2c-tools \
    espeak-ng
```

### 3. Clone & Install

```bash
cd ~/
git clone https://github.com/drwjkirkpatrick-web/embedded-vehicle-integration.git
cd embedded-vehicle-integration
python -m venv venv
source venv/bin/activate
pip install -e ".[dev]"
```

### 4. Configure

```bash
# Copy the sample config and edit
cp configs/vehicle.yaml.example configs/vehicle.yaml
nano configs/vehicle.yaml
```

Set your:
- OBD port (`/dev/rfcomm0` for Bluetooth, `/dev/ttyUSB0` for USB)
- GPS port (`/dev/ttyACM0`)
- GPIO relay pin assignments
- Telegram bot token (optional)
- Vehicle year/make/model

### 5. Run Tests (All Hardware Mocked)

```bash
python -m pytest tests/ -v
# 171 tests should pass, 1 skipped
```

### 6. Start the Daemon

```bash
# Run all subsystems
python -m embedded_vehicle.main

# Or run individual tools
vehicle-obd --port /dev/ttyUSB0
vehicle-camera --snapshot
```

---

## Architecture

```
┌─────────────────────────────────────────────┐
│           Raspberry Pi 4/5                    │
│  ┌─────────┐ ┌─────────┐ ┌───────────────┐  │
│  │  OBD    │ │  GPS    │ │   Camera      │  │
│  │ (pyobd) │ │(pynmea2)│ │  (picamera2)  │  │
│  └────┬────┘ └────┬────┘ └───────┬───────┘  │
│  ┌────┴───────────┴───────────────┴───────┐  │
│  │         Async Event Bus                │  │
│  │   (pub/sub between all modules)        │  │
│  └────┬───────────┬───────────────┬───────┘  │
│  ┌────┴────┐ ┌───┴────┐ ┌──────┴───────┐  │
│  │  GPIO   │ │ Storage│ │   Telegram   │  │
│  │(lgpio)  │ │(SQLite)│ │    Bot       │  │
│  └─────────┘ └────────┘ └──────────────┘  │
│  ┌─────────┐ ┌─────────┐ ┌───────────────┐  │
│  │  Audio  │ │  API    │ │   Security    │  │
│  │(PyAudio)│ │(FastAPI) │ │  (Immobilize) │  │
│  └─────────┘ └─────────┘ └───────────────┘  │
└─────────────────────────────────────────────┘
```

All modules communicate via the **async EventBus** — loosely coupled, easy to test, trivial to extend.

---

## API Endpoints

Once running, the FastAPI server exposes:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Vehicle health score |
| GET | `/state` | Engine, GPS, OBD, IMU state |
| POST | `/engine/start` | Start engine (if wired) |
| POST | `/engine/stop` | Stop engine |
| GET | `/obd/snapshot` | Latest OBD PID values |
| GET | `/gps/fix` | Current GPS coordinates |
| GET | `/camera/snapshot` | Capture JPEG |
| POST | `/camera/lock` | Lock video buffer |
| GET | `/storage/stats` | Disk usage |
| GET | `/gpio/relays` | Relay states |
| POST | `/gpio/relay/{name}` | Toggle relay |
| POST | `/telegram/msg` | Send Telegram message |

Protected by **Bearer token auth** and **rate limiting**.

---

## Security Features

- **AES-256 encryption** for video segments and sensitive files
- **OBD intrusion detection** — blocks unauthorized scan tools when armed
- **Anti-theft immobilizer** — fuel-pump kill, tow detection, door-breach alerts
- **Local-only by default** — API binds to `localhost`; remote access via Tailscale/ngrok is opt-in
- **LUKS encryption** supported for M.2 NVMe partition

---

## Development

```bash
# Format code
ruff format src/ tests/

# Lint
ruff check src/ tests/

# Type-check
mypy src/embedded_vehicle

# Run tests with coverage
pytest --cov=embedded_vehicle --cov-report=term-missing
```

---

## Contributing

This is a personal research project.  Issues and PRs welcome, but the primary goal is a **working, reliable, local-first vehicle computer**.

If you add a new sensor or module:
1. Write a mock-based test in `tests/`
2. Add a config section in `core/config.py`
3. Document the wiring in this README
4. Ensure `pytest tests/` passes

---

## License

MIT — use it, fork it, build your own.

---

## Project Roadmap

| Phase | Status |
|-------|--------|
| Core + OBD + GPS + IMU | ✅ Complete |
| GPIO + Camera + Storage + Display | ✅ Complete |
| Audio + Telegram + Modern Vehicle | ✅ Complete |
| Security + API + Vehicle Health | ✅ Complete |
| LTE + Rain + Ultrasonic + RTK + Thermal | ✅ Complete |
| Dashboard GUI (PyQt/Flutter) | 🔄 Next |
| ML driving model (local) | 🔄 Planned |
| CAN FD physical testing | 🔄 Blocked on hardware |

---

*Built with patience, open-source software, and the belief that your car's data belongs to you.*
