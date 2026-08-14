"""Restore all clusters, then dump the VGR (NAUO2) sub-structure so we can find
its kinematic links (static base vs rotating column vs vertical carriage vs arm)."""
import omni.usd
from pxr import Usd, UsdGeom, Gf

ROOT = "/World/TrainingFactory/World/Factory/Assembly/Part_5"
VGR = ROOT + "/NAUO2"


def main():
    stage = omni.usd.get_context().get_stage()
    stage.SetEditTarget(stage.GetRootLayer())

    # restore any deactivated clusters
    restored = 0
    for child in stage.GetPrimAtPath(ROOT).GetChildren():
        if not child.IsActive():
            child.SetActive(True)
            restored += 1
    print("restored", restored, "clusters")

    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)
    vgr = stage.GetPrimAtPath(VGR)
    r = bc.ComputeWorldBound(vgr).ComputeAlignedRange()
    print("VGR world bbox:", [round(v, 3) for v in r.GetMin()], [round(v, 3) for v in r.GetMax()])

    # direct children (sub-assemblies) with bbox center/height/diag
    print("\nVGR sub-groups (name | center | dims | diag):")
    subs = []
    for c in vgr.GetChildren():
        cr = bc.ComputeWorldBound(c).ComputeAlignedRange()
        if cr.IsEmpty():
            continue
        mn, mx = cr.GetMin(), cr.GetMax()
        ctr = [round((mn[i] + mx[i]) / 2, 3) for i in range(3)]
        dims = [round(mx[i] - mn[i], 3) for i in range(3)]
        subs.append((round((mx - mn).GetLength(), 3), c.GetName(), ctr, dims))
    subs.sort(reverse=True)
    for diag, name, ctr, dims in subs:
        print(f"  {name:10} center={ctr} dims={dims} diag={diag}")


main()
