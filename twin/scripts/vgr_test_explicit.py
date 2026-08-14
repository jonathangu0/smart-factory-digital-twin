"""Pause the live driver and test-rotate an EXPLICIT tower+arm set by 90 deg,
with a VGR close-up, to verify clean part selection (base electronics stay put)."""
import os
import omni.usd
import omni.kit.app
import builtins
from pxr import Usd, UsdGeom, Gf

VGRP = "/World/TrainingFactory/World/Factory/Assembly/Part_5/NAUO2"
PIVOT = Gf.Vec3d(0.05, -0.17, 0.0)
ANGLE = 90.0
ROTATING = ["NAUO2856", "NAUO2857", "NAUO2858"]  # column + arm sub-assemblies
SHOT = r"C:/Users/icets/Downloads/digitaltwinsf/twin/shots/vgr_explicit.png"


def main():
    # stop the live articulation callback so it doesn't overwrite our test
    builtins._vgr_artic_sub = None

    stage = omni.usd.get_context().get_stage()
    stage.SetEditTarget(stage.GetRootLayer())
    vgr = stage.GetPrimAtPath(VGRP)
    xc = UsdGeom.XformCache()
    Pp = xc.GetLocalToWorldTransform(vgr)
    Rz = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), ANGLE))
    d = Gf.Matrix4d().SetTranslate(-PIVOT) * Rz * Gf.Matrix4d().SetTranslate(PIVOT)
    inner = Pp * d * Pp.GetInverse()

    for name in ROTATING:
        c = stage.GetPrimAtPath(f"{VGRP}/{name}")
        if not (c and c.IsValid()):
            print("missing", name); continue
        xf = UsdGeom.Xformable(c)
        L = xf.GetLocalTransformation()
        xf.ClearXformOpOrder()
        xf.AddTransformOp().Set(L * inner)
    print("rotated", ROTATING, "by", ANGLE)

    # close-up camera on the VGR
    C = Gf.Vec3d(0.05, -0.15, 0.16)
    cam = UsdGeom.Camera.Define(stage, "/World/VGRCam")
    eye = C + Gf.Vec3d(0.42, -0.42, 0.28)
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 0, 1))
    cx = UsdGeom.Xformable(cam); cx.ClearXformOpOrder()
    cx.AddTransformOp().Set(view.GetInverse())
    cam.GetFocalLengthAttr().Set(30.0)

    from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
    vp = get_active_viewport()
    vp.set_active_camera("/World/VGRCam")
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    capture_viewport_to_file(vp, SHOT)
    print("shot ->", SHOT)


main()
