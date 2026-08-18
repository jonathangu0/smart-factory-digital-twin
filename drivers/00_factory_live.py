"""Live digital twin of the Training Factory, driven by OPC-UA tags.

Polls the PLC ~10x/s and mirrors factory state: a beacon marks the active
station (State_*.x_active) and a HUD shows order state, VGR/HBW axis positions,
and SLD color counters. STATIONS scene positions are best-guess on the
baseplate and easy to tune.
"""
import asyncio
import threading
import logging
import builtins

import omni.usd
import omni.kit.app
import omni.ui as ui
from pxr import UsdGeom, UsdLux, Gf, Vt

logging.getLogger("asyncua").setLevel(logging.CRITICAL)

URL = "opc.tcp://192.168.0.1:4840"
DB = 'ns=3;s="gtyp_Interface_Dashboard"."Subscribe".'   # dashboard prefix

ACTIVE = {
    "HBW": DB + '"State_HBW"."x_active"',
    "VGR": DB + '"State_VGR"."x_active"',
    "MPO": DB + '"State_MPO"."x_active"',
    "SLD": DB + '"State_SLD"."x_active"',
    "DSI": DB + '"State_DSI"."x_active"',
    "DSO": DB + '"State_DSO"."x_active"',
}
TARGET = {k: v.replace('"x_active"', '"s_target"') for k, v in ACTIVE.items()}
MISC = {
    "order": DB + '"State_Order"."s_state"',
    "vgr_rot": 'ns=3;s="gtyp_VGR"."rotate_Axis"."di_Actual_Position"',
    "vgr_ver": 'ns=3;s="gtyp_VGR"."vertical_Axis"."di_Actual_Position"',
    "vgr_hor": 'ns=3;s="gtyp_VGR"."horizontal_Axis"."di_Actual_Position"',
    "hbw_hor": 'ns=3;s="gtyp_HBW"."Horizontal_Axis"."di_Actual_Position"',
    "hbw_ver": 'ns=3;s="gtyp_HBW"."Vertical_Axis"."di_Actual_Position"',
    "sld_blue": 'ns=3;s="gtyp_SLD"."i_CounterValue_Blue"',
    "sld_white": 'ns=3;s="gtyp_SLD"."i_CounterValue_White"',
    "sld_red": 'ns=3;s="gtyp_SLD"."i_CounterValue_Red"',
}

# scene positions of each station on the baseplate (X[-0.47,0.47] Y[-0.38,0.38])
STATIONS = {
    "HBW": (-0.34, 0.20),
    "VGR": (0.00, 0.06),
    "MPO": (0.28, 0.18),
    "SLD": (0.26, -0.22),
    "DSI": (-0.30, -0.15),
    "DSO": (0.00, -0.30),
}
Z_BEACON = 0.20

STATE = {"connected": False, "error": "connecting", "active": None}
builtins._factory_state = STATE
ORDER = ["HBW", "VGR", "MPO", "SLD", "DSI", "DSO"]


async def _loop():
    from asyncua import Client
    allnodes = {**{f"act_{k}": v for k, v in ACTIVE.items()}, **MISC}
    while getattr(builtins, "_factory_run", True):
        client = Client(url=URL)
        client.session_timeout = 30000
        try:
            await client.connect()
            nodes = {k: client.get_node(v) for k, v in allnodes.items()}
            STATE["connected"] = True
            STATE["error"] = ""
            while getattr(builtins, "_factory_run", True):
                try:
                    for k, node in nodes.items():
                        STATE[k] = await asyncio.wait_for(node.read_value(), timeout=2.0)
                except Exception as e:
                    STATE["connected"] = False
                    STATE["error"] = f"read drop: {str(e)[:30]}"
                    break  # drop to the reconnect below instead of hanging
                act = next((s for s in ORDER if STATE.get(f"act_{s}")), None)
                STATE["active"] = act
                await asyncio.sleep(0.1)
        except Exception as e:
            STATE["connected"] = False
            STATE["error"] = str(e)[:50]
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        await asyncio.sleep(3)


def _build_scene():
    stage = omni.usd.get_context().get_stage()
    stage.SetEditTarget(stage.GetSessionLayer())  # runtime edits only; never bakes into the scene file
    # hide the old scripted cycle so only the live mirror shows
    for p in ("/World/Twin",):
        pr = stage.GetPrimAtPath(p)
        if pr and pr.IsValid():
            pr.SetActive(False)
    live = UsdGeom.Xform.Define(stage, "/World/Live")
    marker = UsdGeom.Sphere.Define(stage, "/World/Live/Beacon")
    marker.GetRadiusAttr().Set(0.03)
    marker.GetDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(0.2, 1.0, 0.3)]))
    mt = UsdGeom.Xformable(marker); mt.ClearXformOpOrder()
    beacon_t = mt.AddTranslateOp()
    light = UsdLux.SphereLight.Define(stage, "/World/Live/BeaconLight")
    light.GetRadiusAttr().Set(0.025)
    light.GetIntensityAttr().Set(40000)
    light.GetColorAttr().Set(Gf.Vec3f(0.4, 1.0, 0.5))
    lt = UsdGeom.Xformable(light); lt.ClearXformOpOrder()
    light_t = lt.AddTranslateOp()
    return marker, beacon_t, light, light_t


def main():
    builtins._factory_run = True
    threading.Thread(target=lambda: asyncio.run(_loop()), daemon=True).start()

    marker, beacon_t, light, light_t = _build_scene()
    marker_img = UsdGeom.Imageable(marker)
    light_img = UsdGeom.Imageable(light)

    if getattr(builtins, "_factory_hud", None):
        try:
            builtins._factory_hud.destroy()
        except Exception:
            pass
    win = ui.Window("Training Factory — LIVE twin", width=340, height=250)
    L = {}
    with win.frame:
        with ui.VStack(spacing=3, height=0):
            L["status"] = ui.Label("connecting...")
            L["order"] = ui.Label("order: -")
            L["active"] = ui.Label("ACTIVE station: -")
            ui.Separator(height=3)
            L["vgr"] = ui.Label("VGR  r/v/h: -")
            L["hbw"] = ui.Label("HBW  h/v: -")
            L["sld"] = ui.Label("SLD  B/W/R: -")
            ui.Separator(height=3)
            L["src"] = ui.Label(URL, height=14)
    builtins._factory_hud = win

    def g(k):
        v = STATE.get(k)
        return "-" if v is None else v

    def _update(_e):
        s = STATE
        if s.get("connected"):
            L["status"].text = "● LIVE — connected to PLC"
        else:
            L["status"].text = f"○ offline — {s.get('error','')}"
        L["order"].text = f"order: {g('order')}"
        act = s.get("active")
        L["active"].text = f"ACTIVE station: {act or 'idle'}"
        deg = (s.get('vgr_rot') or 0) / 5331 * 270
        L["vgr"].text = f"VGR  r/v/h: {g('vgr_rot')} ({deg:.0f}°) / {g('vgr_ver')} / {g('vgr_hor')}"
        L["hbw"].text = f"HBW  h/v: {g('hbw_hor')} / {g('hbw_ver')}"
        L["sld"].text = f"SLD  B/W/R: {g('sld_blue')} / {g('sld_white')} / {g('sld_red')}"

        if act and act in STATIONS:
            x, y = STATIONS[act]
            beacon_t.Set(Gf.Vec3d(x, y, Z_BEACON))
            light_t.Set(Gf.Vec3d(x, y, Z_BEACON))
            marker_img.MakeVisible()
            light_img.MakeVisible()
        else:
            marker_img.MakeInvisible()
            light_img.MakeInvisible()

    sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
        _update, name="factory_live")
    builtins._factory_sub = sub
    print("LIVE factory twin running. Run a cycle on the real factory to see it mirror.")


main()
