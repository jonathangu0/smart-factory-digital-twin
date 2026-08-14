"""VGR live rotation on the clean scene: cache home transforms of the mast/arm
parts and drive their rotation from the real OPC-UA rotate count every frame."""
import omni.usd
import omni.kit.app
import builtins
from pxr import Usd, UsdGeom, Gf

ROOT = "/World/TrainingFactory/World/Factory/Assembly/Part_5"
VGR = ROOT + "/NAUO2"
PIVOT = Gf.Vec3d(0.05, -0.17, 0.0)
Z_ROTATE = 0.055
ROT_270 = 5331
ROT_SIGN = 1.0


def _inner(angle_deg, Pp):
    Rz = Gf.Matrix4d().SetRotate(Gf.Rotation(Gf.Vec3d(0, 0, 1), angle_deg))
    d = Gf.Matrix4d().SetTranslate(-PIVOT) * Rz * Gf.Matrix4d().SetTranslate(PIVOT)
    return Pp * d * Pp.GetInverse()


def main():
    stage = omni.usd.get_context().get_stage()
    stage.SetEditTarget(stage.GetRootLayer())
    vgr = stage.GetPrimAtPath(VGR)
    xc = UsdGeom.XformCache()
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)
    Pp = xc.GetLocalToWorldTransform(vgr)

    home = {}
    for c in vgr.GetChildren():
        r = bc.ComputeWorldBound(c).ComputeAlignedRange()
        if r.IsEmpty():
            continue
        zc = (r.GetMin()[2] + r.GetMax()[2]) / 2
        if zc >= Z_ROTATE:
            xf = UsdGeom.Xformable(c)
            L0 = xf.GetLocalTransformation()
            xf.ClearXformOpOrder()
            xf.AddTransformOp().Set(L0)
            home[c.GetPath().pathString] = (xf, L0)
    print("VGR live rotation: driving", len(home), "mast/arm parts")

    def _update(_e):
        st = getattr(builtins, "_factory_state", {}) or {}
        count = st.get("vgr_rot") or 0
        inner = _inner(ROT_SIGN * (count / ROT_270) * 270.0, Pp)
        for _p, (xf, L0) in home.items():
            xf.GetOrderedXformOps()[0].Set(L0 * inner)

    builtins._vgr_artic_sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
        _update, name="vgr_live_artic2")
    print("VGR now rotates live with the real robot.")


main()
