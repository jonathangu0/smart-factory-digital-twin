"""Timestamped OPC-UA event logger -> JSONL for analysis.

Polls the meaningful factory tags ~5x/s and appends a JSON line every time a
value changes, with a UTC timestamp. Robust to session drops (read timeout +
auto-reconnect). Run on the factory WiFi:

    python twin/opcua_discovery/event_logger.py

Writes: twin/logs/factory_events.jsonl   (one JSON object per line)
    {"ts": "...Z", "station": "VGR", "tag": "vgr_rot", "value": 677, "prev": 0}

Ctrl+C to stop.
"""
import os
import json
import asyncio
import logging
from datetime import datetime, timezone
from asyncua import Client

logging.getLogger("asyncua").setLevel(logging.CRITICAL)

URL = "opc.tcp://192.168.0.1:4840"
OUT = os.path.join(os.path.dirname(__file__), "..", "logs", "factory_events.jsonl")
DB = 'ns=3;s="gtyp_Interface_Dashboard"."Subscribe".'


def _axis(station, axis):
    base = f'ns=3;s="gtyp_{station}"."{axis}_Axis".'
    return {
        f"{station.lower()}_{axis.lower()}": base + '"di_Actual_Position"',
        f"{station.lower()}_{axis.lower()}_tgt": base + '"di_Target_Position"',
        f"{station.lower()}_{axis.lower()}_reached": base + '"x_Position_Reached"',
    }


TAGS = {"order": DB + '"State_Order"."s_state"'}
for st in ("HBW", "VGR", "MPO", "SLD", "DSI", "DSO"):
    TAGS[f"active_{st}"] = DB + f'"State_{st}"."x_active"'
    TAGS[f"target_{st}"] = DB + f'"State_{st}"."s_target"'
TAGS.update(_axis("VGR", "rotate"))
TAGS.update(_axis("VGR", "vertical"))
TAGS.update(_axis("VGR", "horizontal"))
TAGS.update(_axis("HBW", "Horizontal"))
TAGS.update(_axis("HBW", "Vertical"))
TAGS.update(_axis("SSC", "Horizontal"))
TAGS.update(_axis("SSC", "Vertical"))
TAGS.update({
    "sld_blue": 'ns=3;s="gtyp_SLD"."i_CounterValue_Blue"',
    "sld_white": 'ns=3;s="gtyp_SLD"."i_CounterValue_White"',
    "sld_red": 'ns=3;s="gtyp_SLD"."i_CounterValue_Red"',
    "sld_counter": 'ns=3;s="gtyp_SLD"."i_Counter_Actual"',
    "wp_HBW": 'ns=3;s="gtyp_HBW"."Workpiece"."s_state"',
    "wp_MPO": 'ns=3;s="gtyp_MPO"."Workpiece"."s_state"',
    "wp_SLD": 'ns=3;s="gtyp_SLD"."Workpiece"."s_state"',
    "wp_SSC": 'ns=3;s="gtyp_SSC"."Workpiece"."s_state"',
})


def station_of(tag):
    for st in ("HBW", "VGR", "MPO", "SLD", "SSC", "DSI", "DSO"):
        if st.lower() in tag.lower() or st in tag:
            return st
    return "ORDER"


def now_iso():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


async def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    prev = {}
    n_events = 0
    with open(OUT, "a", encoding="utf-8") as f:
        f.write(json.dumps({"ts": now_iso(), "event": "logger_start", "tags": len(TAGS)}) + "\n")
        f.flush()
        while True:
            client = Client(url=URL)
            client.session_timeout = 30000
            try:
                await client.connect()
                nodes = {k: client.get_node(v) for k, v in TAGS.items()}
                print(f"connected. logging {len(TAGS)} tags -> {OUT}")
                while True:
                    for tag, node in nodes.items():
                        try:
                            val = await asyncio.wait_for(node.read_value(), timeout=2.0)
                        except asyncio.TimeoutError:
                            raise
                        except Exception:
                            continue
                        if tag not in prev:
                            prev[tag] = val
                            continue
                        if val != prev[tag]:
                            rec = {"ts": now_iso(), "station": station_of(tag),
                                   "tag": tag, "value": val, "prev": prev[tag]}
                            f.write(json.dumps(rec) + "\n")
                            f.flush()
                            prev[tag] = val
                            n_events += 1
                            if n_events % 20 == 0:
                                print(f"  {n_events} events logged...")
                    await asyncio.sleep(0.2)
            except Exception as e:
                print(f"connection drop: {e} - reconnecting in 3s")
            finally:
                try:
                    await client.disconnect()
                except Exception:
                    pass
            await asyncio.sleep(3)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped.")
