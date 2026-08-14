"""3/4 view of the VGR alone (documentation-like angle). Camera only."""
import omni.usd
from pxr import UsdGeom, Gf


def main():
    stage = omni.usd.get_context().get_stage()
    C = Gf.Vec3d(0.086, -0.150, 0.17)
    cam = UsdGeom.Camera.Define(stage, "/World/VGR3QCam")
    eye = C + Gf.Vec3d(0.46, -0.52, 0.30)
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 0, 1))
    cx = UsdGeom.Xformable(cam); cx.ClearXformOpOrder()
    cx.AddTransformOp().Set(view.GetInverse())
    cam.GetFocalLengthAttr().Set(22.0)
    cam.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 100.0))
    from omni.kit.viewport.utility import get_active_viewport
    get_active_viewport().set_active_camera("/World/VGR3QCam")
    print("VGR 3/4 cam active")


main()
