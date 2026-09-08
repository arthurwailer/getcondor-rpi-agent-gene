# GetCondor Drone Agent

Connects any drone to the GetCondor aerial surveillance platform.
Sends real-time telemetry via MQTT (Protobuf) and uploads geotagged photos via HTTP.

## Requirements

- Python 3.8+
- Internet connection (Wi-Fi, 4G, or Starlink)

## Quick Start

```bash
pip install -r requirements.txt
python3 agent.py
```

The agent will interactively ask for:
- **Drone ID** — found in your GetCondor dashboard under Drones
- **MQTT Token** — generated automatically when the drone is created
- **Position** — starting coordinates for the simulated flight
- **Photos folder** — optional, uploads JPG/PNG files during flight

## What Gets Sent

**Telemetry (every 2 seconds via MQTT):**
- GPS: latitude, longitude, altitude
- Flight: speed, heading, pitch, roll, yaw
- Battery: percentage, voltage, temperature, time remaining
- Status: FLYING, HOVERING, LANDING, etc.
- Wind speed

**Media (via HTTP POST):**
- Photos (JPG/PNG) with GPS coordinates and heading
- Videos (MP4) — same endpoint, media_type=VIDEO
- Orthophotos (GeoTIFF) — same endpoint, media_type=GEOTIFF

## Architecture
┌──────────────────────┐         ┌─────────────────────┐
│   Drone / RPi        │         │   GetCondor Cloud    │
│                      │  MQTT   │                      │
│  GPS ──┐             ├────────►│  EMQX Broker         │
│  IMU ──┤  agent.py   │  1883   │    ↓                 │
│  Bat ──┘     │       │         │  telemetry-svc       │
│              │       │  HTTPS  │    ↓                 │
│  Camera ─────┘       ├────────►│  media-svc → MinIO   │
│                      │  443    │                      │
└──────────────────────┘         └─────────────────────┘

## Simulation Mode (Default)

The agent simulates a figure-8 flight pattern with realistic telemetry.
Use this for demos and platform testing.

## Real Hardware Integration

Replace the simulated flight loop with your data source:

**MAVLink (ArduPilot/PX4):**
```python
from pymavlink import mavutil
conn = mavutil.mavlink_connection('/dev/ttyUSB0', baud=57600)
msg = conn.recv_match(type='GLOBAL_POSITION_INT', blocking=True)
lat = msg.lat / 1e7
lon = msg.lon / 1e7
```

**Serial GPS (NMEA):**
```python
import serial
gps = serial.Serial('/dev/ttyUSB0', 9600)
# Parse NMEA sentences
```

**USB Camera:**
```python
from picamera2 import Picamera2
cam = Picamera2()
cam.capture_file('/tmp/photo.jpg')
# Upload via agent's upload_photo()
```

## API Reference

**Telemetry:** MQTT topic `drones/{drone_id}/telemetry` — Protobuf encoded

**Media Upload:** `POST https://getcondor.win/media/upload`
- `drone_id` — string
- `token` — MQTT token for authentication
- `mission_id` — string
- `media_type` — PHOTO, VIDEO, or GEOTIFF
- `latitude`, `longitude`, `altitude`, `heading` — floats
- `file` — multipart file upload

## Support

Contact: info@getcondor.win
