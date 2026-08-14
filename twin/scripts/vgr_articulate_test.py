"""Test VGR articulation: rotate all parts above the turntable about the vertical
column axis by a test angle; static base stays. Screenshot to check it swings right."""
import os
import omni.usd
from pxr import Usd, UsdGeom, Gf

VGR = "/World/TrainingFactory/World/Factory/Assembly/Part_5/NAUO2"
PIVOT = Gf.Vec3d(0.05, -0.17, 0.0)   # column vertical axis (world XY)
Z_ROTATE = 0.055                     # parts with center Z above this rotate
ANGLE = 90.0
SHOT = r"C:/Users/icets/Downloads/digitaltwinsf/twin/shots/vgr_artic.png"


def main():
    stage = omni.usd.get_context().get_stage()
    stage.SetEditTarget(stage.GetRootLayer())
    vgr = stage.GetPrimAtPath(VGR)
    xc = UsdGeom.XformCache()
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)

    Pp = xc.GetLocalToWorldTransform(vgr)   # all sub-parts share this parent
    Rz = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), ANGLE))
    Tin = Gf.Matrix4d().SetTranslate(-PIVOT)
    Tout = Gf.Matrix4d().SetTranslate(PIVOT)
    delta_world = Tin * Rz * Tout
    inner = Pp * delta_world * Pp.GetInverse()

    n_rot, n_base = 0, 0
    for c in vgr.GetChildren():
        r = bc.ComputeWorldBound(c).ComputeAlignedRange()
        if r.IsEmpty():
            continue
        zc = (r.GetMin()[2] + r.GetMax()[2]) / 2
        if zc >= Z_ROTATE:
            xf = UsdGeom.Xformable(c)
            L = xf.GetLocalTransformation()
            xf.ClearXformOpOrder()
            xf.AddTransformOp().Set(L * inner)
            n_rot += 1
        else:
            n_base += 1
    print(f"rotated {n_rot} parts, base kept {n_base}")

    from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
    vp = get_active_viewport()
    vp.set_active_camera("/World/OverviewCam")
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    capture_viewport_to_file(vp, SHOT)
    print("shot ->", SHOT)


main()
