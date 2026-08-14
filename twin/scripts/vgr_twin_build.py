"""
vgr_twin_build.py — build a clean, kinematic VGR digital-twin in a fresh Z-up stage.

Hierarchy (each *group* is a pure Xform with ONE driven op):
  /World/VGR
    Base                 static plate
    Rotate   (rotZ)      column + everything above rotates about Z
      column             static
      Vertical (transЗ)  carriage slides down the column
        carriage
        Horizontal (transX)  arm extends
          arm
          Gripper           head + suction at the arm tip

set_pose(rotate_ct, vertical_ct, horizontal_ct) maps raw OPC-UA pulse counts to
the three driven ops using the smart-factory calibration.
"""
import omni.usd
from pxr import Usd, UsdGeom, UsdLux, Gf, Sdf, Vt

STAGE = r"C:/Users/icets/Downloads/digitaltwinsf/twin/usd/vgr_twin.usd"

# --- calibration (counts at travel extremes) ---
ROT_270, VERT_MAX, HORIZ_MAX = 5331, 2993, 3377
# --- scene travel (meters) ---
COLUMN_H, VERT_TRAVEL, HORIZ_TRAVEL, ARM_BASE = 0.50, 0.34, 0.26, 0.10
ROT_SIGN, ROT_OFFSET_DEG = 1.0, 0.0   # tune sign/heading against the real robot

_C = {}  # cache of driven Xformable ops, filled by build()


def _box(stage, path, sx, sy, sz, tx, ty, tz, color):
    c = UsdGeom.Cube.Define(stage, path)
    c.GetSizeAttr().Set(1.0)
    xf = UsdGeom.Xformable(c)
    xf.AddTranslateOp().Set(Gf.Vec3d(tx, ty, tz))
    xf.AddScaleOp().Set(Gf.Vec3f(sx, sy, sz))
    c.GetDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*color)]))
    return c


def _cyl(stage, path, radius, height, tx, ty, tz, color):
    c = UsdGeom.Cylinder.Define(stage, path)
    c.GetRadiusAttr().Set(radius); c.GetHeightAttr().Set(height); c.GetAxisAttr().Set("Z")
    UsdGeom.Xformable(c).AddTranslateOp().Set(Gf.Vec3d(tx, ty, tz))
    c.GetDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*color)]))
    return c


def _xform(stage, path):
    return UsdGeom.Xform.Define(stage, path)


def build():
    ctx = omni.usd.get_context()
    ctx.new_stage()
    stage = ctx.get_stage()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    world = _xform(stage, "/World")
    stage.SetDefaultPrim(world.GetPrim())

    # lighting
    dome = UsdLux.DomeLight.Define(stage, "/World/DomeLight"); dome.GetIntensityAttr().Set(800)
    sun = UsdLux.DistantLight.Define(stage, "/World/Sun"); sun.GetIntensityAttr().Set(2500)
    UsdGeom.Xformable(sun).AddRotateXYZOp().Set(Gf.Vec3f(315, 0, 25))

    # ground
    _box(stage, "/World/Ground", 3.0, 3.0, 0.02, 0, 0, -0.01, (0.16, 0.17, 0.19))

    vgr = _xform(stage, "/World/VGR")

    # static base plate
    _cyl(stage, "/World/VGR/Base", 0.20, 0.05, 0, 0, 0.025, (0.75, 0.23, 0.17))

    # ROTATE group (about Z), pivot at origin
    rot = _xform(stage, "/World/VGR/Rotate")
    rotop = UsdGeom.Xformable(rot).AddRotateZOp(); rotop.Set(0.0)
    _box(stage, "/World/VGR/Rotate/column", 0.10, 0.10, COLUMN_H, 0, 0, 0.05 + COLUMN_H / 2, (0.60, 0.64, 0.70))

    # VERTICAL group (slides down Z)
    vert = _xform(stage, "/World/VGR/Rotate/Vertical")
    vop = UsdGeom.Xformable(vert).AddTranslateOp(); vop.Set(Gf.Vec3d(0, 0, 0))
    carriage_z = 0.05 + COLUMN_H  # starts at the top of the column
    _box(stage, "/World/VGR/Rotate/Vertical/carriage", 0.18, 0.18, 0.12, 0, 0, carriage_z, (0.90, 0.30, 0.24))

    # HORIZONTAL group (extends along X)
    hor = _xform(stage, "/World/VGR/Rotate/Vertical/Horizontal")
    hop = UsdGeom.Xformable(hor).AddTranslateOp(); hop.Set(Gf.Vec3d(0, 0, 0))
    _box(stage, "/World/VGR/Rotate/Vertical/Horizontal/arm", 0.30, 0.10, 0.10,
         0.15 + ARM_BASE / 2, 0, carriage_z, (0.60, 0.64, 0.70))
    tip_x = 0.30 + ARM_BASE
    _box(stage, "/World/VGR/Rotate/Vertical/Horizontal/head", 0.12, 0.12, 0.12,
         tip_x, 0, carriage_z, (0.20, 0.55, 0.86))
    _cyl(stage, "/World/VGR/Rotate/Vertical/Horizontal/suction", 0.045, 0.10,
         tip_x, 0, carriage_z - 0.11, (0.95, 0.95, 0.95))

    # framed camera
    cam = UsdGeom.Camera.Define(stage, "/World/TwinCam")
    view = Gf.Matrix4d().SetLookAt(Gf.Vec3d(1.5, -1.6, 1.1), Gf.Vec3d(0, 0, 0.45), Gf.Vec3d(0, 0, 1))
    UsdGeom.Xformable(cam).AddTransformOp().Set(view.GetInverse())

    _C["rot"], _C["vert"], _C["hor"] = rotop, vop, hop
    stage.GetRootLayer().Export(STAGE)
    return stage


def _ops():
    if _C:
        return _C["rot"], _C["vert"], _C["hor"]
    stage = omni.usd.get_context().get_stage()
    rot = UsdGeom.Xformable(stage.GetPrimAtPath("/World/VGR/Rotate")).GetOrderedXformOps()[0]
    vert = UsdGeom.Xformable(stage.GetPrimAtPath("/World/VGR/Rotate/Vertical")).GetOrderedXformOps()[0]
    hor = UsdGeom.Xformable(stage.GetPrimAtPath("/World/VGR/Rotate/Vertical/Horizontal")).GetOrderedXformOps()[0]
    return rot, vert, hor


def set_pose(rotate_ct, vertical_ct, horizontal_ct):
    rot, vert, hor = _ops()
    deg = ROT_SIGN * (float(rotate_ct) / ROT_270) * 270.0 + ROT_OFFSET_DEG
    drop = (float(vertical_ct) / VERT_MAX) * VERT_TRAVEL
    ext = (float(horizontal_ct) / HORIZ_MAX) * HORIZ_TRAVEL
    rot.Set(deg)
    vert.Set(Gf.Vec3d(0, 0, -drop))
    hor.Set(Gf.Vec3d(ext, 0, 0))
    return {"deg": round(deg, 1), "drop_m": round(drop, 3), "ext_m": round(ext, 3)}


build()
print("Built VGR twin ->", STAGE)
print("home pose:", set_pose(0, 0, 0))
