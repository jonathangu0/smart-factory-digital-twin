"""VGR articulation in WORLD space (fixes 'arm slides to the side' bug):
  ROTATE (2856+2857+2858) about the vertical pivot axis
  VERTICAL lift (2857+2858) = straight down WORLD -Z (stays between the mast bars)
  HORIZONTAL extend (2858) = along the arm's radial direction (WORLD, home = -Y)
Excludes the static vacuum/compressor cylinders (2859/2860). Live from OPC-UA.
Set builtins._vgr_test_pose=(rot,ver,hor) to force a pose; None = live.
"""
import omni.usd
import omni.kit.app
import builtins
from pxr import UsdGeom, Gf

VGRP = "/World/TrainingFactory/World/Factory/Assembly/Part_5/NAUO2"
PIVOT = Gf.Vec3d(0.05, -0.17, 0.0)     # world rotation axis (X,Y)
ARM_DIR = Gf.Vec3d(0.0, -1.0, 0.0)     # world direction the arm extends at home
ROT_270, VERT_MAX, HORIZ_MAX = 5331, 2993, 3377
VERT_TRAVEL = 0.12     # 120 mm
HORIZ_TRAVEL = 0.14    # 140 mm
ROT_SIGN, VERT_SIGN, HORIZ_SIGN = 1.0, 1.0, 1.0

ROTATE = ["NAUO2856", "NAUO2857", "NAUO2858"]
VERTICAL = ["NAUO2857", "NAUO2858"]
HORIZONTAL = ["NAUO2858"]

# world point at the gripper suction cup when at home (published for the workpiece)
SUCTION_HOME = Gf.Vec3d(0.153, -0.214, 0.176)
# arm+gripper sit +0.108 in X off the tower; shift them onto the pillar so the
# horizontal beam runs THROUGH the column (matches the documentation).
ARM_CENTER_FIX = Gf.Vec3d(-0.108, 0.0, 0.0)


def main():
    stage = omni.usd.get_context().get_stage()
    stage.SetEditTarget(stage.GetRootLayer())
    vgr = stage.GetPrimAtPath(VGRP)
    Pp = UsdGeom.XformCache().GetLocalToWorldTransform(vgr)
    Pinv = Pp.GetInverse()

    home = {}
    for name in ROTATE:
        c = stage.GetPrimAtPath(f"{VGRP}/{name}")
        if not (c and c.IsValid()):
            print("missing", name); continue
        xf = UsdGeom.Xformable(c)
        L0 = xf.GetLocalTransformation()
        xf.ClearXformOpOrder()
        xf.AddTransformOp().Set(L0)
        home[name] = (xf, L0)

    def T(v):
        return Gf.Matrix4d().SetTranslate(v)

    def apply(rot, ver, hor):
        angle = ROT_SIGN * (rot / ROT_270) * 270.0
        drop = VERT_SIGN * (ver / VERT_MAX) * VERT_TRAVEL
        ext = HORIZ_SIGN * (hor / HORIZ_MAX) * HORIZ_TRAVEL
        Rz = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), angle))
        Rw = T(-PIVOT) * Rz * T(PIVOT)          # world rotation about pivot
        Tl = T(Gf.Vec3d(0, 0, -drop))           # world Z lift
        Te = T(Gf.Vec3d(ARM_DIR[0]*ext, ARM_DIR[1]*ext, ARM_DIR[2]*ext))  # extend along arm
        Tc = T(ARM_CENTER_FIX)                   # center the beam on the pillar
        Dw_arm = Tc * Rw * Tl                    # arm carriage
        Dw_grip = Tc * Te * Rw * Tl              # gripper (also horizontal extend)
        for name, (xf, L0) in home.items():
            if name in HORIZONTAL:
                Dw = Dw_grip
            elif name in VERTICAL:
                Dw = Dw_arm
            else:
                Dw = Rw
            xf.GetOrderedXformOps()[0].Set(L0 * (Pp * Dw * Pinv))
        # publish the gripper suction point so a workpiece can ride with it
        sp = Dw_grip.Transform(SUCTION_HOME)
        builtins._vgr_grip_pos = (sp[0], sp[1], sp[2])

    builtins._vgr_apply = apply

    def _update(_e):
        tp = getattr(builtins, "_vgr_test_pose", None)
        if tp is not None:
            apply(*tp)
        else:
            st = getattr(builtins, "_factory_state", {}) or {}
            apply(st.get("vgr_rot") or 0, st.get("vgr_ver") or 0, st.get("vgr_hor") or 0)

    builtins._vgr_artic_sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
        _update, name="vgr_full")
    print("VGR world-space articulation running")


main()
