#!/usr/bin/env python3
"""
GetCondor Drone Agent
Sends telemetry via MQTT (Protobuf) and photos via HTTP to GetCondor.
"""
import os, sys, time, math, random, requests
import paho.mqtt.client as mqtt
import telemetry_pb2 as pb

DEFAULT_BROKER = "getcondor.win"
DEFAULT_PORT = 1883
DEFAULT_API = "https://getcondor.win"
TELEMETRY_INTERVAL = 2

def on_connect(client, userdata, flags, rc, properties=None):
    rc_code = rc.value if hasattr(rc, "value") else rc
    codes = {0: "OK", 4: "Bad credentials", 5: "Not authorized"}
    print(f"\n  ✅ MQTT Connected: {codes.get(rc_code, f'Error {rc_code}')}")
    if rc_code != 0:
        print("  ❌ Authentication failed. Please check drone_id and token.")
        sys.exit(1)

def build_telemetry(drone_id, mission_id, lat, lon, alt, heading, speed, battery_pct):
    msg = pb.TelemetryMessage()
    msg.drone_id = drone_id
    msg.mission_id = mission_id
    msg.timestamp = int(time.time() * 1000)
    msg.position.latitude = lat
    msg.position.longitude = lon
    msg.position.altitude = alt
    msg.position.speed = speed
    msg.position.heading = heading
    msg.position.accuracy = 1.5
    msg.status.state = pb.FLYING
    msg.status.pitch = random.uniform(-5, 5)
    msg.status.roll = random.uniform(-3, 3)
    msg.status.yaw = heading
    msg.status.wind_speed = random.uniform(1, 8)
    msg.battery.percentage = battery_pct
    msg.battery.voltage = 22.2 + (battery_pct / 100) * 3.0
    msg.battery.temperature = random.uniform(25, 40)
    msg.battery.time_remaining = int(battery_pct * 12)
    return msg

def upload_photo(api_url, drone_id, mqtt_token, mission_id, lat, lon, alt, heading, filepath):
    with open(filepath, "rb") as f:
        r = requests.post(f"{api_url}/media/upload", files={"file": (os.path.basename(filepath), f)},
            data={"drone_id": drone_id, "token": mqtt_token, "mission_id": mission_id,
                  "media_type": "PHOTO", "latitude": str(lat), "longitude": str(lon),
                  "altitude": str(alt), "heading": str(heading)}, timeout=30)
        print(f"  📸 Photo uploaded: {'OK' if r.ok else 'FAIL'} ({r.status_code})")

def ask(prompt, default=None):
    if default:
        val = input(f"  {prompt} [{default}]: ").strip()
        return val if val else default
    while True:
        val = input(f"  {prompt}: ").strip()
        if val: return val
        print("    ⚠️  This field is required")

def setup():
    print("\n" + "=" * 50)
    print("  🛩️  GetCondor Drone Agent")
    print("=" * 50)

    print("\n📋 DRONE DATA (you can find this in the GetCondor dashboard)\n")
    drone_id = ask("Drone ID (e.g., drone-01)")
    token = ask("MQTT Token")

    print("\n🌐 CONNECTION\n")
    broker = ask("MQTT Broker", DEFAULT_BROKER)
    port = int(ask("MQTT Port", str(DEFAULT_PORT)))
    api = ask("API URL", DEFAULT_API)

    print("\n📍 INITIAL POSITION FOR SIMULATED FLIGHT\n")
    lat = float(ask("Latitude", "38.7169"))
    lon = float(ask("Longitude", "-9.1399"))
    alt = float(ask("Altitude (meters)", "120"))

    print("\n📸 PHOTOS (optional)\n")
    photos_dir = input("  Folder with JPG photos (Enter to skip): ").strip() or None
    if photos_dir and not os.path.isdir(photos_dir):
        print(f"    ⚠️  Folder '{photos_dir}' does not exist, photos disabled")
        photos_dir = None

    return {
        "drone_id": drone_id, "token": token,
        "broker": broker, "port": port, "api": api,
        "lat": lat, "lon": lon, "alt": alt,
        "photos_dir": photos_dir
    }

def fly(cfg):
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cfg["drone_id"])
    client.username_pw_set(cfg["drone_id"], cfg["token"])
    client.on_connect = on_connect

    print(f"\n🔌 Connecting to {cfg['broker']}:{cfg['port']}...")
    client.connect(cfg["broker"], cfg["port"], 60)
    client.loop_start()
    time.sleep(2)

    topic = f"drones/{cfg['drone_id']}/telemetry"
    mission_id = f"mission-{int(time.time())}"
    battery = 100.0
    step = 0

    print(f"\n🛫 FLIGHT STARTED")
    print(f"  Drone:     {cfg['drone_id']}")
    print(f"  Mission:   {mission_id}")
    print(f"  Start:     ({cfg['lat']}, {cfg['lon']}) at {cfg['alt']}m")
    print(f"  Photos:    {'Every ~60s from ' + cfg['photos_dir'] if cfg['photos_dir'] else 'Disabled'}")
    print(f"\n  Ctrl+C to land\n")

    try:
        while battery > 5:
            t = (step / 60.0) * 2 * math.pi
            scale = 0.005
            lat = cfg["lat"] + scale * 0.7 * math.sin(t)
            lon = cfg["lon"] + scale * math.sin(t) * math.cos(t)
            alt = cfg["alt"] + math.sin(t * 2) * 10
            heading = (math.degrees(math.atan2(
                math.cos(t)*math.cos(t) - math.sin(t)*math.sin(t), 0.7*math.cos(t))) + 360) % 360
            speed = 8.0 + random.uniform(-2, 2)
            battery -= 0.02

            msg = build_telemetry(cfg["drone_id"], mission_id, lat, lon, alt, heading, speed, battery)
            client.publish(topic, msg.SerializeToString(), qos=1)
            print(f"  📡 [{step:04d}] lat={lat:.6f} lon={lon:.6f} alt={alt:.1f}m hdg={heading:.0f}° bat={battery:.1f}%")

            if cfg["photos_dir"] and step > 0 and step % 30 == 0:
                photos = [f for f in os.listdir(cfg["photos_dir"]) if f.lower().endswith(('.jpg','.jpeg','.png'))]
                if photos:
                    upload_photo(cfg["api"], cfg["drone_id"], cfg["token"], mission_id,
                               lat, lon, alt, heading, os.path.join(cfg["photos_dir"], random.choice(photos)))

            step += 1
            time.sleep(TELEMETRY_INTERVAL)

    except KeyboardInterrupt:
        print(f"\n\n🛬 LANDING...")
        print(f"  Duration: {step * TELEMETRY_INTERVAL}s")
        print(f"  Remaining battery: {battery:.1f}%")
    finally:
        client.loop_stop()
        client.disconnect()
        print("  🔌 Disconnected from MQTT\n")

if __name__ == "__main__":
    cfg = setup()
    fly(cfg)