"""Position VGRCam as a steep top-down over the VGR and make it active.
Capture separately (pure_capture.py) to avoid the set/capture timing race."""
import omni.usd
from pxr import UsdGeom, Gf


def main():
    stage = omni.usd.get_context().get_stage()
    C = Gf.Vec3d(0.05, -0.16, 0.17)          # VGR center
    eye = C + Gf.Vec3d(0.10, -0.10, 0.55)     # nearly above, slight offset
    cam = UsdGeom.Camera.Define(stage, "/World/VGRCam")
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 1, 0))  # up = +Y (top-down)
    cx = UsdGeom.Xformable(cam); cx.ClearXformOpOrder()
    cx.AddTransformOp().Set(view.GetInverse())
    cam.GetFocalLengthAttr().Set(22.0)
    cam.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 100.0))  # avoid near-plane clipping

    from omni.kit.viewport.utility import get_active_viewport
    vp = get_active_viewport()
    vp.set_active_camera("/World/VGRCam")
    print("VGRCam set top-down, active:", vp.get_active_camera())


main()
