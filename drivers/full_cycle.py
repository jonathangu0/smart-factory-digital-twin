"""Full ORDER cycle animation: one product travels HBW, VGR, MPO, VGR, SLD, VGR,
DPS, handed off between machines (following each machine's published tool
position). Reference: fischertechnik Training Factory order flow. Drives the
VGR/HBW/MPO poses in sync. Run after the station drivers (00-05). Toggle with
builtins._fullcycle; disables the demo automatically."""
import omni.usd
import omni.kit.app
import builtins
from pxr import UsdGeom, Gf, Vt

T = 64.0  # full cycle length (seconds)

# VGR rotation counts to face each station (0..5331 == 0..270 deg; arm home = -Y)
FACE_HBW, FACE_MPO, FACE_SLD, FACE_DPS = 5100, 3300, 1950, 700

# station rest positions (world metres)
BAY = Gf.Vec3d(-0.239, 0.112, 0.180)
MPO_POS = Gf.Vec3d(0.241, 0.172, 0.105)
SLD_START = Gf.Vec3d(0.346, 0.050, 0.078)
SLD_BIN = Gf.Vec3d(0.435, -0.233, 0.078)
DPS_POS = Gf.Vec3d(0.010, -0.315, 0.055)


def key(t, f):
    if t <= f[0][0]:
        return f[0][1]
    for i in range(1, len(f)):
        if t <= f[i][0]:
            t0, v0 = f[i-1]; t1, v1 = f[i]
            a = (t - t0) / (t1 - t0)
            return v0 + (v1 - v0) * a
    return f[-1][1]


VGR_ROT = [(0, 0), (11, 0), (15, FACE_HBW), (16, FACE_HBW), (22, FACE_MPO), (24, FACE_MPO),
           (34, FACE_MPO), (36, FACE_MPO), (42, FACE_SLD), (43, FACE_SLD), (50, FACE_SLD),
           (53, FACE_SLD), (58, FACE_DPS), (60, FACE_DPS), (64, FACE_DPS)]
VGR_VER = [(0, 0), (13, 0), (15, 1800), (16, 1800), (18, 400), (21, 400), (23, 1800), (24, 1800),
           (26, 400), (34, 400), (36, 1800), (37, 1800), (39, 400), (48, 400), (50, 1800),
           (53, 1800), (55, 400), (57, 400), (59, 1600), (60, 1600), (62, 400), (64, 0)]
VGR_HOR = [(0, 0), (13, 0), (15, 3000), (16, 3000), (18, 800), (21, 800), (23, 3000), (24, 3000),
           (26, 800), (34, 800), (36, 3000), (37, 3000), (39, 800), (48, 800), (50, 3000),
           (53, 3000), (55, 800), (57, 800), (59, 2600), (60, 2600), (64, 0)]
FORK_Y = [(0, -0.12), (3, 0.112), (6, 0.112), (9, -0.12), (15, -0.12), (64, -0.12)]
FORK_Z = [(0, 0.150), (3, 0.180), (6, 0.180), (9, 0.150), (64, 0.150)]
MPO_ANG = [(0, 0), (24, 0), (28, 110), (32, 0), (64, 0)]


def main():
    builtins._fullcycle = True
    builtins._demo_mode = False           # full cycle takes over from the demo
    builtins._demo_force = False
    builtins._vgr_holding = False          # master product replaces per-machine pucks
    builtins._hbw_carry = False
    builtins._fc_t = getattr(builtins, "_fc_t", 0.0)

    stage = omni.usd.get_context().get_stage()
    stage.SetEditTarget(stage.GetSessionLayer())  # runtime edits only; never bakes into the scene file
    p = UsdGeom.Cylinder.Define(stage, "/World/Product")
    p.GetRadiusAttr().Set(0.013)
    p.GetHeightAttr().Set(0.009)
    p.GetAxisAttr().Set("Z")
    p.GetDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(0.95, 0.55, 0.05)]))  # orange product
    xf = UsdGeom.Xformable(p); xf.ClearXformOpOrder()
    top = xf.AddTranslateOp(); top.Set(BAY)

    def _grip():
        gp = getattr(builtins, "_vgr_grip_pos", None)
        return Gf.Vec3d(gp[0], gp[1], gp[2]) if gp else DPS_POS

    def product_pos(t):
        if t < 6:            # sitting in the rack bay
            return BAY
        if t < 15:           # on the HBW fork (bay -> output)
            fp = getattr(builtins, "_hbw_fork_pos", None)
            return Gf.Vec3d(fp[0] + 0.055, fp[1], fp[2] + 0.02) if fp else BAY
        if t < 23:           # on VGR gripper (HBW -> MPO)
            return _grip()
        if t < 35:           # processed at the MPO turntable
            return MPO_POS
        if t < 43:           # on VGR gripper (MPO -> SLD)
            return _grip()
        if t < 48:           # travelling the SLD belt
            a = (t - 43) / 5.0
            return Gf.Vec3d(SLD_START[0], SLD_START[1] + a * (SLD_BIN[1] - SLD_START[1]), SLD_START[2])
        if t < 50:           # ejected into the colour bin
            a = (t - 48) / 2.0
            return Gf.Vec3d(SLD_START[0] + a * (SLD_BIN[0] - SLD_START[0]), SLD_BIN[1], SLD_BIN[2])
        if t < 60:           # on VGR gripper (SLD -> DPS)
            return _grip()
        return DPS_POS       # delivered

    def _update(e):
        if not getattr(builtins, "_fullcycle", False):
            return
        dt = 1.0 / 60.0
        try:
            dt = float(e.payload.get("dt", dt)) or dt
        except Exception:
            pass
        if dt > 0.05:
            dt = 0.05
        t = (builtins._fc_t + dt) % T
        builtins._fc_t = t
        builtins._vgr_test_pose = (key(t, VGR_ROT), key(t, VGR_VER), key(t, VGR_HOR))
        builtins._hbw_fork_target = (key(t, FORK_Y), key(t, FORK_Z))
        builtins._mpo_test_angle = key(t, MPO_ANG)
        top.Set(product_pos(t))

    builtins._fc_sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
        _update, name="full_cycle")
    print("FULL CYCLE animation running (HBW->VGR->MPO->SLD->VGR->DPS)")


main()
