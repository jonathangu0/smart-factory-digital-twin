"""Report world-space bboxes/centers of VGR sub-parts to learn the true axes."""
import omni.usd
from pxr import Usd, UsdGeom, Gf

VGRP = "/World/TrainingFactory/World/Factory/Assembly/Part_5/NAUO2"
PARTS = ["NAUO2856", "NAUO2857", "NAUO2858", "NAUO2859", "NAUO2860", "NAUO2862"]
LABEL = {"NAUO2856": "mast/column", "NAUO2857": "arm-carriage",
         "NAUO2858": "gripper", "NAUO2859": "vac-cyl1", "NAUO2860": "vac-cyl2",
         "NAUO2862": "netzadapter"}


def main():
    stage = omni.usd.get_context().get_stage()
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)
    xc = UsdGeom.XformCache()
    for name in PARTS:
        p = stage.GetPrimAtPath(f"{VGRP}/{name}")
        if not (p and p.IsValid()):
            print(name, "MISSING"); continue
        rng = bc.ComputeWorldBound(p).ComputeAlignedRange()
        mn, mx = rng.GetMin(), rng.GetMax()
        c = Gf.Vec3d((mn[0]+mx[0])/2, (mn[1]+mx[1])/2, (mn[2]+mx[2])/2)
        size = Gf.Vec3d(mx[0]-mn[0], mx[1]-mn[1], mx[2]-mn[2])
        m = xc.GetLocalToWorldTransform(p)
        origin = m.ExtractTranslation()
        print(f"{name} {LABEL.get(name,''):12s} "
              f"C=({c[0]:+.3f},{c[1]:+.3f},{c[2]:+.3f}) "
              f"SIZE=({size[0]:.3f},{size[1]:.3f},{size[2]:.3f}) "
              f"O=({origin[0]:+.3f},{origin[1]:+.3f},{origin[2]:+.3f})")


main()
