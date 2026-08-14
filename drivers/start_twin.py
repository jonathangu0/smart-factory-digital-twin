"""One-click startup, run by START_LIVE_TWIN.bat via Isaac Sim's --exec flag.

It: opens the twin scene, waits for the geometry to finish loading, then runs all
station drivers so the LIVE twin is ready. The MCP server is enabled by the .bat.

Paths come from the TWIN_REPO env var (set by the .bat); falls back to the default
install path if run by hand.
"""
import os
import omni.usd
import omni.kit.app
import builtins

REPO = os.environ.get("TWIN_REPO", r"C:/Users/icets/Downloads/digitaltwinsf")
REPO = REPO.replace("\\", "/").rstrip("/")
SCENE = REPO + "/scene/TrainingFactoryDigitalTwin.usd"
DRIVERS = REPO + "/drivers"

# station drivers (run in this order), then frame the whole factory
STARTUP = ["00_factory_live", "01_vgr", "02_hbw", "03_mpo", "04_sld",
           "05_vgr_workpiece", "camera_overview"]

# a deep geometry prim -> proof the scene has actually loaded
READY_PRIM = "/World/TrainingFactory/World/Factory/Assembly/Part_5/NAUO2/NAUO2856"

ctx = omni.usd.get_context()
ctx.open_stage(SCENE)
print("[start_twin] opening", SCENE)

_state = {"ran": False, "settle": 0}


def _boot(_e):
    if _state["ran"]:
        return
    stage = ctx.get_stage()
    if not stage or not stage.GetPrimAtPath(READY_PRIM).IsValid():
        _state["settle"] = 0          # geometry not loaded yet
        return
    _state["settle"] += 1
    if _state["settle"] < 60:         # let meshes settle for ~1s after they appear
        return
    _state["ran"] = True
    for name in STARTUP:
        try:
            exec(open(DRIVERS + "/" + name + ".py").read(), {})
            print("[start_twin] started", name)
        except Exception as ex:
            print("[start_twin] ERROR in", name, "->", ex)
    print("[start_twin] ===================================================")
    print("[start_twin] LIVE TWIN READY.")
    print("[start_twin]   * On the factory network? Run a cycle -> it mirrors.")
    print("[start_twin]   * Offline preview: run drivers/demo_cycle.py or full_cycle.py")
    print("[start_twin] ===================================================")


builtins._start_twin_boot = omni.kit.app.get_app().get_update_event_stream(
).create_subscription_to_pop(_boot, name="start_twin_boot")
