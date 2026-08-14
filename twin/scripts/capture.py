"""Capture the active viewport to a PNG using the viewport utility API."""
import os


def main():
    from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
    path = r"C:/Users/icets/Downloads/digitaltwinsf/twin/shots/vgr_cad_01.png"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    vp = get_active_viewport()
    cap = capture_viewport_to_file(vp, path)
    print("capture scheduled ->", path)
    print("viewport:", vp, "cap:", cap)


main()
