"""Live OPC-UA connection to the real VGR, shown in a HUD inside Isaac Sim.

Runs a background asyncua client that connects to the PLC and streams the VGR's
3 axis positions (+ targets + reached flags) into a shared STATE, and a HUD
panel that displays them. Sits in 'offline/retrying' until you join the factory
WiFi (TP-Link_8911), then flips to live automatically.

Connection + node IDs + calibration come from smart-factory-digital-twin/opcua.
"""
import asyncio
import threading
import logging
import builtins

import omni.ui as ui
import omni.kit.app

logging.getLogger("asyncua").setLevel(logging.CRITICAL)

URL = "opc.tcp://192.168.0.1:4840"
NODES = {
    "rotate":             'ns=3;s="gtyp_VGR"."rotate_Axis"."di_Actual_Position"',
    "vertical":           'ns=3;s="gtyp_VGR"."vertical_Axis"."di_Actual_Position"',
    "horizontal":         'ns=3;s="gtyp_VGR"."horizontal_Axis"."di_Actual_Position"',
    "rotate_target":      'ns=3;s="gtyp_VGR"."rotate_Axis"."di_Target_Position"',
    "vertical_target":    'ns=3;s="gtyp_VGR"."vertical_Axis"."di_Target_Position"',
    "horizontal_target":  'ns=3;s="gtyp_VGR"."horizontal_Axis"."di_Target_Position"',
    "rotate_reached":     'ns=3;s="gtyp_VGR"."rotate_Axis"."x_Position_Reached"',
    "vertical_reached":   'ns=3;s="gtyp_VGR"."vertical_Axis"."x_Position_Reached"',
    "horizontal_reached": 'ns=3;s="gtyp_VGR"."horizontal_Axis"."x_Position_Reached"',
}
ROT_270 = 5331

STATE = {"connected": False, "error": "waiting for factory WiFi (TP-Link_8911)"}
builtins._vgr_opcua = STATE


async def _loop():
    from asyncua import Client
    while getattr(builtins, "_vgr_opcua_run", True):
        client = Client(url=URL)
        client.session_timeout = 30000
        try:
            await client.connect()
            nodes = {k: client.get_node(v) for k, v in NODES.items()}
            STATE["connected"] = True
            STATE["error"] = ""
            while getattr(builtins, "_vgr_opcua_run", True):
                for k, node in nodes.items():
                    STATE[k] = await node.read_value()
                await asyncio.sleep(0.1)
        except Exception as e:
            STATE["connected"] = False
            STATE["error"] = str(e)[:60]
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        await asyncio.sleep(3)


def _fmt(v):
    return "-" if v is None else str(v)


def main():
    builtins._vgr_opcua_run = True
    threading.Thread(target=lambda: asyncio.run(_loop()), daemon=True).start()

    if getattr(builtins, "_vgr_hud", None):
        try:
            builtins._vgr_hud.destroy()
        except Exception:
            pass
    win = ui.Window("VGR — Live (OPC UA)", width=320, height=210)
    labels = {}
    with win.frame:
        with ui.VStack(spacing=4, height=0):
            labels["status"] = ui.Label("connecting...", height=20)
            ui.Separator(height=4)
            for key in ("rotate", "vertical", "horizontal"):
                labels[key] = ui.Label(f"{key}: -", height=18)
            ui.Separator(height=4)
            labels["target"] = ui.Label("target r/v/h: -", height=18)
            labels["reached"] = ui.Label("reached r/v/h: -", height=18)
            labels["src"] = ui.Label(URL, height=16)
    builtins._vgr_hud = win

    def _update(_e):
        s = STATE
        if s.get("connected"):
            deg = (s.get("rotate") or 0) / ROT_270 * 270.0
            labels["status"].text = "● LIVE — connected to PLC"
            labels["rotate"].text = f"rotate:     {_fmt(s.get('rotate'))}  ({deg:.0f}°)"
            labels["vertical"].text = f"vertical:   {_fmt(s.get('vertical'))}"
            labels["horizontal"].text = f"horizontal: {_fmt(s.get('horizontal'))}"
            labels["target"].text = (f"target r/v/h: {_fmt(s.get('rotate_target'))} / "
                                     f"{_fmt(s.get('vertical_target'))} / {_fmt(s.get('horizontal_target'))}")
            labels["reached"].text = (f"reached r/v/h: {_fmt(s.get('rotate_reached'))} / "
                                      f"{_fmt(s.get('vertical_reached'))} / {_fmt(s.get('horizontal_reached'))}")
        else:
            labels["status"].text = f"○ offline — {s.get('error','')}"

    sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
        _update, name="vgr_opcua_hud")
    builtins._vgr_opcua_sub = sub
    print("OPC-UA live client + HUD started. Will connect once on factory WiFi.")


main()
