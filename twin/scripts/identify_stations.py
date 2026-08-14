"""Identify each station's geometry cluster: for each big NAUO group under the
factory, print its bbox center + the distinctive (named) parts inside it, so we
can tell which cluster is the VGR / HBW / conveyors / etc."""
import omni.usd
from pxr import Usd, UsdGeom, Gf

ROOT = "/World/TrainingFactory/World/Factory/Assembly/Part_5"


def main():
    stage = omni.usd.get_context().get_stage()
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)
    root = stage.GetPrimAtPath(ROOT)
    if not (root and root.IsValid()):
        print("root not found:", ROOT)
        return

    clusters = []
    for child in root.GetChildren():
        r = bc.ComputeWorldBound(child).ComputeAlignedRange()
        if r.IsEmpty():
            continue
        mn, mx = r.GetMin(), r.GetMax()
        c = [round((mn[i] + mx[i]) / 2, 2) for i in range(3)]
        diag = round((mx - mn).GetLength(), 2)
        # distinctive named parts inside (skip generic NAUO / Mesh / Fase etc.)
        names = {}
        for p in Usd.PrimRange(child):
            n = p.GetName()
            ln = n.lower()
            if n.startswith("NAUO") or n.startswith("Mesh") or ln.startswith("importiert"):
                continue
            key = ''.join(ch for ch in ln if not ch.isdigit()).strip("_")
            if len(key) > 2:
                names[key] = names.get(key, 0) + 1
        top = sorted(names.items(), key=lambda x: -x[1])[:10]
        clusters.append((diag, child.GetName(), c, top))

    clusters.sort(reverse=True)
    for diag, name, c, top in clusters[:12]:
        print(f"{name}  diag={diag}  center={c}")
        print("   parts:", ", ".join(f"{k}({v})" for k, v in top))


main()
