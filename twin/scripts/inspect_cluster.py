"""Frame tightly on one cluster (non-destructive) to identify what station it is."""
import os
import omni.usd

TARGET = "/World/TrainingFactory/World/Factory/Assembly/Part_5/NAUO2"
SHOT = r"C:/Users/icets/Downloads/digitaltwinsf/twin/shots/cluster_NAUO2.png"


def main():
    ctx = omni.usd.get_context()
    ctx.get_selection().set_selected_prim_paths([TARGET], True)
    from omni.kit.viewport.utility import get_active_viewport, frame_viewport_selection, capture_viewport_to_file
    vp = get_active_viewport()
    frame_viewport_selection(vp)
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    capture_viewport_to_file(vp, SHOT)
    print("framed + shot", TARGET, "->", SHOT)


main()
