"""Force a close-up of the VGR and confirm the active camera actually switched."""
import os
import omni.usd
from pxr import UsdGeom, Gf

SHOT = r"C:/Users/icets/Downloads/digitaltwinsf/twin/shots/vgr_closeup.png"


def main():
    stage = omni.usd.get_context().get_stage()
    C = Gf.Vec3d(0.05, -0.16, 0.17)
    cam = UsdGeom.Camera.Define(stage, "/World/VGRCam")
    eye = C + Gf.Vec3d(0.34, -0.34, 0.22)
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 0, 1))
    cx = UsdGeom.Xformable(cam); cx.ClearXformOpOrder()
    cx.AddTransformOp().Set(view.GetInverse())
    cam.GetFocalLengthAttr().Set(20.0)

    from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
    vp = get_active_viewport()
    vp.set_active_camera("/World/VGRCam")
    print("active camera now:", vp.get_active_camera())
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    capture_viewport_to_file(vp, SHOT)
    print("shot ->", SHOT)


main()
