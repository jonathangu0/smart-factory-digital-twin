"""Diagnose why the CAD VGR isn't rendering: lights, meshes, points, references."""
import os
import omni.usd
from pxr import Usd, UsdGeom, UsdLux, Gf


def main():
    ctx = omni.usd.get_context()
    stage = ctx.get_stage()
    print("stage:", stage.GetRootLayer().identifier)

    # companion files next to vgr.usd?
    d = r"C:/Users/icets/Downloads/digitaltwinsf/twin/usd"
    print("usd folder:", [f for f in os.listdir(d)])

    # count meshes INCLUDING instance proxies, and check points on the first few
    rng = Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies())
    meshes = [p for p in rng if p.GetTypeName() == "Mesh"]
    print("Mesh prims (incl. instance proxies):", len(meshes))
    with_points = 0
    for m in meshes[:200]:
        pts = UsdGeom.Mesh(m).GetPointsAttr().Get()
        if pts and len(pts) > 0:
            with_points += 1
    print("of first 200 meshes, with points:", with_points)

    # existing lights?
    lights = [p.GetPath().pathString for p in stage.Traverse()
              if p.GetTypeName() in ("DomeLight", "DistantLight", "SphereLight", "RectLight")]
    print("existing lights:", lights)

    # any unresolved / missing references?
    missing = []
    for p in stage.Traverse():
        if p.HasAuthoredReferences() and not p.IsValid():
            missing.append(p.GetPath().pathString)
    print("invalid prims:", len(missing))

    # add lights so unlit CAD becomes visible
    UsdLux.DomeLight.Define(stage, "/vgr/_DomeLight").GetIntensityAttr().Set(1200)
    sun = UsdLux.DistantLight.Define(stage, "/vgr/_Sun")
    sun.GetIntensityAttr().Set(3000)
    UsdGeom.Xformable(sun).AddRotateXYZOp().Set(Gf.Vec3f(315, 0, 25))
    print("added dome + distant light")


main()
