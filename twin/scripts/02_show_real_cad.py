"""Enable viewport capture, load the REAL CAD VGR, frame it, so we can verify."""
import omni.usd
import omni.kit.app
from pxr import Usd, UsdGeom, Gf

VGR = r"C:/Users/icets/Downloads/digitaltwinsf/twin/usd/vgr.usd"


def main():
    # 1) enable screenshot capability
    mgr = omni.kit.app.get_app().get_extension_manager()
    for ext in ("omni.kit.viewport.utility", "omni.kit.capture.viewport"):
        try:
            mgr.set_extension_enabled_immediate(ext, True)
            print("enabled:", ext)
        except Exception as e:
            print("could not enable", ext, "->", repr(e))

    # 2) open the real CAD
    ctx = omni.usd.get_context()
    ctx.open_stage(VGR)
    stage = ctx.get_stage()

    # 3) world bbox of the model
    bcache = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                              [UsdGeom.Tokens.default_, UsdGeom.Tokens.render],
                              useExtentsHint=True)
    rng = bcache.ComputeWorldBound(stage.GetPrimAtPath("/vgr")).ComputeAlignedRange()
    mn, mx = rng.GetMin(), rng.GetMax()
    C = Gf.Vec3d((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2)
    maxdim = max(mx[i] - mn[i] for i in range(3))
    print("BBOX min", [round(v, 1) for v in mn], "max", [round(v, 1) for v in mx])
    print("center", [round(v, 1) for v in C], "maxdim", round(maxdim, 1))

    # 4) frame the default perspective camera (stage up = Z)
    eye = C + Gf.Vec3d(maxdim * 1.1, -maxdim * 1.3, maxdim * 0.9)
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 0, 1))
    cam = stage.GetPrimAtPath("/OmniverseKit_Persp")
    if cam and cam.IsValid():
        xf = UsdGeom.Xformable(cam)
        xf.ClearXformOpOrder()
        xf.AddTransformOp().Set(view.GetInverse())
        print("framed /OmniverseKit_Persp at eye", [round(v, 1) for v in eye])
    else:
        print("no persp camera found")


main()
