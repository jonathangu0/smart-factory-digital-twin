"""Debug the camera transform + active camera position."""
import omni.usd
from pxr import Gf, UsdGeom


def main():
    C = Gf.Vec3d(0.05, -0.16, 0.14)
    eye = C + Gf.Vec3d(0.4, -0.52, 0.5)
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 0, 1))
    inv = view.GetInverse()
    print("intended eye  :", [round(v, 3) for v in eye])
    print("inv translation:", [round(v, 3) for v in inv.ExtractTranslation()])

    stage = omni.usd.get_context().get_stage()
    from omni.kit.viewport.utility import get_active_viewport
    vp = get_active_viewport()
    ac = str(vp.get_active_camera())
    cam = stage.GetPrimAtPath(ac)
    if cam and cam.IsValid():
        t = UsdGeom.XformCache().GetLocalToWorldTransform(cam).ExtractTranslation()
        fl = UsdGeom.Camera(cam).GetFocalLengthAttr().Get()
        ap = UsdGeom.Camera(cam).GetHorizontalApertureAttr().Get()
        print("active cam    :", ac)
        print("  world pos   :", [round(v, 3) for v in t])
        print("  focalLength :", fl, "horizAperture:", ap)


main()
