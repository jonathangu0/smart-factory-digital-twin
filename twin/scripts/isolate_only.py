"""Hide all factory clusters except the target, frame + shot it, to ID it.
(Non-restoring; run restore_all.py afterward to bring the rest back.)"""
import os
import omni.usd

ROOT = "/World/TrainingFactory/World/Factory/Assembly/Part_5"
TARGET = "NAUO2"
SHOT = r"C:/Users/icets/Downloads/digitaltwinsf/twin/shots/isolate_NAUO2.png"


def main():
    stage = omni.usd.get_context().get_stage()
    stage.SetEditTarget(stage.GetRootLayer())
    root = stage.GetPrimAtPath(ROOT)
    tgt_path = f"{ROOT}/{TARGET}"
    hidden = 0
    for child in root.GetChildren():
        if child.GetPath().pathString != tgt_path:
            child.SetActive(False)
            hidden += 1
    print("hid", hidden, "clusters, kept", TARGET)

    ctx = omni.usd.get_context()
    ctx.get_selection().set_selected_prim_paths([tgt_path], True)
    from omni.kit.viewport.utility import get_active_viewport, frame_viewport_selection, capture_viewport_to_file
    vp = get_active_viewport()
    frame_viewport_selection(vp)
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    capture_viewport_to_file(vp, SHOT)
    print("shot ->", SHOT)


main()
