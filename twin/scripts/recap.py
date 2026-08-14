"""Fresh capture after gizmo removal, from a clean overview camera."""
import os
import omni.usd
from pxr import Usd, UsdGeom, Gf

SHOT = r"C:/Users/icets/Downloads/digitaltwinsf/twin/shots/factory_07.png"


def main():
    ctx = omni.usd.get_context()
    stage = ctx.get_stage()

    # real bounds
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)
    rng = Gf.Range3d()
    for p in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()):
        if p.GetTypeName() == "Mesh":
            rng.UnionWith(bc.ComputeWorldBound(p).ComputeAlignedRange())
    mn, mx = rng.GetMin(), rng.GetMax()
    C = Gf.Vec3d((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2)
    d = max(mx[i] - mn[i] for i in range(3))

    cam = UsdGeom.Camera.Define(stage, "/World/OverviewCam")
    eye = C + Gf.Vec3d(d * 2.0, -d * 2.3, d * 1.6)
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 0, 1))
    cx = UsdGeom.Xformable(cam); cx.ClearXformOpOrder()
    cx.AddTransformOp().Set(view.GetInverse())
    cam.GetFocalLengthAttr().Set(35.0)

    from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
    vp = get_active_viewport()
    vp.set_active_camera("/World/OverviewCam")
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    capture_viewport_to_file(vp, SHOT)
    print("shot ->", SHOT, "| bbox z-height:", round(mx[2] - mn[2], 3))


main()
