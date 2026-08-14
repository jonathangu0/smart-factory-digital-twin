"""Explore the MPO cluster (NAUO10, back-center 'Processing Station'): find the
turntable (rotating disc), oven slider, saw, and conveyor sub-groups."""
import omni.usd
from pxr import Usd, UsdGeom, Gf

MPO = "/World/TrainingFactory/World/Factory/Assembly/Part_5/NAUO10"


def names(prim):
    d = {}
    for p in Usd.PrimRange(prim):
        n = p.GetName().lower()
        if n.startswith(("nauo", "mesh", "importiert", "fase")):
            continue
        k = ''.join(c for c in n if not c.isdigit()).strip("_")
        if len(k) > 2:
            d[k] = d.get(k, 0) + 1
    return sorted(d.items(), key=lambda x: -x[1])[:6]


def main():
    stage = omni.usd.get_context().get_stage()
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)
    mpo = stage.GetPrimAtPath(MPO)
    r = bc.ComputeWorldBound(mpo).ComputeAlignedRange()
    print("MPO bbox:", [round(v, 3) for v in r.GetMin()], [round(v, 3) for v in r.GetMax()])
    subs = []
    for c in mpo.GetChildren():
        cr = bc.ComputeWorldBound(c).ComputeAlignedRange()
        if cr.IsEmpty():
            continue
        mn, mx = cr.GetMin(), cr.GetMax()
        ctr = [round((mn[i]+mx[i])/2, 3) for i in range(3)]
        dims = [round(mx[i]-mn[i], 3) for i in range(3)]
        subs.append((round((mx-mn).GetLength(), 3), c.GetName(), ctr, dims, names(c)))
    subs.sort(reverse=True)
    for diag, name, ctr, dims, nm in subs[:14]:
        print(f"  {name:10} diag={diag} center={ctr} dims={dims} parts={[p[0] for p in nm]}")


main()
