"""Deactivate the two glTF camera groups (works through references, unlike delete)."""
import os
import omni.usd
from pxr import Sdf

SAVE = r"C:/Users/icets/Downloads/digitaltwinsf/TrainingFactory_Industry40.usd"
SHOT = r"C:/Users/icets/Downloads/digitaltwinsf/twin/shots/factory_06.png"

TO_KILL = [
    "/World/TrainingFactory/World/Camera",
    "/World/TrainingFactory/World/Factory/OverviewCamera",
]


def main():
    ctx = omni.usd.get_context()
    stage = ctx.get_stage()
    # edit on the root layer so the deactivation is saved
    stage.SetEditTarget(stage.GetRootLayer())

    for path in TO_KILL:
        p = stage.GetPrimAtPath(path)
        if p and p.IsValid():
            p.SetActive(False)
            print("deactivated:", path, "-> active now:", stage.GetPrimAtPath(path).IsActive())
        else:
            print("not found:", path)

    stage.GetRootLayer().Export(SAVE)
    print("saved ->", SAVE)

    from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
    vp = get_active_viewport()
    vp.set_active_camera("/World/OverviewCam")
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    capture_viewport_to_file(vp, SHOT)
    print("shot ->", SHOT)


main()
