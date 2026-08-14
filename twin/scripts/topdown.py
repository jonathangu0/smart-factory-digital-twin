"""Top-down capture to map station layout."""
import os
import omni.usd
from pxr import Usd, UsdGeom, Gf

SHOT = r"C:/Users/icets/Downloads/digitaltwinsf/twin/shots/factory_top.png"


def main():
    ctx = omni.usd.get_context()
    stage = ctx.get_stage()
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)
    rng = Gf.Range3d()
    for p in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()):
        if p.GetTypeName() == "Mesh":
            rng.UnionWith(bc.ComputeWorldBound(p).ComputeAlignedRange())
    mn, mx = rng.GetMin(), rng.GetMax()
    C = Gf.Vec3d((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2)
    d = max(mx[0] - mn[0], mx[1] - mn[1])
    print("footprint X", round(mn[0], 2), "..", round(mx[0], 2),
          "| Y", round(mn[1], 2), "..", round(mx[1], 2))

    cam = UsdGeom.Camera.Define(stage, "/World/TopCam")
    eye = Gf.Vec3d(C[0], C[1] - 0.001, C[2] + d * 1.8)  # almost straight down, slight tilt
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 1, 0))  # up = +Y
    cx = UsdGeom.Xformable(cam); cx.ClearXformOpOrder()
    cx.AddTransformOp().Set(view.GetInverse())
    cam.GetFocalLengthAttr().Set(30.0)

    from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
    vp = get_active_viewport()
    vp.set_active_camera("/World/TopCam")
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    capture_viewport_to_file(vp, SHOT)
    print("shot ->", SHOT)


main()
