"""SLD sorting line: a workpiece rides the belt (along -Y) while the line is
active, then is ejected sideways (+X) into its color bin at the matching
station. Ejection color comes from the LIVE flags sld_blue/white/red.
Belt = NAUO2105 (long in Y). 3 stations at Y=-0.173/-0.233/-0.293.
Per TxtSortingLine: convBelt + eject White/Red/Blue."""
import omni.usd
import omni.kit.app
import builtins
from pxr import UsdGeom, Gf, Vt

SLD = "/World/TrainingFactory/World/Factory/Assembly/Part_5/NAUO6"
BELT_X = 0.346
BELT_Z = 0.074
Y_IN = 0.050          # infeed (from MPO conveyor)
Y_END = -0.320        # belt end
BIN_X = 0.435         # ejected into bin (+X off the belt)
SPEED = 0.11          # m/s belt travel
# color -> ejection station Y (order along the belt)
STATION = {"white": -0.173, "red": -0.233, "blue": -0.293}
COLOR_RGB = {"white": (0.92, 0.92, 0.92), "red": (0.85, 0.2, 0.15), "blue": (0.1, 0.4, 0.9)}


def main():
    stage = omni.usd.get_context().get_stage()
    stage.SetEditTarget(stage.GetRootLayer())

    # three color bin markers at the stations so the sort target is visible
    UsdGeom.Xform.Define(stage, "/World/SLD_Bins")
    for col, y in STATION.items():
        b = UsdGeom.Cylinder.Define(stage, f"/World/SLD_Bins/bin_{col}")
        b.GetRadiusAttr().Set(0.016)
        b.GetHeightAttr().Set(0.004)
        b.GetAxisAttr().Set("Z")
        b.GetDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(*COLOR_RGB[col])]))
        xb = UsdGeom.Xformable(b); xb.ClearXformOpOrder()
        xb.AddTranslateOp().Set(Gf.Vec3d(BIN_X, y, BELT_Z - 0.002))

    # the traveling workpiece
    p = UsdGeom.Cylinder.Define(stage, "/World/SLD_Workpiece")
    p.GetRadiusAttr().Set(0.013)
    p.GetHeightAttr().Set(0.008)
    p.GetAxisAttr().Set("Z")
    p.GetDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(0.6, 0.6, 0.6)]))
    xf = UsdGeom.Xformable(p); xf.ClearXformOpOrder()
    top = xf.AddTranslateOp(); top.Set(Gf.Vec3d(BELT_X, Y_IN, BELT_Z))
    cattr = p.GetDisplayColorAttr()
    prim = p.GetPrim()

    st_local = {"y": Y_IN, "color": None, "run": False}

    def _update(e):
        st = getattr(builtins, "_factory_state", {}) or {}
        active = bool(st.get("act_SLD"))
        dt = 1.0 / 60.0
        try:
            dt = float(e.payload.get("dt", dt)) or dt
        except Exception:
            pass
        # pick/latch color when a fresh run starts
        if active and not st_local["run"]:
            st_local["run"] = True
            st_local["y"] = Y_IN
            col = "white" if st.get("sld_white") else "red" if st.get("sld_red") else "blue" if st.get("sld_blue") else "white"
            st_local["color"] = col
            cattr.Set(Vt.Vec3fArray([Gf.Vec3f(*COLOR_RGB[col])]))
        if not active:
            st_local["run"] = False

        col = st_local["color"] or "white"
        ey = STATION[col]
        if st_local["run"]:
            UsdGeom.Imageable(prim).MakeVisible()
            if st_local["y"] > ey:                       # travel down the belt
                st_local["y"] = max(ey, st_local["y"] - SPEED * dt)
                top.Set(Gf.Vec3d(BELT_X, st_local["y"], BELT_Z))
            else:                                         # at station -> eject +X into bin
                cur = top.Get()
                nx = min(BIN_X, cur[0] + SPEED * dt)
                top.Set(Gf.Vec3d(nx, ey, BELT_Z))
        else:
            UsdGeom.Imageable(prim).MakeInvisible()
            st_local["y"] = Y_IN
            top.Set(Gf.Vec3d(BELT_X, Y_IN, BELT_Z))

    builtins._sld_sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
        _update, name="sld_sort")
    print("SLD sorting line driver running (belt travel + color eject)")


main()
