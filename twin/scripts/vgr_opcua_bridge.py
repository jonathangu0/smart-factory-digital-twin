"""
vgr_opcua_bridge.py — drive the VGR twin from the real PLC (OPC UA), live.

Architecture (mirrors the smart-factory repo's threading model):
  * A background thread reads the 3 VGR axis counts from the PLC via asyncua
    and writes them into STATE (or, in sim mode, a synthetic sweep does).
  * A Kit update callback (main thread) reads STATE every frame and poses the
    twin via the three driven xformOps built by vgr_twin_build.py.

MODE = "sim"  -> animate a synthetic sweep now, off the factory network.
MODE = "live" -> connect to opc.tcp://192.168.0.1:4840 (needs WiFi TP-Link_8911).

Run:  (Isaac Sim MCP)  execute_python_file  this file.
Stop: execute_python_file twin/scripts/vgr_stop.py
"""
import math
import time
import asyncio
import threading
import builtins

import omni.usd
import omni.kit.app
from pxr import UsdGeom, Gf

MODE = "sim"   # <-- change to "live" on the factory WiFi

# --- OPC UA (from smart-factory-digital-twin/opcua/vgr_twin.py) ---
OPCUA_URL = "opc.tcp://192.168.0.1:4840"
NODES = {
    "rotate":     'ns=3;s="gtyp_VGR"."rotate_Axis"."di_Actual_Position"',
    "vertical":   'ns=3;s="gtyp_VGR"."vertical_Axis"."di_Actual_Position"',
    "horizontal": 'ns=3;s="gtyp_VGR"."horizontal_Axis"."di_Actual_Position"',
}
# --- calibration + scene travel (must match vgr_twin_build.py) ---
ROT_270, VERT_MAX, HORIZ_MAX = 5331, 2993, 3377
COLUMN_H, VERT_TRAVEL, HORIZ_TRAVEL = 0.50, 0.34, 0.26
ROT_SIGN, ROT_OFFSET_DEG = 1.0, 0.0

STATE = {"rotate": 0, "vertical": 0, "horizontal": 0, "connected": False, "mode": MODE}
builtins._vgr_state = STATE


# ---- pose application (main thread, from the Kit update callback) ----
def _ops():
    stage = omni.usd.get_context().get_stage()
    rot = UsdGeom.Xformable(stage.GetPrimAtPath("/World/VGR/Rotate")).GetOrderedXformOps()[0]
    vert = UsdGeom.Xformable(stage.GetPrimAtPath("/World/VGR/Rotate/Vertical")).GetOrderedXformOps()[0]
    hor = UsdGeom.Xformable(stage.GetPrimAtPath("/World/VGR/Rotate/Vertical/Horizontal")).GetOrderedXformOps()[0]
    return rot, vert, hor


def _apply(_dt):
    rot, vert, hor = _ops()
    deg = ROT_SIGN * (float(STATE["rotate"]) / ROT_270) * 270.0 + ROT_OFFSET_DEG
    drop = (float(STATE["vertical"]) / VERT_MAX) * VERT_TRAVEL
    ext = (float(STATE["horizontal"]) / HORIZ_MAX) * HORIZ_TRAVEL
    rot.Set(deg)
    vert.Set(Gf.Vec3d(0, 0, -drop))
    hor.Set(Gf.Vec3d(ext, 0, 0))


# ---- OPC UA reader thread (live mode) ----
async def _opcua_loop():
    from asyncua import Client
    import logging
    logging.getLogger("asyncua").setLevel(logging.CRITICAL)
    while getattr(builtins, "_vgr_run", True):
        client = Client(url=OPCUA_URL)
        try:
            await client.connect()
            nodes = {k: client.get_node(v) for k, v in NODES.items()}
            STATE["connected"] = True
            while getattr(builtins, "_vgr_run", True):
                for k, node in nodes.items():
                    STATE[k] = await node.read_value()
                await asyncio.sleep(0.1)
        except Exception as e:
            STATE["connected"] = False
            STATE["error"] = str(e)
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        time.sleep(3)


# ---- synthetic sweep thread (sim mode) ----
def _sim_loop():
    t0 = time.time()
    while getattr(builtins, "_vgr_run", True):
        t = time.time() - t0
        STATE["rotate"] = int((0.5 + 0.5 * math.sin(t * 0.5)) * ROT_270)
        STATE["vertical"] = int((0.5 + 0.5 * math.sin(t * 0.8 + 1.0)) * VERT_MAX)
        STATE["horizontal"] = int((0.5 + 0.5 * math.sin(t * 0.7 + 2.0)) * HORIZ_MAX)
        STATE["connected"] = True
        time.sleep(0.05)


def start():
    builtins._vgr_run = True
    if MODE == "live":
        threading.Thread(target=lambda: asyncio.run(_opcua_loop()), daemon=True).start()
        src = f"OPC UA {OPCUA_URL}"
    else:
        threading.Thread(target=_sim_loop, daemon=True).start()
        src = "SIMULATED sweep (offline)"
    sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
        _apply, name="vgr_twin_apply")
    builtins._vgr_sub = sub  # keep alive
    print(f"VGR bridge running in {MODE!r} mode -> {src}")
    print("Watch the twin move. Stop with vgr_stop.py")


start()
