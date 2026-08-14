"""MPO view camera + force a turntable index angle to show it rotating."""
import builtins
import omni.usd
from pxr import UsdGeom, Gf


def main():
    builtins._mpo_test_angle = 70.0
    stage = omni.usd.get_context().get_stage()
    C = Gf.Vec3d(0.24, 0.17, 0.085)
    cam = UsdGeom.Camera.Define(stage, "/World/MPOCam")
    eye = C + Gf.Vec3d(0.10, -0.34, 0.24)
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 0, 1))
    cx = UsdGeom.Xformable(cam); cx.ClearXformOpOrder()
    cx.AddTransformOp().Set(view.GetInverse())
    cam.GetFocalLengthAttr().Set(28.0)
    cam.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 100.0))
    from omni.kit.viewport.utility import get_active_viewport
    get_active_viewport().set_active_camera("/World/MPOCam")
    print("MPO cam active; turntable forced to 70 deg")


main()
