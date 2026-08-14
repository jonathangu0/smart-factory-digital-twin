"""Stand the factory up: rotate Y-up model into the Z-up stage, re-ground, reframe."""
import os
import omni.usd
from pxr import Usd, UsdGeom, Gf, Vt

SAVE = r"C:/Users/icets/Downloads/digitaltwinsf/TrainingFactory_Industry40.usd"
SHOT = r"C:/Users/icets/Downloads/digitaltwinsf/twin/shots/factory_03.png"


def main():
    ctx = omni.usd.get_context()
    stage = ctx.get_stage()

    tf = stage.GetPrimAtPath("/World/TrainingFactory")
    xf = UsdGeom.Xformable(tf)
    M = xf.GetLocalTransformation()
    delta = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(1, 0, 0), 90.0))  # Y-up -> Z-up
    xf.ClearXformOpOrder()
    xf.AddTransformOp().Set(M * delta)

    # recompute real bounds after rotation
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)
    rng = Gf.Range3d()
    for p in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()):
        if p.GetTypeName() == "Mesh":
            rng.UnionWith(bc.ComputeWorldBound(p).ComputeAlignedRange())
    mn, mx = rng.GetMin(), rng.GetMax()
    C = Gf.Vec3d((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2)
    dims = [mx[i] - mn[i] for i in range(3)]
    d = max(dims)
    print("after rotate: bbox", [round(v, 2) for v in mn], [round(v, 2) for v in mx])
    print("center", [round(v, 2) for v in C], "dims", [round(v, 2) for v in dims])

    # ground under the model
    g = UsdGeom.Cube.Define(stage, "/World/Ground")
    g.GetSizeAttr().Set(1.0)
    gx = UsdGeom.Xformable(g); gx.ClearXformOpOrder()
    gx.AddTranslateOp().Set(Gf.Vec3d(C[0], C[1], mn[2] - 0.005))
    gx.AddScaleOp().Set(Gf.Vec3f(max(dims[0], dims[1]) * 1.5, max(dims[0], dims[1]) * 1.5, 0.01))
    g.GetDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(0.22, 0.23, 0.25)]))

    # overview camera
    cam = UsdGeom.Camera.Define(stage, "/World/OverviewCam")
    eye = C + Gf.Vec3d(d * 1.0, -d * 1.15, d * 0.8)
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 0, 1))
    cx = UsdGeom.Xformable(cam); cx.ClearXformOpOrder()
    cx.AddTransformOp().Set(view.GetInverse())
    cam.GetFocalLengthAttr().Set(22.0)

    stage.GetRootLayer().Export(SAVE)
    print("saved ->", SAVE)

    from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
    vp = get_active_viewport()
    vp.set_active_camera("/World/OverviewCam")
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    capture_viewport_to_file(vp, SHOT)
    print("shot ->", SHOT)


main()
