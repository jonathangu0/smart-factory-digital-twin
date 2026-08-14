"""Clear all test poses (go fully live), frame the whole factory, capture."""
import os
import omni.usd
import builtins
from pxr import Usd, UsdGeom, Gf

SHOT = r"C:/Users/icets/Downloads/digitaltwinsf/twin/shots/twin_final.png"


def main():
    builtins._vgr_test_pose = None
    builtins._mpo_test_angle = None

    stage = omni.usd.get_context().get_stage()
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)
    rng = Gf.Range3d()
    for p in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()):
        if p.GetTypeName() != "Mesh":
            continue
        ps = p.GetPath().pathString
        if "CameraModel" in ps or "ViewportCameraMesh" in ps:
            continue
        rng.UnionWith(bc.ComputeWorldBound(p).ComputeAlignedRange())
    mn, mx = rng.GetMin(), rng.GetMax()
    C = Gf.Vec3d((mn[0]+mx[0])/2, (mn[1]+mx[1])/2, (mn[2]+mx[2])/2)
    d = max(mx[i]-mn[i] for i in range(3))
    cam = UsdGeom.Camera.Define(stage, "/World/OverviewCam")
    eye = C + Gf.Vec3d(d*1.6, -d*1.9, d*1.15)
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 0, 1))
    cx = UsdGeom.Xformable(cam); cx.ClearXformOpOrder()
    cx.AddTransformOp().Set(view.GetInverse())
    cam.GetFocalLengthAttr().Set(27.0)
    from omni.kit.viewport.utility import get_active_viewport
    get_active_viewport().set_active_camera("/World/OverviewCam")
    print("all live; overview set. VGR/HBW/MPO articulation active.")


main()
