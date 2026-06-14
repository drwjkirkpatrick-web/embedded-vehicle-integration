# Embedded Vehicle Integration

Hermes Agent × Raspberry Pi 5 × Any Vehicle — Universal telemetry, security, and AI copilot platform.

**150+ integrations** | **Dual-camera dashcam** | **OBD-II/CAN diagnostics** | **Voice copilot** | **Modern vehicle adapter**

Works with any vehicle: 1996 pre-CAN classics, 2008-2015 CAN-era, 2016+ modern with CAN-FD, 2020+ with ADAS radar and driver monitoring.

---

## Quick Start

```bash
# 1. Flash Pi 5 with Raspberry Pi OS, enable I2C/SPI/camera
# 2. Install M.2 HAT+ with 1TB NVMe (optional but recommended for video)
# 3. Clone and install
git clone https://github.com/drwjkirkpatrick-web/embedded-vehicle-integration.git
cd embedded-vehicle-integration
sudo bash scripts/install.sh

# 4. Edit config for your vehicle
sudo nano /etc/vehicle/vehicle.yaml

# 5. Run bench test before vehicle install
sudo .venv/bin/python scripts/bench_test.py --all

# 6. Start daemon
sudo systemctl start vehicle-daemon
```

---

## Vehicle Compatibility

| Era | Year | Protocol | Supported | Adapter |
|-----|------|----------|-----------|---------|
| **Pre-CAN** | 1996-2007 | ISO 9141-2, KWP2000 | ✅ Full | ELM327 USB |
| **Early CAN** | 2008-2015 | CAN 2.0A/B (500 kbps) | ✅ Full | CANable Pro / PiCAN2 |
| **Modern CAN** | 2016-2020 | CAN-FD (2-5 Mbps) | ✅ Full | CANable Pro / Waveshare CAN-FD |
| **ADAS Era** | 2020+ | Multi-CAN + UDS + SecOC | ✅ Partial | CANable Pro + aftermarket radar |

### How to configure for your vehicle

```yaml
# /etc/vehicle/vehicle.yaml
vehicle:
  year: 2015          # Your vehicle year
  make: "Honda"       # Your make
  model: "Civic"      # Your model
  vin: ""             # Optional: auto-detected via OBD/CAN
  obd_protocol: "CAN" # CAN, ISO9141, KWP2000, or auto
  fuel_type: "gasoline"
  tank_capacity_l: 50
  engine_displacement_l: 1.8

# Enable the right adapter
obd:
  enabled: true
  port: "/dev/ttyUSB0"    # For ELM327 (pre-CAN)
  # For CAN vehicles, use modern_vehicle instead:

modern_vehicle:
  enabled: true           # Enable for 2008+ vehicles
  can_primary: "can0"     # PT CAN (powertrain)
  can_secondary: "can1" # Body/chassis CAN
  can_fd: false           # true for 2020+ vehicles
  uds_enabled: true       # Unified Diagnostic Services
  tpms_enabled: true      # Direct TPMS via RTL-SDR
  radar_enabled: false    # Aftermarket radar add-on
  dms_enabled: false      # Driver monitoring camera
```

---

## Hardware Stack

| Component | Part | Interface | Status | Vehicles |
|-----------|------|-----------|--------|----------|
| **Pi 5** | Raspberry Pi 5 8GB | — | ✅ Core | All |
| **Storage** | Pineberry Pi M.2 HAT+ 1TB NVMe | PCIe | ✅ 72hr rolling buffer | All |
| **OBD-II** | ELM327 USB | USB | ✅ Pre-CAN (1996-2007) | Pre-CAN |
| **CAN Bus** | CANable Pro / PiCAN2 | USB/SPI | ✅ CAN 2.0B | 2008+ |
| **CAN-FD** | Waveshare CAN-FD HAT | SPI | ✅ Up to 5 Mbps | 2020+ |
| **GPS** | u-blox NEO-M8N | UART/USB | ✅ NMEA, geofence | All |
| **RTK GPS** | u-blox ZED-F9P | UART | 🆕 2cm accuracy | All |
| **Camera (front)** | Pi Camera Module 3 | CSI0 | ✅ 1080p H.264 | All |
| **Camera (rear/cabin)** | Pi Camera Module 3 | CSI1 | ✅ 1080p H.264 | All |
| **Thermal** | MLX90640 / FLIR Lepton | I2C/SPI | 🆕 Night vision | All |
| **IMU** | MPU-6050 / MPU-9250 | I2C | ✅ 100Hz, collision detect | All |
| **LTE** | Quectel EC25 / SIM7600 | USB | 🆕 Always-on 4G | All |
| **Rain** | IR reflectance module | ADC (MCP3008) | 🆕 Auto wipers | All |
| **Ultrasonic** | HC-SR04 × 8 | GPIO | 🆕 Parking assist | All |
| **Air quality** | SCD40 + SGP40 + SPS30 | I2C | 🆕 CO2/VOC/PM2.5 | All |
| **Display** | JoyBring 10.1" / any HDMI touchscreen | HDMI + USB | 🆕 Head-unit | All |
| **Audio** | USB mic + AUX/FM | USB/3.5mm | ✅ Voice copilot | All |
| **Power** | 12V→5V/5A buck + relay board | Hardwired | ✅ IGN-switched | All |

---

## Module Architecture

```
Event Bus (async pub/sub, 30+ event types)
    ├── Core
    │   ├── config.py          # Pydantic settings, 15 subsystems
    │   ├── __init__.py        # EventBus, 30 event types, logging
    │   └── main.py            # Daemon orchestrator
    │
    ├── Pre-CAN Vehicles (1996-2007)
    │   └── obd/interface.py   # ELM327, ISO 9141-2, KWP2000, 15 PIDs
    │
    ├── Modern Vehicles (2008+)
    │   ├── modern_vehicle/can_multibus.py    # Multi-CAN (PT/body/chassis)
    │   ├── modern_vehicle/uds_client.py        # UDS diagnostic
    │   ├── modern_vehicle/tpms_direct.py       # Direct RF TPMS
    │   ├── modern_vehicle/radar_fusion.py      # ADAS radar
    │   ├── modern_vehicle/driver_monitor.py  # DMS (drowsiness)
    │   └── modern_vehicle/interior_sensing.py # Air quality
    │
    ├── Universal (All Vehicles)
    │   ├── camera/recorder.py        # Dual 1080p, rolling buffer, AES-256
    │   ├── camera/picamera2_backend.py  # Real Pi Camera 3 H.264
    │   ├── gps/tracker.py            # NMEA, geofence, trip logging
    │   ├── imu/sensor.py           # MPU-6050, collision/tow detection
    │   ├── gpio/controller.py       # lgpio relays, inputs, MCP3008 ADC
    │   ├── audio/assistant.py       # Wake word, LLM query, TTS
    │   ├── audio/whisper_stt.py     # faster-whisper local STT
    │   ├── telegram/bot.py          # 10 commands, auto-alerts
    │   ├── storage/manager.py       # aiosqlite, 5 tables, disk monitor
    │   ├── connectivity/lte.py      # 4G LTE, NTRIP, MQTT, SMS
    │   ├── sensors/rain_sensor.py    # Auto wipers
    │   ├── sensors/ultrasonic_array.py # 8× parking sensors
    │   ├── sensors/rtk_gps.py       # Centimeter GPS
    │   └── sensors/thermal_camera.py  # Night vision
    │
    └── Display (Optional Head-Unit)
        ├── display/joybring.py       # Main controller
        ├── display/hdmi_sink.py      # HDMI, EDID, CEC
        ├── display/touch_input.py    # USB multi-touch
        ├── display/can_bridge.py     # Vehicle CAN ↔ head-unit
        ├── display/steering_wheel.py # ADC resistor ladder
        ├── display/dashboard.py      # Kivy GUI, 8 pages
        └── display/radio.py          # FM/AM/internet radio
```

---

## CLI Tools

```bash
# Individual subsystem testing
vehicle-obd --watch rpm,speed,coolant   # Live OBD monitor (pre-CAN)
vehicle-camera --snapshot               # Capture still image
vehicle-camera --record 60              # Record 60-second clip

# Bench test (run before vehicle install)
python scripts/bench_test.py --all
python scripts/bench_test.py --obd --gps --imu --gpio --camera --audio --lte
```

---

## Configuration

Copy and edit for your vehicle:

```bash
cp configs/vehicle.example.yaml /etc/vehicle/vehicle.yaml
cp configs/environment.example /etc/vehicle/environment
sudo chmod 600 /etc/vehicle/environment
```

Key sections in `vehicle.yaml`:
- `vehicle`: year, make, model, VIN, engine, fuel type, tank capacity
- `obd`: port, protocol (auto/CAN/ISO9141/KWP2000), PIDs to poll
- `modern_vehicle`: CAN bus config, UDS, TPMS, radar, DMS, air quality
- `camera`: resolution, buffer duration, encryption
- `gps`: port, baud, geofence zones
- `gpio`: relay pins, input pins, ADC channels
- `audio`: sample rate, wake word, LLM endpoint
- `telegram`: bot token, authorized chat IDs
- `display`: resolution, touch, CAN bridge, SWC
- `lte`: APN, NTRIP caster, MQTT broker
- `rain`: thresholds, wiper pins
- `ultrasonic`: sensor count, pins, alert distances
- `rtk`: port, NTRIP credentials
- `thermal`: model, overlay alpha, hotspot threshold

### Vehicle-specific examples

**1996 Honda Civic (pre-CAN):**
```yaml
vehicle:
  year: 1996
  make: "Honda"
  model: "Civic"
  obd_protocol: "ISO9141"
obd:
  enabled: true
  port: "/dev/ttyUSB0"
modern_vehicle:
  enabled: false
```

**2015 Ford F-150 (CAN 2.0B):**
```yaml
vehicle:
  year: 2015
  make: "Ford"
  model: "F-150"
  obd_protocol: "CAN"
obd:
  enabled: false
modern_vehicle:
  enabled: true
  can_primary: "can0"
  can_secondary: "can1"
  can_fd: false
  uds_enabled: true
```

**2022 Tesla Model 3 (CAN-FD, encrypted):**
```yaml
vehicle:
  year: 2022
  make: "Tesla"
  model: "Model 3"
  obd_protocol: "CAN_FD"
modern_vehicle:
  enabled: true
  can_primary: "can0"
  can_fd: true
  uds_enabled: true
  # Note: Tesla uses proprietary encryption; UDS may be limited
```

---

## Test Suite

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific module
python -m pytest tests/test_new_sensors.py -v
python -m pytest tests/test_modern_vehicle.py -v
python -m pytest tests/test_display.py -v
```

| Module | Tests | Status |
|--------|-------|--------|
| Core | 12 | ✅ All pass |
| OBD (pre-CAN) | 10 | ✅ Mocked |
| GPS | 6 | ✅ Mocked |
| IMU | 7 | ✅ Mocked |
| GPIO | 10 | ✅ Mocked |
| Camera | 9 | ✅ Mocked |
| Audio | 7 | ⚠️ 5 need tuning |
| Storage | 10 | ✅ All pass |
| Telegram | 8 | ✅ Mocked |
| Display | 11 | ✅ Mocked |
| Modern Vehicle | 13 | ✅ Mocked |
| New Sensors | 14 | ✅ All pass |
| **Total** | **117** | **~107 pass** |

---

## Systemd Service

```bash
# Install auto-start
sudo cp scripts/vehicle-daemon.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable vehicle-daemon
sudo systemctl start vehicle-daemon

# Check status
sudo systemctl status vehicle-daemon
sudo journalctl -u vehicle-daemon -f
```

---

## Safety & Legal

⚠️ **This system is for diagnostics, logging, and driver assistance only.**

- **No physical control** of brakes, steering, or throttle
- **Relay controls** (wipers, HVAC, lights) are advisory — driver override always works
- **OBD-II is read-only** by default — no ECU writes without explicit unlock
- **Dashcam encryption** uses AES-256 — keys in `/etc/vehicle/environment`
- **DMS camera** is IR + local processing — no video leaves the Pi
- **Check local laws** for dashcam, phone use, and OBD-II modifications
- **Modern vehicle CAN** is monitored only — no injection without SecOC bypass

---

## Roadmap

| Priority | Feature | Module | Est. Cost | Vehicles |
|----------|---------|--------|-----------|----------|
| 1 | 4G LTE HAT | `connectivity/lte.py` | $60 | All |
| 2 | RTK GPS | `sensors/rtk_gps.py` | $200 | All |
| 3 | Direct TPMS | `modern_vehicle/tpms_direct.py` | $30 | 2007+ |
| 4 | Interior air quality | `modern_vehicle/interior_sensing.py` | $65 | All |
| 5 | Aftermarket radar | `modern_vehicle/radar_fusion.py` | $150 | All |
| 6 | Thermal camera | `sensors/thermal_camera.py` | $60-200 | All |
| 7 | DMS IR camera | `modern_vehicle/driver_monitor.py` | $40 | All |
| 8 | Rain sensor | `sensors/rain_sensor.py` | $10 | All |
| 9 | Ultrasonic parking | `sensors/ultrasonic_array.py` | $25 | All |
| 10 | CAN-FD support | `modern_vehicle/can_multibus.py` | $40 | 2020+ |
| 11 | Mobileye 6 (AEB) | External | $1000 | All |
| 12 | LIDAR (SLAM) | New module | $600 | All |

---

## Documentation

- [`docs/SHOPPING_LIST.md`](docs/SHOPPING_LIST.md) — Complete parts list with vendors, prices, wiring
- [`configs/vehicle.example.yaml`](configs/vehicle.example.yaml) — Full configuration template
- [`configs/environment.example`](configs/environment.example) — Secrets template
- [`scripts/bench_test.py`](scripts/bench_test.py) — Hardware verification before install
- [`scripts/install.sh`](scripts/install.sh) — One-shot installer

---

## License

MIT — See [LICENSE](LICENSE) (create one if needed)

---

## Author

Walker — Oregon naturopathic physician, poultry scientist, Hermes Agent builder.

GitHub: [@drwjkirkpatrick-web](https://github.com/drwjkirkpatrick-web)

---

## Acknowledgments

- Original `pi-camry-integration` was built for a 1996 Toyota Camry
- This generic version extends support to all vehicles 1996–2025+
- OBD-II support via `python-obd` and ELM327 community knowledge
- CAN support via `python-can` and CANable Pro open hardware
- RTK GPS via u-blox and RTKLIB open-source
- Whisper STT via OpenAI's faster-whisper
