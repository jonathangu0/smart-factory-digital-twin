"""Reset the test-rotated VGR parts (2856/57/58) back to home via inverse rotation."""
import omni.usd
from pxr import UsdGeom, Gf

VGRP = "/World/TrainingFactory/World/Factory/Assembly/Part_5/NAUO2"
PIVOT = Gf.Vec3d(0.05, -0.17, 0.0)
PARTS = ["NAUO2856", "NAUO2857", "NAUO2858"]


def main():
    stage = omni.usd.get_context().get_stage()
    stage.SetEditTarget(stage.GetRootLayer())
    vgr = stage.GetPrimAtPath(VGRP)
    Pp = UsdGeom.XformCache().GetLocalToWorldTransform(vgr)
    Rz = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), 90.0))
    d = Gf.Matrix4d().SetTranslate(-PIVOT) * Rz * Gf.Matrix4d().SetTranslate(PIVOT)
    inv90 = (Pp * d * Pp.GetInverse()).GetInverse()
    for name in PARTS:
        c = stage.GetPrimAtPath(f"{VGRP}/{name}")
        xf = UsdGeom.Xformable(c)
        cur = xf.GetLocalTransformation()
        xf.ClearXformOpOrder()
        xf.AddTransformOp().Set(cur * inv90)
    print("reset to home:", PARTS)


main()
