"""Side view of the VGR to verify vertical drop + arm extend."""
import omni.usd
from pxr import UsdGeom, Gf


def main():
    stage = omni.usd.get_context().get_stage()
    C = Gf.Vec3d(0.05, -0.16, 0.17)
    eye = C + Gf.Vec3d(0.30, 0.42, 0.10)   # from the +Y/+X side, near VGR height
    cam = UsdGeom.Camera.Define(stage, "/World/VGRCam")
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 0, 1))
    cx = UsdGeom.Xformable(cam); cx.ClearXformOpOrder()
    cx.AddTransformOp().Set(view.GetInverse())
    cam.GetFocalLengthAttr().Set(35.0)
    cam.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 100.0))
    from omni.kit.viewport.utility import get_active_viewport
    vp = get_active_viewport()
    vp.set_active_camera("/World/VGRCam")
    print("side cam active:", vp.get_active_camera())


main()
