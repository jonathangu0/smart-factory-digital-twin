"""Top-down camera over the VGR to see arm-vs-tower alignment. Pauses demo."""
import builtins
import omni.usd
from pxr import UsdGeom, Gf


def main():
    builtins._demo_mode = False
    builtins._vgr_test_pose = (0, 0, 0)   # home
    stage = omni.usd.get_context().get_stage()
    C = Gf.Vec3d(0.086, -0.155, 0.20)
    cam = UsdGeom.Camera.Define(stage, "/World/VGRTopCam")
    eye = C + Gf.Vec3d(0.0, 0.0, 0.55)
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 1, 0))  # up = +Y
    cx = UsdGeom.Xformable(cam); cx.ClearXformOpOrder()
    cx.AddTransformOp().Set(view.GetInverse())
    cam.GetFocalLengthAttr().Set(30.0)
    cam.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 100.0))
    from omni.kit.viewport.utility import get_active_viewport
    get_active_viewport().set_active_camera("/World/VGRTopCam")
    print("VGR top-down cam active; home pose")


main()
