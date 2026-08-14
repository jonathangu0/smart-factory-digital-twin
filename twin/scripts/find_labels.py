"""Find the station name-plate labels and map each to its factory cluster."""
import omni.usd
from pxr import Usd, UsdGeom, Gf

ROOT = "/World/TrainingFactory/World/Factory/Assembly/Part_5"


def main():
    stage = omni.usd.get_context().get_stage()
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)

    # cluster centers
    clusters = {}
    root = stage.GetPrimAtPath(ROOT)
    for c in root.GetChildren():
        r = bc.ComputeWorldBound(c).ComputeAlignedRange()
        if not r.IsEmpty():
            clusters[c.GetName()] = (r.GetMin() + r.GetMax()) * 0.5

    def nearest(pos):
        best, bd = None, 1e9
        for name, ctr in clusters.items():
            dxy = ((pos[0]-ctr[0])**2 + (pos[1]-ctr[1])**2) ** 0.5
            if dxy < bd:
                best, bd = name, dxy
        return best, round(bd, 3)

    # find label-ish prims (fischertechnik name plates)
    keys = ("schild", "label", "beschrift", "name", "text", "plate", "logo", "sign")
    seen = set()
    for p in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()):
        ln = p.GetName().lower()
        if any(k in ln for k in keys):
            r = bc.ComputeWorldBound(p).ComputeAlignedRange()
            if r.IsEmpty():
                continue
            pos = (r.GetMin() + r.GetMax()) * 0.5
            key = (p.GetName(), round(pos[0], 2), round(pos[1], 2))
            if key in seen:
                continue
            seen.add(key)
            nb, dist = nearest(pos)
            print(f"{p.GetName():28} pos={[round(v,2) for v in pos]} -> cluster {nb} (d={dist})")

    print("\n--- cluster centers for reference ---")
    for name, ctr in sorted(clusters.items(), key=lambda x: -((x[1][0])**2+(x[1][1])**2)):
        print(f"  {name:10} center={[round(v,2) for v in ctr]}")


main()
