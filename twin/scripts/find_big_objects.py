"""Identify the two giant grey shapes: largest meshes + any camera-named prims."""
import omni.usd
from pxr import Usd, UsdGeom, Gf


def main():
    ctx = omni.usd.get_context()
    stage = ctx.get_stage()
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)

    # camera-type prims and camera-named prims
    cams = []
    named = []
    for p in stage.Traverse():
        tn = p.GetTypeName()
        nm = p.GetName().lower()
        if tn == "Camera":
            cams.append(p.GetPath().pathString)
        if any(k in nm for k in ("camera", "kamera", "webcam", "cam_")):
            named.append(f"{p.GetPath()} [{tn}]")
    print("Camera-type prims:", cams)
    print("camera-named prims:", named[:30])

    # largest single meshes by bbox diagonal
    sizes = []
    for p in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()):
        if p.GetTypeName() == "Mesh":
            r = bc.ComputeWorldBound(p).ComputeAlignedRange()
            if not r.IsEmpty():
                d = (r.GetMax() - r.GetMin()).GetLength()
                sizes.append((d, p.GetPath().pathString))
    sizes.sort(reverse=True)
    print("\nTOP 12 LARGEST MESHES (diagonal m, path):")
    for d, path in sizes[:12]:
        print(f"  {round(d,3):>7}  {path}")

    # direct children of the geometry root, with bbox sizes, to spot the 2 big groups
    root = stage.GetPrimAtPath("/World/TrainingFactory/World/Factory/Assembly/Part_5")
    if root and root.IsValid():
        print("\nPart_5 direct children bbox diagonals:")
        kids = []
        for c in root.GetChildren():
            r = bc.ComputeWorldBound(c).ComputeAlignedRange()
            if not r.IsEmpty():
                kids.append(((r.GetMax() - r.GetMin()).GetLength(), c.GetName()))
        kids.sort(reverse=True)
        for d, n in kids[:15]:
            print(f"  {round(d,3):>7}  {n}")


main()
