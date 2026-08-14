"""Save a screenshot of the active viewport camera to shots/twin.png.
Run this in a SEPARATE call from any camera change (avoids a timing race)."""
import os
from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file


def main():
    vp = get_active_viewport()
    path = r"C:/Users/icets/Downloads/digitaltwinsf/shots/twin.png"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    capture_viewport_to_file(vp, path)
    print("captured from", vp.get_active_camera(), "->", path)


main()
