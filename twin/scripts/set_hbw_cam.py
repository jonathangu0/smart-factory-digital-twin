"""Set a 3/4 HBW camera active (capture separately)."""
import omni.usd
from pxr import UsdGeom, Gf


def main():
    stage = omni.usd.get_context().get_stage()
    C = Gf.Vec3d(-0.29, 0.01, 0.16)
    cam = UsdGeom.Camera.Define(stage, "/World/HBWCam")
    eye = C + Gf.Vec3d(0.34, -0.30, 0.26)
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 0, 1))
    cx = UsdGeom.Xformable(cam); cx.ClearXformOpOrder()
    cx.AddTransformOp().Set(view.GetInverse())
    cam.GetFocalLengthAttr().Set(24.0)
    cam.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 100.0))
    from omni.kit.viewport.utility import get_active_viewport
    vp = get_active_viewport()
    vp.set_active_camera("/World/HBWCam")
    print("HBWCam active:", vp.get_active_camera())


main()
