"""Pure capture from the already-active camera (no camera change) to avoid the
set-active-camera / capture timing race."""
import os
from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file


def main():
    vp = get_active_viewport()
    path = r"C:/Users/icets/Downloads/digitaltwinsf/twin/shots/vgr_pure.png"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    capture_viewport_to_file(vp, path)
    print("captured from", vp.get_active_camera(), "->", path)


main()
