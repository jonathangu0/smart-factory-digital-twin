"""Diagnose VGR horizontal axis: side view (+X looking -X, so Y=left/right,
Z=up), force horizontal-only pose to see current behavior."""
import omni.usd
import builtins
from pxr import UsdGeom, Gf


def main():
    builtins._vgr_test_pose = (0, 0, 3377)  # full horizontal only
    stage = omni.usd.get_context().get_stage()
    C = Gf.Vec3d(0.05, -0.18, 0.19)
    cam = UsdGeom.Camera.Define(stage, "/World/VGRCam")
    eye = C + Gf.Vec3d(0.48, 0.02, 0.14)   # from +X, looking -X
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 0, 1))
    cx = UsdGeom.Xformable(cam); cx.ClearXformOpOrder()
    cx.AddTransformOp().Set(view.GetInverse())
    cam.GetFocalLengthAttr().Set(26.0)
    cam.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 100.0))
    from omni.kit.viewport.utility import get_active_viewport
    get_active_viewport().set_active_camera("/World/VGRCam")
    print("horizontal-only pose set; side cam active")


main()
