"""Find HBW crane travel rail extent, bay pick positions, and the VGR-HBW
transfer point, to calibrate crane motion precisely."""
import omni.usd
from pxr import Usd, UsdGeom, Gf

HBW = "/World/TrainingFactory/World/Factory/Assembly/Part_5/NAUO11"
VGR = "/World/TrainingFactory/World/Factory/Assembly/Part_5/NAUO2"


def main():
    stage = omni.usd.get_context().get_stage()
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)

    def rng(path):
        r = bc.ComputeWorldBound(stage.GetPrimAtPath(path)).ComputeAlignedRange()
        return r.GetMin(), r.GetMax()

    vmn, vmx = rng(VGR)
    print(f"VGR bounds X[{vmn[0]:+.3f},{vmx[0]:+.3f}] Y[{vmn[1]:+.3f},{vmx[1]:+.3f}]")

    hbw = stage.GetPrimAtPath(HBW)
    # long-Y low-Z parts = floor travel rail candidates
    print("--- floor-rail candidates (long Y, low Z) ---")
    for c in hbw.GetAllChildren():
        a, b = rng(c.GetPath().pathString)
        sy, sz = b[1]-a[1], b[2]-a[2]
        cz = (a[2]+b[2])/2
        if sy > 0.30 and cz < 0.08:
            print(f"  {c.GetName():8s} Yextent[{a[1]:+.3f},{b[1]:+.3f}] Zc={cz:+.3f} "
                  f"Xc={(a[0]+b[0])/2:+.3f} SIZE=({b[0]-a[0]:.3f},{sy:.3f},{sz:.3f})")

    # bay pick columns: parts at X ~ -0.239, group Y & Z
    print("--- rack bay cells (X~-0.239) Y/Z grid ---")
    ys, zs = set(), set()
    for c in hbw.GetAllChildren():
        a, b = rng(c.GetPath().pathString)
        cx, cy, cz = (a[0]+b[0])/2, (a[1]+b[1])/2, (a[2]+b[2])/2
        if -0.25 < cx < -0.225 and 0.10 < cz < 0.25 and (b[0]-a[0]) < 0.04:
            ys.add(round(cy, 3)); zs.add(round(cz, 3))
    print("  bay Y set:", sorted(ys))
    print("  bay Z set:", sorted(zs))

    # crane current position
    for n in ["NAUO47", "NAUO48", "NAUO49"]:
        a, b = rng(f"{HBW}/{n}")
        print(f"  crane {n}: Xc={(a[0]+b[0])/2:+.3f} Yc={(a[1]+b[1])/2:+.3f} Zc={(a[2]+b[2])/2:+.3f}")

    # -Y end (toward VGR) candidate transfer parts
    print("--- -Y end parts (toward VGR, transfer candidates) ---")
    for c in hbw.GetAllChildren():
        a, b = rng(c.GetPath().pathString)
        cy = (a[1]+b[1])/2
        if cy < -0.20:
            print(f"  {c.GetName():8s} C=({(a[0]+b[0])/2:+.3f},{cy:+.3f},{(a[2]+b[2])/2:+.3f}) "
                  f"SIZE=({b[0]-a[0]:.3f},{b[1]-a[1]:.3f},{b[2]-a[2]:.3f})")


main()
