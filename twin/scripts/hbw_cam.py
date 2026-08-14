"""HBW view camera + a mid-travel test pose to show crane + flat pucks."""
import builtins
import omni.usd
from pxr import UsdGeom, Gf


def main():
    builtins._hbw_test_pose = (1500, 1200)  # crane partway along Y, fork partway down
    stage = omni.usd.get_context().get_stage()
    C = Gf.Vec3d(-0.27, 0.02, 0.17)
    cam = UsdGeom.Camera.Define(stage, "/World/HBWCam")
    eye = C + Gf.Vec3d(-0.30, -0.52, 0.26)
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 0, 1))
    cx = UsdGeom.Xformable(cam); cx.ClearXformOpOrder()
    cx.AddTransformOp().Set(view.GetInverse())
    cam.GetFocalLengthAttr().Set(24.0)
    cam.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 100.0))
    from omni.kit.viewport.utility import get_active_viewport
    get_active_viewport().set_active_camera("/World/HBWCam")
    print("HBW cam active; test pose (1500,1200)")


main()
