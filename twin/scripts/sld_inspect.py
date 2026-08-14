"""Inspect SLD (NAUO6) sub-parts to find belt axis + the 3 color ejectors."""
import omni.usd
from pxr import Usd, UsdGeom, Gf

SLD = "/World/TrainingFactory/World/Factory/Assembly/Part_5/NAUO6"


def main():
    stage = omni.usd.get_context().get_stage()
    sld = stage.GetPrimAtPath(SLD)
    if not (sld and sld.IsValid()):
        print("NAUO6 invalid"); return
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)
    r = bc.ComputeWorldBound(sld).ComputeAlignedRange()
    mn, mx = r.GetMin(), r.GetMax()
    print(f"SLD overall C=({(mn[0]+mx[0])/2:+.3f},{(mn[1]+mx[1])/2:+.3f},{(mn[2]+mx[2])/2:+.3f}) "
          f"SIZE=({mx[0]-mn[0]:.3f},{mx[1]-mn[1]:.3f},{mx[2]-mn[2]:.3f})")
    kids = list(sld.GetAllChildren())
    print("children:", len(kids))
    for c in kids:
        rr = bc.ComputeWorldBound(c).ComputeAlignedRange()
        a, b = rr.GetMin(), rr.GetMax()
        cc = Gf.Vec3d((a[0]+b[0])/2, (a[1]+b[1])/2, (a[2]+b[2])/2)
        sz = Gf.Vec3d(b[0]-a[0], b[1]-a[1], b[2]-a[2])
        print(f"  {c.GetName():10s} C=({cc[0]:+.3f},{cc[1]:+.3f},{cc[2]:+.3f}) "
              f"SIZE=({sz[0]:.3f},{sz[1]:.3f},{sz[2]:.3f})")


main()
