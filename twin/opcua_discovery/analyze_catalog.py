"""Summarize the OPC-UA catalog: per-station drivable tags (state/position/sensor)."""
import json
import os
import re

CAT = os.path.join(os.path.dirname(__file__), "opcua_catalog.json")
KEYWORDS = ("actual", "target", "position", "reached", "active", "state", "step",
            "status", "sensor", "light", "motor", "current", "order", "color",
            "workpiece", "running", "busy", "done", "start", "error", "count")


def station_of(node_id):
    m = re.search(r'gtyp_([A-Za-z_]+?)"', node_id)
    return m.group(1) if m else "other"


def main():
    data = json.load(open(CAT, encoding="utf-8"))
    variables = [r for r in data if r["node_class"] == "Variable"]

    by_station = {}
    for r in variables:
        by_station.setdefault(station_of(r["node_id"]), []).append(r)

    print("VARIABLES PER STATION:")
    for st in sorted(by_station, key=lambda s: -len(by_station[s])):
        print(f"  {st:28} {len(by_station[st])}")

    for st in sorted(by_station):
        rows = by_station[st]
        interesting = [r for r in rows
                       if any(k in (r.get("browse_name") or "").lower() for k in KEYWORDS)]
        if not interesting:
            continue
        print(f"\n===== {st}  ({len(interesting)} interesting of {len(rows)}) =====")
        for r in interesting[:40]:
            bn = r.get("browse_name")
            val = r.get("value")
            # short node id tail
            tail = r["node_id"].split("gtyp_")[-1]
            print(f"  {bn:34} = {val!r:>10}   [{tail}]")


main()
