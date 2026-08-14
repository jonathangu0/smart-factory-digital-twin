"""Find the HBW cluster (owner of the High_Bay_warehouse label) and dump its
sub-structure to identify the moving crane (mast/fork) vs the static rack."""
import omni.usd
from pxr import Usd, UsdGeom, Gf

P5 = "/World/TrainingFactory/World/Factory/Assembly/Part_5"


def top_owner(prim):
    o = prim
    while o.GetParent() and o.GetParent().GetPath().pathString != P5:
        o = o.GetParent()
    return o


def main():
    stage = omni.usd.get_context().get_stage()
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)

    # locate the HBW cluster via its label
    hbw_cluster = None
    for p in Usd.PrimRange(stage.GetPrimAtPath("/World/TrainingFactory")):
        if "high_bay" in p.GetName().lower():
            hbw_cluster = top_owner(p)
            break
    if not hbw_cluster:
        print("HBW label not found"); return
    print("HBW cluster:", hbw_cluster.GetName())
    r = bc.ComputeWorldBound(hbw_cluster).ComputeAlignedRange()
    print("HBW bbox:", [round(v, 3) for v in r.GetMin()], [round(v, 3) for v in r.GetMax()])

    subs = []
    for c in hbw_cluster.GetChildren():
        cr = bc.ComputeWorldBound(c).ComputeAlignedRange()
        if cr.IsEmpty():
            continue
        mn, mx = cr.GetMin(), cr.GetMax()
        ctr = [round((mn[i] + mx[i]) / 2, 3) for i in range(3)]
        dims = [round(mx[i] - mn[i], 3) for i in range(3)]
        subs.append((round((mx - mn).GetLength(), 3), c.GetName(), ctr, dims))
    subs.sort(reverse=True)
    print("HBW sub-groups (largest first):")
    for diag, name, ctr, dims in subs[:20]:
        print(f"  {name:10} center={ctr} dims={dims} diag={diag}")


main()
