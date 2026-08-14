"""Force a VGR test pose and set a 3/4 close camera. Capture separately."""
import omni.usd
import builtins
from pxr import UsdGeom, Gf


def main():
    builtins._vgr_test_pose = (1736, 1500, 1800)  # rot ~88deg, lift ~half, extend ~half

    stage = omni.usd.get_context().get_stage()
    C = Gf.Vec3d(0.05, -0.16, 0.18)
    cam = UsdGeom.Camera.Define(stage, "/World/VGRCam")
    eye = C + Gf.Vec3d(0.36, -0.36, 0.20)
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 0, 1))
    cx = UsdGeom.Xformable(cam); cx.ClearXformOpOrder()
    cx.AddTransformOp().Set(view.GetInverse())
    cam.GetFocalLengthAttr().Set(24.0)
    cam.GetClippingRangeAttr().Set(Gf.Vec2f(0.01, 100.0))

    from omni.kit.viewport.utility import get_active_viewport
    vp = get_active_viewport()
    vp.set_active_camera("/World/VGRCam")
    print("test pose set (1736,1500,1800); cam active:", vp.get_active_camera())


main()
