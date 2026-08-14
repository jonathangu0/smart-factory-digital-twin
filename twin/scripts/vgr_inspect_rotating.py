"""Inspect the VGR (NAUO2) parts: list the currently-rotating group (Z>=0.055)
with representative inner part names, and locate base electronics
(battery / TXT controller / circuit board) that must NOT rotate."""
import omni.usd
from pxr import Usd, UsdGeom, Gf

VGR = "/World/TrainingFactory/World/Factory/Assembly/Part_5/NAUO2"
Z_ROTATE = 0.055
ELECTRONICS = ("akku", "batt", "batterie", "platine", "txt", "controller",
               "board", "elektronik", "9v", "motoransteuer", "relais", "buchse")


def distinctive_names(prim):
    names = {}
    for p in Usd.PrimRange(prim):
        n = p.GetName()
        ln = n.lower()
        if n.startswith("NAUO") or n.startswith("Mesh") or ln.startswith(("importiert", "fase")):
            continue
        key = ''.join(ch for ch in ln if not ch.isdigit()).strip("_")
        if len(key) > 2:
            names[key] = names.get(key, 0) + 1
    return sorted(names.items(), key=lambda x: -x[1])[:6]


def main():
    stage = omni.usd.get_context().get_stage()
    vgr = stage.GetPrimAtPath(VGR)
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)

    print("=== CURRENTLY ROTATING children (center Z >= %.3f) ===" % Z_ROTATE)
    for c in vgr.GetChildren():
        r = bc.ComputeWorldBound(c).ComputeAlignedRange()
        if r.IsEmpty():
            continue
        mn, mx = r.GetMin(), r.GetMax()
        zc = (mn[2] + mx[2]) / 2
        if zc >= Z_ROTATE:
            ctr = [round((mn[i] + mx[i]) / 2, 3) for i in range(3)]
            dims = [round(mx[i] - mn[i], 3) for i in range(3)]
            parts = distinctive_names(c)
            print(f"  {c.GetName()} zc={round(zc,3)} center={ctr} dims={dims}")
            print(f"     parts: {[p[0] for p in parts]}")

    print("\n=== ELECTRONICS parts anywhere in the VGR (should be STATIC) ===")
    for p in Usd.PrimRange(vgr):
        ln = p.GetName().lower()
        if any(k in ln for k in ELECTRONICS):
            r = bc.ComputeWorldBound(p).ComputeAlignedRange()
            if r.IsEmpty():
                continue
            zc = round((r.GetMin()[2] + r.GetMax()[2]) / 2, 3)
            # which top-level NAUO2 child owns it
            owner = p
            while owner.GetParent() and owner.GetParent().GetPath().pathString != VGR:
                owner = owner.GetParent()
            flag = "  <-- ROTATING!" if zc >= Z_ROTATE else ""
            print(f"  {p.GetName()} zc={zc} owner={owner.GetName()}{flag}")


main()
