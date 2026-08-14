"""
live_data_feed.py

A live IoT data feed for the fischertechnik training factory, built for driving
a DIGITAL TWIN.

On top of just printing MQTT traffic (see subscriber.py), this script:

  * Maintains a single normalized, in-memory model of the whole factory
    (stations, sensors, actuators, stock, orders, NFC) that always reflects
    the latest known state.
  * Persists that model to `factory_state.json` after every change, written
    atomically so a twin process can safely poll/read it at any time.
  * Appends every decoded message to `factory_events.jsonl` (one JSON object
    per line) so you have a full time-series history for replay/analytics.
  * Captures ANY topic it sees - even ones it doesn't have a dedicated handler
    for - into a generic `raw` store, so no sensor/actuator data is ever lost.
  * Prints a clean, aligned, colour-coded stream so a human can watch along.

Press Ctrl+C to stop; a summary of every station's last known state prints on
exit, and the final `factory_state.json` is left on disk for the twin.
"""

import json
import os
import time
import tempfile
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

# ---------------------------------------------------------------------------
# Broker connection. These are the fischertechnik defaults for the local
# broker running on the TXT controller.
# ---------------------------------------------------------------------------
BROKER_HOST = "192.168.0.10"
BROKER_PORT = 1883
BROKER_USER = "txt"
BROKER_PASS = "xtx"

# How often, at most, to PRINT a sensor reading (seconds). Note: this only
# throttles console noise - the state model and JSONL log are always updated.
SENSOR_PRINT_INTERVAL = 5.0

# Where the digital twin reads from. The snapshot is the "current truth";
# the events log is the full history.
STATE_FILE = "factory_state.json"
EVENTS_FILE = "factory_events.jsonl"

# Curated topics we understand and pretty-print. Set SUBSCRIBE_ALL = True to
# additionally tap EVERYTHING on the broker (still captured into `raw`), which
# is handy when you're discovering what actuator/transport topics exist.
TOPICS = [
    "f/i/state/#",     # all six station states
    "f/i/stock",       # warehouse contents
    "f/i/order",       # order lifecycle
    "f/i/nfc/ds",      # NFC tag reads
    "i/bme680",        # environment sensor (temp/humidity/pressure/air quality)
    "i/ldr",           # brightness sensor
]
SUBSCRIBE_ALL = False        # flip to True to also subscribe to "#"

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
# at a glance. If your terminal shows garbled characters, set USE_COLOUR=False.
USE_COLOUR = True
C = {
    "station": "\033[96m",   # cyan
    "active":  "\033[92m",   # green
    "idle":    "\033[90m",   # grey
    "stock":   "\033[95m",   # magenta
    "order":   "\033[93m",   # yellow
    "nfc":     "\033[94m",   # blue
    "sensor":  "\033[36m",   # dim cyan
    "raw":     "\033[35m",   # purple
    "header":  "\033[1m",    # bold
    "reset":   "\033[0m",
}


def colour(text, kind):
    if not USE_COLOUR:
        return text
    return f"{C.get(kind, '')}{text}{C['reset']}"


# ---------------------------------------------------------------------------
# The live factory model. This single dict IS the digital-twin state; every
# handler updates a slice of it, and we then persist the whole thing.
# ---------------------------------------------------------------------------
STATE = {
    "meta": {
        "updated": None,        # ISO-8601 timestamp of last change
        "updated_epoch": None,  # same, as a float epoch (easy for maths)
        "event_count": 0,
        "source_broker": f"{BROKER_HOST}:{BROKER_PORT}",
    },
    "stations": {},             # code -> station state
    "sensors": {},              # "environment" / "brightness" -> readings
    "stock": {},                # latest warehouse contents
    "orders": {},               # latest order payload
    "nfc": {},                  # latest NFC read
    "raw": {},                  # topic -> {payload, received} for anything else
}

# Bookkeeping that shouldn't live in the persisted model.
last_station_key = {}      # station -> (active, code) last PRINTED
last_sensor_print = {}     # topic -> last time we PRINTED this sensor


# ---------------------------------------------------------------------------
# Time + output helpers
# ---------------------------------------------------------------------------

def now_iso():
    """UTC ISO-8601 timestamp - unambiguous and sortable, good for a twin."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def clock():
    """Short local wall-clock for the human-facing console lines."""
    return datetime.now().strftime("%H:%M:%S")


def touch_meta():
    """Stamp the model as freshly updated and bump the event counter."""
    STATE["meta"]["updated"] = now_iso()
    STATE["meta"]["updated_epoch"] = time.time()
    STATE["meta"]["event_count"] += 1


def save_state():
    """Atomically rewrite factory_state.json so a reader never sees a
    half-written file (write to a temp file in the same dir, then rename)."""
    directory = os.path.dirname(os.path.abspath(STATE_FILE)) or "."
    fd, tmp = tempfile.mkstemp(dir=directory, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(STATE, f, indent=2, sort_keys=False)
        os.replace(tmp, STATE_FILE)
    except Exception:
        # Never let a persistence hiccup take down the live feed.
        if os.path.exists(tmp):
            os.remove(tmp)


def log_event(topic, data):
    """Append the raw decoded message to the time-series history."""
    record = {"ts": now_iso(), "topic": topic, "data": data}
    try:
        with open(EVENTS_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass  # history is best-effort; don't crash the feed over it


def emit(tag, tag_kind, message):
    """Print one aligned event line: time, category tag, then the detail."""
    print(f"{colour(clock(), 'idle')} {colour(f'{tag:<8s}', tag_kind)} {message}")


# ---------------------------------------------------------------------------
# Per-category handlers. Each updates STATE, then prints (throttled where the
# data is chatty). Persistence + history are handled centrally in on_message.
# ---------------------------------------------------------------------------

def on_station_state(data):
    station = data.get("station", "?")
    active = data.get("active")
    code = data.get("code")
    description = (data.get("description") or "").strip()
    target = (data.get("target") or "").strip()

    STATE["stations"][station] = {
        "name": STATIONS.get(station, station.upper()),
        "active": bool(active),
        "code": code,
        "description": description,
        "target": target,
        "seen": now_iso(),
    }

    # Only PRINT when this station actually changed (skip heartbeat repeats).
    key = (active, code)
    if last_station_key.get(station) == key:
        return
    last_station_key[station] = key

    name = STATIONS.get(station, station.upper())
    status = colour("ACTIVE", "active") if active else colour("idle  ", "idle")
    detail = f"{name:<20s} {status}  code={code}"
    if description:
        detail += f"  {description}"
    if target:
        detail += f"  -> {target}"
    emit("STATION", "station", detail)


def on_stock(data):
    items = data.get("stockItems", [])
    slots = []
    filled = []
    for item in items:
        wp = item.get("workpiece") or {}
        loc = item.get("location", "?")

        # An EMPTY slot still arrives as a workpiece object, just with blank
        # type/state/id. A non-empty dict is truthy in Python, so checking
        # `if wp:` would count empty slots as full and the total would never
        # move on delivery/pickup. Treat a slot as occupied only when the
        # workpiece actually carries content.
        wp_type = (wp.get("type") or "").strip()
        wp_state = (wp.get("state") or "").strip()
        wp_id = (wp.get("id") or "").strip()
        occupied = bool(wp_type or wp_id)

        slot = {"location": loc, "occupied": occupied, "workpiece": None}
        if occupied:
            slot["workpiece"] = {
                "type": wp_type or None,
                "state": wp_state or None,
                "id": wp_id or None,
            }
            filled.append(f"{loc}:{(wp_type or '?')[:1]}{(wp_state or '?')[:1].lower()}")
        slots.append(slot)

    STATE["stock"] = {
        "slots": slots,
        "occupied": len(filled),
        "capacity": len(items),
        "seen": now_iso(),
    }

    summary = f"{len(filled)}/{len(items)} slots occupied"
    if filled:
        summary += "  " + ", ".join(filled)
    emit("STOCK", "stock", summary)


def on_order(data):
    STATE["orders"] = {**data, "seen": now_iso()}
    parts = [f"{k}={v}" for k, v in data.items() if k != "ts"]
    emit("ORDER", "order", ", ".join(parts) if parts else str(data))


def on_nfc(data):
    STATE["nfc"] = {**data, "seen": now_iso()}
    parts = [f"{k}={v}" for k, v in data.items() if k != "ts"]
    emit("NFC", "nfc", ", ".join(parts) if parts else str(data))


def _air_quality_label(iaq):
    if iaq is None:
        return ""
    if iaq <= 50:
        return "good"
    if iaq <= 100:
        return "moderate"
    if iaq <= 150:
        return "unhealthy for sensitive groups"
    if iaq <= 200:
        return "unhealthy"
    if iaq <= 300:
        return "very unhealthy"
    return "hazardous"


def on_environment(data):
    """Environment sensor: temperature, humidity, pressure, air quality."""
    t = data.get("t")
    h = data.get("h")
    p = data.get("p")
    iaq = data.get("iaq")
    aq_label = _air_quality_label(iaq)

    STATE["sensors"]["environment"] = {
        "temperature_c": t,
        "humidity_pct": h,
        "pressure_hpa": p,
        "air_quality_index": iaq,
        "air_quality_label": aq_label,
        "seen": now_iso(),
    }

    # Throttle only the console print, not the model/history.
    now = time.time()
    if now - last_sensor_print.get("env", 0) < SENSOR_PRINT_INTERVAL:
        return
    last_sensor_print["env"] = now

    detail = f"temp={t}c  humidity={h}%  pressure={p} hPa  air quality index={iaq}"
    if aq_label:
        detail += f" ({aq_label})"
    emit("ENV", "sensor", detail)


def on_brightness(data):
    STATE["sensors"]["brightness"] = {
        "brightness_pct": data.get("br"),
        "raw_resistance": data.get("ldr"),
        "seen": now_iso(),
    }

    now = time.time()
    if now - last_sensor_print.get("ldr", 0) < SENSOR_PRINT_INTERVAL:
        return
    last_sensor_print["ldr"] = now
    emit("LIGHT", "sensor",
         f"brightness={data.get('br')}%  raw resistance={data.get('ldr')}")


def on_generic(topic, data):
    """Catch-all for any topic without a dedicated handler (e.g. actuator
    commands, transport/FTS state, or topics we haven't mapped yet). We still
    record it so the twin sees the complete picture."""
    STATE["raw"][topic] = {"payload": data, "seen": now_iso()}

    now = time.time()
    if now - last_sensor_print.get(topic, 0) < SENSOR_PRINT_INTERVAL:
        return
    last_sensor_print[topic] = now

    preview = data if isinstance(data, (dict, list)) else str(data)
    text = json.dumps(preview, separators=(",", ":"))
    if len(text) > 90:
        text = text[:87] + "..."
    emit("RAW", "raw", f"{topic}  {text}")


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
    if SUBSCRIBE_ALL:
        client.subscribe("#")
        print(colour("Subscribed to ALL topics (# wildcard).", "idle"))
    print(colour(f"Subscribed to {len(TOPICS)} curated topic groups.", "idle"))
    print(colour(f"State  -> {os.path.abspath(STATE_FILE)}", "idle"))
    print(colour(f"Events -> {os.path.abspath(EVENTS_FILE)}", "idle"))
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
    else:
        on_generic(topic, data)

    # Centralised: stamp, persist current truth, append to history.
    touch_meta()
    save_state()
    log_event(topic, data)


def print_summary():
    """Printed when you stop the script: the state of every station at that
    moment, which is a useful thing to screenshot or read out in a demo."""
    print()
    print(colour("-" * 78, "idle"))
    print(colour("FACTORY STATE AT TIME OF STOPPING", "header"))
    print()

    stations = STATE["stations"]
    if not stations:
        print("  No station data received. Was the factory running?")
    else:
        for code_name, friendly in STATIONS.items():
            state = stations.get(code_name)
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

    env = STATE["sensors"].get("environment")
    light = STATE["sensors"].get("brightness")
    if env or light:
        print()
        print(colour("SENSORS", "header"))
        if env:
            print(f"  environment  temp={env['temperature_c']}c  "
                  f"humidity={env['humidity_pct']}%  "
                  f"pressure={env['pressure_hpa']} hPa  "
                  f"iaq={env['air_quality_index']} ({env['air_quality_label']})")
        if light:
            print(f"  brightness   {light['brightness_pct']}%  "
                  f"(raw resistance {light['raw_resistance']})")

    if STATE["raw"]:
        print()
        print(colour(f"OTHER TOPICS CAPTURED ({len(STATE['raw'])})", "header"))
        for topic in sorted(STATE["raw"]):
            print(f"  {topic}")

    print()
    print(f"  Total events shown: {STATE['meta']['event_count']}")
    print(f"  Final snapshot written to: {os.path.abspath(STATE_FILE)}")
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
