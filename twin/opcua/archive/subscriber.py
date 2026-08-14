"""
factory_live_view.py

A live terminal view of the fischertechnik training factory. Subscribes to the
factory's MQTT topics and prints a readable, colour-coded stream of what each
station is doing, plus the environment/brightness sensors and order activity.

Press Ctrl+C to stop; a summary of every station's last known state is printed
on exit.
"""

import json
import time
from datetime import datetime

import paho.mqtt.client as mqtt

# ---------------------------------------------------------------------------
# Broker connection. These are the fischertechnik defaults for the local
# broker running on the TXT controller.
# ---------------------------------------------------------------------------
BROKER_HOST = "192.168.0.10"
BROKER_PORT = 1883
BROKER_USER = "txt"
BROKER_PASS = "xtx"

# How often, at most, to print a sensor reading (in seconds). Raise this if
# the sensor lines still feel too chatty, lower it if you want them more often.
SENSOR_PRINT_INTERVAL = 5.0

TOPICS = [
    "f/i/state/#",     # all six station states
    "f/i/stock",       # warehouse contents
    "f/i/order",       # order lifecycle
    "f/i/nfc/ds",      # NFC tag reads
    "i/bme680",        # environment sensor
    "i/ldr",           # brightness sensor
]

# Plain-English station names, so output doesn't read as raw abbreviations.
STATIONS = {
    "hbw": "High-Bay Warehouse",
    "vgr": "Vacuum Gripper",
    "mpo": "Processing Station",
    "sld": "Sorting Line",
    "dsi": "Input Station",
    "dso": "Output Station",
}

# ANSI colour codes, purely so the different event types are easy to pick out
# at a glance in the terminal. If your terminal shows them as garbled
# characters instead of colour, set USE_COLOUR = False below.
USE_COLOUR = True
C = {
    "station": "\033[96m",   # cyan
    "active":  "\033[92m",   # green
    "idle":    "\033[90m",   # grey
    "stock":   "\033[95m",   # magenta
    "order":   "\033[93m",   # yellow
    "nfc":     "\033[94m",   # blue
    "sensor":  "\033[36m",   # dim cyan
    "header":  "\033[1m",    # bold
    "reset":   "\033[0m",
}


def colour(text, kind):
    if not USE_COLOUR:
        return text
    return f"{C.get(kind, '')}{text}{C['reset']}"


# ---------------------------------------------------------------------------
# Live state kept in memory, used to filter repeats and to print a summary
# when the script is stopped.
# ---------------------------------------------------------------------------
last_station_key = {}      # station -> (active, code) last printed
snapshot = {}              # station -> dict of its current condition
last_sensor_print = {}     # topic -> timestamp of last printed reading
event_count = 0


def clock():
    """Wall-clock time for the terminal, so you can correlate what you see on
    screen with what you see happening on the physical factory."""
    return datetime.now().strftime("%H:%M:%S")


def emit(tag, tag_kind, message):
    """Print one aligned event line: time, category tag, then the detail."""
    global event_count
    event_count += 1
    print(f"{colour(clock(), 'idle')} {colour(f'{tag:<8s}', tag_kind)} {message}")


# ---------------------------------------------------------------------------
# Per-category handlers
# ---------------------------------------------------------------------------

def on_station_state(data):
    station = data.get("station", "?")
    active = data.get("active")
    code = data.get("code")
    description = (data.get("description") or "").strip()
    target = (data.get("target") or "").strip()

    # Skip heartbeat repeats; only report when this station actually changed.
    key = (active, code)
    if last_station_key.get(station) == key:
        return
    last_station_key[station] = key

    snapshot[station] = {
        "active": active,
        "code": code,
        "description": description,
        "target": target,
        "seen": clock(),
    }

    name = STATIONS.get(station, station.upper())
    is_active = bool(active)
    status = colour("ACTIVE", "active") if is_active else colour("idle  ", "idle")

    detail = f"{name:<20s} {status}  code={code}"
    if description:
        detail += f"  {description}"
    if target:
        detail += f"  -> {target}"
    emit("STATION", "station", detail)


def on_stock(data):
    items = data.get("stockItems", [])
    filled = []
    for item in items:
        wp = item.get("workpiece")
        loc = item.get("location", "?")
        if wp:
            filled.append(f"{loc}:{wp.get('type','?')[:1]}{wp.get('state','?')[:1].lower()}")

    summary = f"{len(filled)}/{len(items)} slots occupied"
    if filled:
        summary += "  " + ",".join(filled)
    emit("STOCK", "stock", summary)


def on_order(data):
    parts = [f"{k}={v}" for k, v in data.items() if k != "ts"]
    emit("ORDER", "order", ", ".join(parts) if parts else str(data))


def on_nfc(data):
    parts = [f"{k}={v}" for k, v in data.items() if k != "ts"]
    emit("NFC", "nfc", ", ".join(parts) if parts else str(data))


def on_environment(data):
    """Environment sensor: temperature, humidity, pressure, air quality.
    Rate-limited so it doesn't dominate the output."""
    now = time.time()
    if now - last_sensor_print.get("env", 0) < SENSOR_PRINT_INTERVAL:
        return
    last_sensor_print["env"] = now

    t = data.get("t")
    h = data.get("h")
    p = data.get("p")
    iaq = data.get("iaq")

    # Air quality index bands, from the factory's sensor documentation.
    if iaq is None:
        aq_label = ""
    elif iaq <= 50:
        aq_label = "good"
    elif iaq <= 100:
        aq_label = "moderate"
    elif iaq <= 150:
        aq_label = "unhealthy for sensitive groups"
    elif iaq <= 200:
        aq_label = "unhealthy"
    elif iaq <= 300:
        aq_label = "very unhealthy"
    else:
        aq_label = "hazardous"

    detail = (f"temp={t}c  humidity={h}%  pressure={p} hPa  "
              f"air quality index={iaq}")
    if aq_label:
        detail += f" ({aq_label})"
    emit("ENV", "sensor", detail)


def on_brightness(data):
    now = time.time()
    if now - last_sensor_print.get("ldr", 0) < SENSOR_PRINT_INTERVAL:
        return
    last_sensor_print["ldr"] = now
    emit("LIGHT", "sensor", f"brightness={data.get('br')}%  raw resistance={data.get('ldr')}")


# ---------------------------------------------------------------------------
# MQTT callbacks. paho-mqtt calls these for you; you never call them directly.
# ---------------------------------------------------------------------------

def on_connect(client, userdata, flags, rc):
    if rc != 0:
        print(colour(f"\nConnection refused, code {rc}.", "order"))
        print("  0 = success. 4 or 5 usually means a wrong username or "
              "password. Anything else, check the host and port, and that "
              "your Mac is joined to the factory's WiFi network.\n")
        return

    print(colour(f"Connected to broker {BROKER_HOST}:{BROKER_PORT}", "active"))
    for topic in TOPICS:
        client.subscribe(topic)
    print(colour(f"Subscribed to {len(TOPICS)} topic groups.", "idle"))
    print()
    print(colour(f"{'TIME':<8s}  {'TYPE':<8s}  DETAIL", "header"))
    print(colour("-" * 78, "idle"))
    print(colour("Waiting for factory activity. Place an order on the "
                 "dashboard to see the line run.", "idle"))
    print(colour("Press Ctrl+C to stop.", "idle"))
    print()


def on_message(client, userdata, msg):
    try:
        data = json.loads(msg.payload.decode())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return  # e.g. camera frames, not plain JSON. Ignore rather than crash.

    topic = msg.topic
    if topic.startswith("f/i/state/"):
        on_station_state(data)
    elif topic == "f/i/stock":
        on_stock(data)
    elif topic == "f/i/order":
        on_order(data)
    elif topic == "f/i/nfc/ds":
        on_nfc(data)
    elif topic == "i/bme680":
        on_environment(data)
    elif topic == "i/ldr":
        on_brightness(data)


def print_summary():
    """Printed when you stop the script: the state of every station at that
    moment, which is a useful thing to screenshot or read out in a demo."""
    print()
    print(colour("-" * 78, "idle"))
    print(colour("FACTORY STATE AT TIME OF STOPPING", "header"))
    print()
    if not snapshot:
        print("  No station data received. Was the factory running?")
    else:
        for code_name, friendly in STATIONS.items():
            state = snapshot.get(code_name)
            if not state:
                print(f"  {friendly:<20s}  no data received")
                continue
            status = "ACTIVE" if state["active"] else "idle"
            line = f"  {friendly:<20s}  {status:<7s} code={state['code']}"
            if state["description"]:
                line += f"  {state['description']}"
            if state["target"]:
                line += f"  -> {state['target']}"
            line += f"  (last change {state['seen']})"
            print(line)

    print()
    print(f"  Total events shown: {event_count}")
    print()


def main():
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)  # paho-mqtt 2.x
    except AttributeError:
        client = mqtt.Client()  # paho-mqtt 1.x

    client.username_pw_set(BROKER_USER, BROKER_PASS)
    client.on_connect = on_connect
    client.on_message = on_message

    print(f"Connecting to {BROKER_HOST}:{BROKER_PORT} ...")
    try:
        client.connect(BROKER_HOST, BROKER_PORT, keepalive=60)
    except OSError as e:
        print(colour(f"\nCould not reach the broker: {e}", "order"))
        print("  Check that your Mac is joined to the factory WiFi "
              "(TP-Link_8911), that the factory is powered on, and that "
              "the dashboard loads at http://192.168.0.5:1880/ui\n")
        return

    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print_summary()
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
