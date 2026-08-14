"""Convert the browsed OPC-UA catalog into a clean CSV node reference for analysis.
Columns: station, browse_name, node_class, value_type, value, node_id, path
"""
import json
import os
import csv
import re

HERE = os.path.dirname(__file__)
CAT = os.path.join(HERE, "opcua_catalog.json")
OUT = os.path.join(HERE, "opcua_nodes.csv")


def station_of(node_id):
    m = re.search(r'gtyp_([A-Za-z_]+?)"', node_id or "")
    return m.group(1) if m else ("(root)" if "gtyp_" not in (node_id or "") else "other")


def vtype(v):
    if v is None:
        return ""
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, int):
        return "int"
    if isinstance(v, float):
        return "float"
    if isinstance(v, str):
        return "string"
    return type(v).__name__


def main():
    data = json.load(open(CAT, encoding="utf-8"))
    rows = []
    for r in data:
        val = r.get("value")
        # keep complex ExtensionObject values short in the CSV
        sval = "" if val is None else str(val)
        if len(sval) > 120:
            sval = sval[:117] + "..."
        rows.append({
            "station": station_of(r.get("node_id")),
            "browse_name": r.get("browse_name") or "",
            "node_class": r.get("node_class") or "",
            "value_type": vtype(val),
            "value": sval,
            "node_id": r.get("node_id") or "",
            "path": r.get("path") or "",
        })

    rows.sort(key=lambda x: (x["station"], x["path"]))
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["station", "browse_name", "node_class",
                                          "value_type", "value", "node_id", "path"])
        w.writeheader()
        w.writerows(rows)

    # summary
    from collections import Counter
    per_station = Counter(r["station"] for r in rows)
    variables = sum(1 for r in rows if r["node_class"] == "Variable")
    print(f"wrote {len(rows)} nodes ({variables} variables) -> {OUT}")
    print("per station:")
    for st, n in per_station.most_common():
        print(f"  {st:26} {n}")


main()
