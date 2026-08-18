"""Standalone OPC-UA discovery: recursively browse the PLC address space and dump
every node (NodeId, path, class, datatype, value) to a JSON catalog.

Run on factory WiFi (TP-Link_8911):
    python twin/opcua_discovery/browse_opcua.py

Writes twin/opcua_discovery/opcua_catalog.json plus a printed summary of the
top-level station structures (gtyp_VGR, gtyp_HBW, gtyp_MPO, gtyp_SLD, ...).
"""
import os
import json
import asyncio
import logging
from asyncua import Client, ua

logging.getLogger("asyncua").setLevel(logging.CRITICAL)

URL = "opc.tcp://192.168.0.1:4840"
OUT = os.path.join(os.path.dirname(__file__), "opcua_catalog.json")
MAX_NODES = 8000
MAX_DEPTH = 12


async def walk(node, path, depth, out, seen):
    if len(out) >= MAX_NODES or depth > MAX_DEPTH:
        return
    try:
        nid = node.nodeid.to_string()
    except Exception:
        return
    if nid in seen:
        return
    seen.add(nid)

    rec = {"node_id": nid, "path": path, "browse_name": None,
           "node_class": None, "data_type": None, "value": None}
    try:
        rec["browse_name"] = (await node.read_browse_name()).Name
    except Exception:
        pass
    try:
        nclass = await node.read_node_class()
        rec["node_class"] = nclass.name
        if nclass == ua.NodeClass.Variable:
            try:
                v = await node.read_value()
                rec["value"] = v if isinstance(v, (int, float, bool, str)) else str(v)
            except Exception as e:
                rec["value"] = f"<err {e}>"
    except Exception:
        pass
    out.append(rec)

    try:
        for child in await node.get_children():
            bn = rec["browse_name"] or "?"
            await walk(child, f"{path}/{bn}", depth + 1, out, seen)
    except Exception:
        pass


async def main():
    print(f"connecting to {URL} ...")
    client = Client(url=URL)
    client.session_timeout = 30000
    await client.connect()
    print("connected. browsing address space (this may take a minute)...")
    out, seen = [], set()
    await walk(client.nodes.objects, "Objects", 0, out, seen)
    await client.disconnect()

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    variables = [r for r in out if r["node_class"] == "Variable"]
    print(f"\nDISCOVERED {len(out)} nodes ({len(variables)} variables) -> {OUT}")

    groups = {}
    for r in out:
        bn = r.get("browse_name") or ""
        if bn.startswith("gtyp_") or bn.startswith("gtyp"):
            groups.setdefault(bn, 0)
    print("\nTOP-LEVEL STATION STRUCTURES (gtyp_*):")
    for r in out:
        bn = r.get("browse_name") or ""
        if bn.lower().startswith("gtyp"):
            print(f"  {bn:24} {r['node_id']}")


if __name__ == "__main__":
    asyncio.run(main())
