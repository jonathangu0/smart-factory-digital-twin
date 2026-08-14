"""Report world bboxes of MPO (NAUO10) sub-parts to identify moving elements."""
import omni.usd
from pxr import Usd, UsdGeom, Gf

MPO = "/World/TrainingFactory/World/Factory/Assembly/Part_5/NAUO10"


def main():
    stage = omni.usd.get_context().get_stage()
    mpo = stage.GetPrimAtPath(MPO)
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)
    r = bc.ComputeWorldBound(mpo).ComputeAlignedRange()
    mn, mx = r.GetMin(), r.GetMax()
    print(f"MPO overall C=({(mn[0]+mx[0])/2:+.3f},{(mn[1]+mx[1])/2:+.3f},{(mn[2]+mx[2])/2:+.3f}) "
          f"SIZE=({mx[0]-mn[0]:.3f},{mx[1]-mn[1]:.3f},{mx[2]-mn[2]:.3f})")
    kids = list(mpo.GetAllChildren())
    print("num children:", len(kids))
    for c in kids:
        rr = bc.ComputeWorldBound(c).ComputeAlignedRange()
        a, b = rr.GetMin(), rr.GetMax()
        cc = Gf.Vec3d((a[0]+b[0])/2, (a[1]+b[1])/2, (a[2]+b[2])/2)
        sz = Gf.Vec3d(b[0]-a[0], b[1]-a[1], b[2]-a[2])
        nm = c.GetName()
        disp = c.GetAttribute("userProperties:originalName")
        extra = ""
        print(f"  {nm:10s} C=({cc[0]:+.3f},{cc[1]:+.3f},{cc[2]:+.3f}) "
              f"SIZE=({sz[0]:.3f},{sz[1]:.3f},{sz[2]:.3f})")


main()
