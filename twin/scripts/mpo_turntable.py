"""MPO turntable: rotate the drehkranz disc (NAUO1016) AND the vacuum-gripper
assembly mounted on it, about the turntable's vertical axis, in WORLD space.
Auto-selects the mounted parts by radius so nothing else moves. Shows clear
activity: indexes back-and-forth while State_MPO is active; holds at 0 when idle.
Force with builtins._mpo_test_angle (deg); None = live."""
import omni.usd
import omni.kit.app
import builtins
import math
from pxr import Usd, UsdGeom, Gf

MPO = "/World/TrainingFactory/World/Factory/Assembly/Part_5/NAUO10"
PIVOT = Gf.Vec3d(0.241, 0.172, 0.0)
DISC = "NAUO1016"
RAD, ZLO, ZHI = 0.052, 0.064, 0.140
INDEX_MAX = 120.0   # turntable indexes ~120 deg between stations
SPEED = 55.0        # deg/sec while active


def main():
    stage = omni.usd.get_context().get_stage()
    stage.SetEditTarget(stage.GetRootLayer())
    mpo = stage.GetPrimAtPath(MPO)
    Pp = UsdGeom.XformCache().GetLocalToWorldTransform(mpo)
    Pinv = Pp.GetInverse()
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)

    names = [DISC]
    for c in mpo.GetAllChildren():
        r = bc.ComputeWorldBound(c).ComputeAlignedRange()
        a, b = r.GetMin(), r.GetMax()
        cx, cy, cz = (a[0]+b[0])/2, (a[1]+b[1])/2, (a[2]+b[2])/2
        d = ((cx-PIVOT[0])**2 + (cy-PIVOT[1])**2)**0.5
        if c.GetName() != DISC and d <= RAD and ZLO <= cz <= ZHI:
            names.append(c.GetName())

    home = {}
    for name in names:
        c = stage.GetPrimAtPath(f"{MPO}/{name}")
        if not (c and c.IsValid()):
            continue
        xf = UsdGeom.Xformable(c)
        L0 = xf.GetLocalTransformation()
        xf.ClearXformOpOrder()
        xf.AddTransformOp().Set(L0)
        home[name] = (xf, L0)
    print("turntable parts:", len(home))

    def apply(angle):
        Rz = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), angle))
        Dw = Gf.Matrix4d().SetTranslate(-PIVOT) * Rz * Gf.Matrix4d().SetTranslate(PIVOT)
        inner = Pp * Dw * Pinv
        for xf, L0 in home.values():
            xf.GetOrderedXformOps()[0].Set(L0 * inner)

    builtins._mpo_apply = apply
    builtins._mpo_accum = getattr(builtins, "_mpo_accum", 0.0)

    def _update(e):
        ta = getattr(builtins, "_mpo_test_angle", None)
        if ta is not None:
            apply(ta); return
        st = getattr(builtins, "_factory_state", {}) or {}
        active = bool(st.get("act_MPO"))
        dt = 1.0 / 60.0
        try:
            dt = float(e.payload.get("dt", dt)) or dt
        except Exception:
            pass
        acc = builtins._mpo_accum
        if active:
            acc += SPEED * dt
        else:
            acc = 0.0
        builtins._mpo_accum = acc
        # triangle wave 0..INDEX_MAX..0 for indexing look
        phase = acc % (2 * INDEX_MAX)
        angle = phase if phase <= INDEX_MAX else (2 * INDEX_MAX - phase)
        apply(angle)

    builtins._mpo_sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
        _update, name="mpo_turntable")
    print("MPO turntable driver running (disc + mounted gripper)")


main()
