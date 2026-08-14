"""Build the official Training Factory USD scene from the imported glTF:
lights + ground + framed camera, save, and screenshot to verify."""
import os
import omni.usd
from pxr import Usd, UsdGeom, UsdLux, Gf, Vt

SAVE = r"C:/Users/icets/Downloads/digitaltwinsf/TrainingFactory_Industry40.usd"
SHOT = r"C:/Users/icets/Downloads/digitaltwinsf/twin/shots/factory_01.png"


def main():
    ctx = omni.usd.get_context()
    stage = ctx.get_stage()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)

    # world bbox of the factory
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)
    rng = bc.ComputeWorldBound(stage.GetPrimAtPath("/World/TrainingFactory")).ComputeAlignedRange()
    mn, mx = rng.GetMin(), rng.GetMax()
    C = [(mn[i] + mx[i]) / 2 for i in range(3)]
    dims = [mx[i] - mn[i] for i in range(3)]
    print("factory bbox min", [round(v, 2) for v in mn], "max", [round(v, 2) for v in mx])
    print("center", [round(v, 2) for v in C], "dims", [round(v, 2) for v in dims])

    # lights
    UsdLux.DomeLight.Define(stage, "/World/Lights/Dome").GetIntensityAttr().Set(1000)
    sun = UsdLux.DistantLight.Define(stage, "/World/Lights/Sun")
    sun.GetIntensityAttr().Set(3000)
    UsdGeom.Xformable(sun).AddRotateXYZOp().Set(Gf.Vec3f(315, 0, 25))

    # ground plane just under the model, sized to ~1.5x footprint
    foot = max(dims[0], dims[1]) * 1.5
    g = UsdGeom.Cube.Define(stage, "/World/Ground")
    g.GetSizeAttr().Set(1.0)
    gx = UsdGeom.Xformable(g)
    gx.AddTranslateOp().Set(Gf.Vec3d(C[0], C[1], mn[2] - 0.01))
    gx.AddScaleOp().Set(Gf.Vec3f(foot, foot, 0.02))
    g.GetDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(0.20, 0.21, 0.23)]))

    stage.SetDefaultPrim(stage.GetPrimAtPath("/World"))
    stage.GetRootLayer().Export(SAVE)
    print("saved ->", SAVE)

    # frame + screenshot
    ctx.get_selection().set_selected_prim_paths(["/World/TrainingFactory"], True)
    from omni.kit.viewport.utility import get_active_viewport, frame_viewport_selection, capture_viewport_to_file
    vp = get_active_viewport()
    frame_viewport_selection(vp)
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    capture_viewport_to_file(vp, SHOT)
    print("shot ->", SHOT)


main()
