"""A workpiece puck that rides with the VGR gripper suction point. Reads
builtins._vgr_grip_pos (published by the VGR driver). Held whenever
builtins._vgr_holding is True (default True)."""
import omni.usd
import omni.kit.app
import builtins
from pxr import UsdGeom, Gf, Vt


def main():
    stage = omni.usd.get_context().get_stage()
    stage.SetEditTarget(stage.GetSessionLayer())  # runtime edits only; never bakes into the scene file
    builtins._vgr_holding = getattr(builtins, "_vgr_holding", True)

    p = UsdGeom.Cylinder.Define(stage, "/World/VGR_Workpiece")
    p.GetRadiusAttr().Set(0.013)
    p.GetHeightAttr().Set(0.008)
    p.GetAxisAttr().Set("Z")  # flat puck
    p.GetDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(0.1, 0.4, 0.9)]))
    xf = UsdGeom.Xformable(p)
    xf.ClearXformOpOrder()
    top = xf.AddTranslateOp()
    top.Set(Gf.Vec3d(0.153, -0.214, 0.176))
    prim = p.GetPrim()

    def _update(_e):
        pos = getattr(builtins, "_vgr_grip_pos", None)
        hold = getattr(builtins, "_vgr_holding", True)
        UsdGeom.Imageable(prim).MakeVisible() if hold else UsdGeom.Imageable(prim).MakeInvisible()
        if pos is not None and hold:
            top.Set(Gf.Vec3d(pos[0], pos[1], pos[2]))

    builtins._vgr_wp_sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
        _update, name="vgr_workpiece")
    print("VGR workpiece riding the gripper")


main()
