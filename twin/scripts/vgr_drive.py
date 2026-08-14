"""
vgr_drive.py — pose the imported VGR to mirror the real robot's axis counts.

The CAD model is millimeters and Y-up. The three named sub-assemblies:
  Turm                -> rotates about the vertical (Y) axis through the tower
  querausleger        -> the horizontal boom: rotates + drops (vertical)
  querausleger_sauger -> the gripper: rotates + drops + extends (horizontal)

set_pose() maps raw OPC-UA pulse counts -> transforms using the calibration
from the smart-factory repo. Rest (home) transforms are cached in builtins so
repeated calls compose from home rather than accumulating.

All the * _SIGN / * _MM / PIVOT constants are meant to be tuned against the real
robot on screen — adjust and re-run until motion matches.
"""
import builtins
import omni.usd
from pxr import Usd, UsdGeom, Gf

VGR_USD = r"C:/Users/icets/Downloads/digitaltwinsf/twin/usd/vgr.usd"

# --- prim paths of the three moving sub-assemblies ---
P_TURM = "/vgr/vgr/Turm"
P_ARM  = "/vgr/vgr/querausleger"
P_GRIP = "/vgr/vgr/querausleger_sauger"

# --- calibration (pulse counts at the travel extremes) ---
ROT_270   = 5331     # counts for 270 deg of rotation (0 = South, CCW)
VERT_MAX  = 2993     # counts at the lowest arm position
HORIZ_MAX = 3377     # counts at full horizontal extension

# --- geometry mapping (millimeters; tune to the model) ---
PIVOT   = Gf.Vec3d(33.4, 0.0, 255.2)  # tower vertical axis (X, _, Z) in /vgr/vgr space
VERT_MM  = 150.0     # physical vertical travel over VERT_MAX counts
HORIZ_MM = 200.0     # physical horizontal travel over HORIZ_MAX counts
ROT_SIGN  = +1.0     # flip if rotation goes the wrong way
VERT_SIGN = +1.0     # +1 => larger count drops the arm (-Y)
HORIZ_SIGN = +1.0    # +1 => larger count extends along +X


def _stage():
    ctx = omni.usd.get_context()
    stage = ctx.get_stage()
    ident = stage.GetRootLayer().identifier if stage else ""
    if stage is None or "vgr.usd" not in (ident or ""):
        ctx.open_stage(VGR_USD)
        stage = ctx.get_stage()
    return stage


def _rest(prim):
    if not hasattr(builtins, "_vgr_rest"):
        builtins._vgr_rest = {}
    key = str(prim.GetPath())
    if key not in builtins._vgr_rest:
        builtins._vgr_rest[key] = UsdGeom.Xformable(prim).GetLocalTransformation()
    return builtins._vgr_rest[key]


def _set_local(prim, matrix):
    xf = UsdGeom.Xformable(prim)
    xf.ClearXformOpOrder()
    xf.AddTransformOp().Set(matrix)


def _rot_about_pivot(angle_deg):
    rm = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0, 1, 0), angle_deg))
    t_in = Gf.Matrix4d().SetTranslate(Gf.Vec3d(-PIVOT[0], 0, -PIVOT[2]))
    t_out = Gf.Matrix4d().SetTranslate(Gf.Vec3d(PIVOT[0], 0, PIVOT[2]))
    return t_in * rm * t_out


def set_pose(rotate_ct, vertical_ct, horizontal_ct):
    """Pose the VGR from raw OPC-UA axis counts. Returns the computed angles/mm."""
    stage = _stage()
    turm = stage.GetPrimAtPath(P_TURM)
    arm = stage.GetPrimAtPath(P_ARM)
    grip = stage.GetPrimAtPath(P_GRIP)

    angle = ROT_SIGN * (float(rotate_ct) / ROT_270) * 270.0
    dy = -VERT_SIGN * (float(vertical_ct) / VERT_MAX) * VERT_MM
    dx = HORIZ_SIGN * (float(horizontal_ct) / HORIZ_MAX) * HORIZ_MM

    m_rot = _rot_about_pivot(angle)
    t_vert = Gf.Matrix4d().SetTranslate(Gf.Vec3d(0, dy, 0))
    t_horiz = Gf.Matrix4d().SetTranslate(Gf.Vec3d(dx, 0, 0))

    # new_local = rest * Delta   (row-vector convention: p' = p_group * rest * Delta)
    _set_local(turm, _rest(turm) * m_rot)
    _set_local(arm,  _rest(arm)  * (t_vert * m_rot))
    _set_local(grip, _rest(grip) * (t_horiz * t_vert * m_rot))
    return {"angle_deg": round(angle, 1), "drop_mm": round(dy, 1), "extend_mm": round(dx, 1)}


def home():
    return set_pose(0, 0, 0)


# When run via execute_python_file, apply a clearly-visible demo pose:
#   rotate ~90 deg East, arm ~half down, ~half extended.
_demo = set_pose(1736, 1500, 1800)
print("VGR demo pose applied:", _demo)
print("Pivot:", tuple(PIVOT), "| VERT_MM:", VERT_MM, "| HORIZ_MM:", HORIZ_MM)
