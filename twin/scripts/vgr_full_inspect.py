"""Full VGR inspection: separate the fixed base from the rotating tower and
find the true rotation axis (base center)."""
import omni.usd
from pxr import Usd, UsdGeom, Gf

VGR = "/World/TrainingFactory/World/Factory/Assembly/Part_5/NAUO2"


def main():
    stage = omni.usd.get_context().get_stage()
    vgr = stage.GetPrimAtPath(VGR)
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)
    r = bc.ComputeWorldBound(vgr).ComputeAlignedRange()
    mn, mx = r.GetMin(), r.GetMax()
    print(f"VGR overall C=({(mn[0]+mx[0])/2:+.3f},{(mn[1]+mx[1])/2:+.3f},{(mn[2]+mx[2])/2:+.3f}) "
          f"SIZE=({mx[0]-mn[0]:.3f},{mx[1]-mn[1]:.3f},{mx[2]-mn[2]:.3f})")
    kids = list(vgr.GetAllChildren())
    print("num children:", len(kids))
    rows = []
    for c in kids:
        rr = bc.ComputeWorldBound(c).ComputeAlignedRange()
        a, b = rr.GetMin(), rr.GetMax()
        rows.append((round((a[2]+b[2])/2, 3), c.GetName(),
                     round((a[0]+b[0])/2, 3), round((a[1]+b[1])/2, 3),
                     round(b[0]-a[0], 3), round(b[1]-a[1], 3), round(b[2]-a[2], 3)))
    rows.sort()
    for z, n, cx, cy, sx, sy, sz in rows:
        print(f"  {n:10s} Zc={z:+.3f} C=({cx:+.3f},{cy:+.3f}) SIZE=({sx:.3f},{sy:.3f},{sz:.3f})")


main()
