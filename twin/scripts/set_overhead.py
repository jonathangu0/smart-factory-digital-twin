"""Overhead camera over the whole factory to read station labels + map layout."""
import omni.usd
from pxr import UsdGeom, Gf


def main():
    stage = omni.usd.get_context().get_stage()
    C = Gf.Vec3d(0.0, 0.0, 0.1)
    eye = Gf.Vec3d(0.0, -0.06, 1.15)
    cam = UsdGeom.Camera.Define(stage, "/World/VGRCam")
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 1, 0))
    cx = UsdGeom.Xformable(cam); cx.ClearXformOpOrder()
    cx.AddTransformOp().Set(view.GetInverse())
    cam.GetFocalLengthAttr().Set(24.0)
    cam.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 100.0))
    from omni.kit.viewport.utility import get_active_viewport
    vp = get_active_viewport()
    vp.set_active_camera("/World/VGRCam")
    print("overhead active:", vp.get_active_camera())


main()
