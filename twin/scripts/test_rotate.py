"""Apply a test 90-degree rotation about world-Z to a candidate VGR cluster and
screenshot, to confirm which NAUO group is the VGR and that it swings sensibly."""
import os
import omni.usd
from pxr import Usd, UsdGeom, Gf

CANDIDATE = "/World/TrainingFactory/World/Factory/Assembly/Part_5/NAUO2"
ANGLE = -90.0
SHOT = r"C:/Users/icets/Downloads/digitaltwinsf/twin/shots/rotate_revert.png"


def main():
    stage = omni.usd.get_context().get_stage()
    stage.SetEditTarget(stage.GetRootLayer())
    prim = stage.GetPrimAtPath(CANDIDATE)
    if not (prim and prim.IsValid()):
        print("candidate not found")
        return

    xc = UsdGeom.XformCache()
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)
    P = bc.ComputeWorldBound(prim).ComputeAlignedRange()
    Pc = (P.GetMin() + P.GetMax()) * 0.5
    pivot = Gf.Vec3d(Pc[0], Pc[1], 0.0)  # rotate about vertical axis through cluster center

    parent = prim.GetParent()
    Pp = xc.GetLocalToWorldTransform(parent)
    xf = UsdGeom.Xformable(prim)
    L = xf.GetLocalTransformation()

    Rz = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), ANGLE))
    Tin = Gf.Matrix4d().SetTranslate(-pivot)
    Tout = Gf.Matrix4d().SetTranslate(pivot)
    delta_world = Tin * Rz * Tout
    inner = Pp * delta_world * Pp.GetInverse()
    new_local = L * inner

    xf.ClearXformOpOrder()
    xf.AddTransformOp().Set(new_local)
    print("applied", ANGLE, "deg about Z at", [round(v, 2) for v in pivot], "to", CANDIDATE)

    from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
    vp = get_active_viewport()
    vp.set_active_camera("/World/OverviewCam")
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    capture_viewport_to_file(vp, SHOT)
    print("shot ->", SHOT)


main()
