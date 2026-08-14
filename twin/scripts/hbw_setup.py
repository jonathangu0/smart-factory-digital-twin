"""HBW stacker crane: moves along the rack (WORLD Y) and the fork lifts (WORLD Z),
computed in WORLD space. 9 flat pucks in the rack. Adds precise fork-position
control (put the fork exactly at a bay or the VGR transfer point) and a workpiece
that rides the fork so you can watch it carried from the bay to the VGR meeting
point. Live OPC-UA still drives it via hor/ver counts."""
import omni.usd
import omni.kit.app
import builtins
from pxr import UsdGeom, Gf, Vt

HBW = "/World/TrainingFactory/World/Factory/Assembly/Part_5/NAUO11"
CRANE = ["NAUO47", "NAUO48", "NAUO49"]   # mast + fork carriage + fork arm
FORK = ["NAUO48", "NAUO49"]              # lifts vertically on the mast

# rack bays (flat pucks)
SLOT_X = -0.239
SLOT_Y = [0.112, 0.022, -0.068]
SLOT_Z = [0.120, 0.180, 0.234]
COLORS = [(0.1, 0.4, 0.9), (0.85, 0.2, 0.15), (0.92, 0.92, 0.92)]

# fork reference (NAUO49) home pose -> used for precise positioning
FORK_HOME = Gf.Vec3d(-0.310, 0.110, 0.229)
CARRY_OFFSET = Gf.Vec3d(0.055, 0.0, 0.006)   # puck sits on the tines, toward the rack

HBW_H_MAX, HBW_V_MAX = 3250, 3250
Y_TRAVEL, Z_TRAVEL = 0.22, 0.11
H_SIGN, V_SIGN = 1.0, 1.0
# live OPC-UA counts sit ~+0.23 m in Y past the demo's range; shift them back so
# the live crane matches the demo. Tweak at runtime via builtins._hbw_h_offset.
H_OFFSET_Y = 0.23


def main():
    stage = omni.usd.get_context().get_stage()
    stage.SetEditTarget(stage.GetRootLayer())

    UsdGeom.Xform.Define(stage, "/World/HBW_Workpieces")
    for zi, z in enumerate(SLOT_Z):
        for yi, y in enumerate(SLOT_Y):
            p = UsdGeom.Cylinder.Define(stage, f"/World/HBW_Workpieces/wp_{zi}_{yi}")
            p.GetRadiusAttr().Set(0.013)
            p.GetHeightAttr().Set(0.008)
            p.GetAxisAttr().Set("Z")
            p.GetDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*COLORS[(zi + yi) % 3])]))
            xf = UsdGeom.Xformable(p); xf.ClearXformOpOrder()
            xf.AddTranslateOp().Set(Gf.Vec3d(SLOT_X, y, z))
    print("placed 9 flat workpieces")

    # workpiece carried on the fork
    carry = UsdGeom.Cylinder.Define(stage, "/World/HBW_Carry")
    carry.GetRadiusAttr().Set(0.013)
    carry.GetHeightAttr().Set(0.008)
    carry.GetAxisAttr().Set("Z")
    carry.GetDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(0.1, 0.4, 0.9)]))
    cxf = UsdGeom.Xformable(carry); cxf.ClearXformOpOrder()
    carry_top = cxf.AddTranslateOp(); carry_top.Set(FORK_HOME + CARRY_OFFSET)
    carry_prim = carry.GetPrim()

    hbw = stage.GetPrimAtPath(HBW)
    Pp = UsdGeom.XformCache().GetLocalToWorldTransform(hbw)

    def wdelta(V):
        return Pp * Gf.Matrix4d().SetTranslate(V) * Pp.GetInverse()

    home = {}
    for name in CRANE:
        c = stage.GetPrimAtPath(f"{HBW}/{name}")
        if not (c and c.IsValid()):
            print("missing", name); continue
        xf = UsdGeom.Xformable(c)
        L0 = xf.GetLocalTransformation()
        xf.ClearXformOpOrder()
        xf.AddTransformOp().Set(L0)
        home[name] = (xf, L0)

    def move(yt, zt):
        for name, (xf, L0) in home.items():
            V = Gf.Vec3d(0, yt, -zt) if name in FORK else Gf.Vec3d(0, yt, 0)
            xf.GetOrderedXformOps()[0].Set(L0 * wdelta(V))
        builtins._hbw_fork_pos = (FORK_HOME[0], FORK_HOME[1] + yt, FORK_HOME[2] - zt)

    def apply(hor, ver):  # OPC-UA counts -> shifted to match the demo's Y range
        off = getattr(builtins, "_hbw_h_offset", H_OFFSET_Y)
        move(H_SIGN * (hor / HBW_H_MAX) * Y_TRAVEL - off, V_SIGN * (ver / HBW_V_MAX) * Z_TRAVEL)

    def apply_pos(fy, fz):  # put the fork exactly at world (fy, fz)
        move(fy - FORK_HOME[1], FORK_HOME[2] - fz)

    builtins._hbw_apply = apply
    builtins._hbw_apply_pos = apply_pos

    def _update(_e):
        ft = getattr(builtins, "_hbw_fork_target", None)
        if ft is not None:
            apply_pos(*ft)
        else:
            tp = getattr(builtins, "_hbw_test_pose", None)
            if tp is not None:
                apply(*tp)
            else:
                st = getattr(builtins, "_factory_state", {}) or {}
                apply(st.get("hbw_hor") or 0, st.get("hbw_ver") or 0)
        # carried workpiece rides the fork
        carrying = bool(getattr(builtins, "_hbw_carry", False))
        UsdGeom.Imageable(carry_prim).MakeVisible() if carrying else UsdGeom.Imageable(carry_prim).MakeInvisible()
        if carrying:
            fp = getattr(builtins, "_hbw_fork_pos", None)
            if fp is not None:
                carry_top.Set(Gf.Vec3d(fp[0] + CARRY_OFFSET[0], fp[1] + CARRY_OFFSET[1], fp[2] + CARRY_OFFSET[2]))

    builtins._hbw_sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
        _update, name="hbw_crane")
    print("HBW crane driver running (fork-position + carried workpiece)")


main()
