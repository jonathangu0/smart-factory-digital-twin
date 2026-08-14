"""Delete the two glTF cameras whose gizmo meshes show as giant grey props."""
import os
import omni.usd
import omni.kit.commands

SAVE = r"C:/Users/icets/Downloads/digitaltwinsf/TrainingFactory_Industry40.usd"
SHOT = r"C:/Users/icets/Downloads/digitaltwinsf/twin/shots/factory_05.png"

TO_DELETE = [
    "/World/TrainingFactory/World/Camera",
    "/World/TrainingFactory/World/Factory/OverviewCamera",
]


def main():
    ctx = omni.usd.get_context()
    stage = ctx.get_stage()

    for path in TO_DELETE:
        p = stage.GetPrimAtPath(path)
        print(path, "exists:", bool(p and p.IsValid()))
    omni.kit.commands.execute("DeletePrims", paths=TO_DELETE)

    # verify gone
    for path in TO_DELETE:
        p = stage.GetPrimAtPath(path)
        print("after delete", path, "valid:", bool(p and p.IsValid()))

    stage.GetRootLayer().Export(SAVE)
    print("saved ->", SAVE)

    from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
    vp = get_active_viewport()
    vp.set_active_camera("/World/OverviewCam")
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    capture_viewport_to_file(vp, SHOT)
    print("shot ->", SHOT)


main()
