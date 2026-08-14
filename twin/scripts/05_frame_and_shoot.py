"""Select the CAD model, frame the viewport on it properly, and screenshot."""
import os
import omni.usd


def main():
    ctx = omni.usd.get_context()
    ctx.get_selection().set_selected_prim_paths(["/vgr"], True)

    from omni.kit.viewport.utility import get_active_viewport
    vp = get_active_viewport()

    framed = False
    try:
        from omni.kit.viewport.utility import frame_viewport_selection
        frame_viewport_selection(vp)
        framed = True
        print("frame_viewport_selection ok")
    except Exception as e:
        print("frame_viewport_selection failed:", repr(e))
    if not framed:
        try:
            from omni.kit.viewport.utility import frame_viewport_prims
            frame_viewport_prims(vp, prims=["/vgr"])
            framed = True
            print("frame_viewport_prims ok")
        except Exception as e:
            print("frame_viewport_prims failed:", repr(e))

    path = r"C:/Users/icets/Downloads/digitaltwinsf/twin/shots/vgr_cad_02.png"
    os.makedirs(os.path.dirname(path), exist_ok=True)
    from omni.kit.viewport.utility import capture_viewport_to_file
    capture_viewport_to_file(vp, path)
    print("capture ->", path)


main()
