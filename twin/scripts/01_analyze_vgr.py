# Analyze the converted VGR USD: units, scale, key link transforms, motor positions.
# Motor (encodermotor) world positions mark where each axis/joint lives.
import omni.usd
from pxr import Usd, UsdGeom, Gf

VGR = r"C:/Users/icets/Downloads/digitaltwinsf/twin/usd/vgr.usd"

ctx = omni.usd.get_context()
stage = ctx.get_stage()
ident = stage.GetRootLayer().identifier if stage else ""
if stage is None or "vgr.usd" not in (ident or ""):
    ctx.open_stage(VGR)
    stage = ctx.get_stage()

xcache = UsdGeom.XformCache(Usd.TimeCode.Default())
bcache = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render],
                           useExtentsHint=True)


def world_pos(path):
    p = stage.GetPrimAtPath(path)
    if not p or not p.IsValid():
        return None
    t = xcache.GetLocalToWorldTransform(p).ExtractTranslation()
    return [round(t[0], 2), round(t[1], 2), round(t[2], 2)]


def world_bbox(path):
    p = stage.GetPrimAtPath(path)
    if not p or not p.IsValid():
        return None
    rng = bcache.ComputeWorldBound(p).ComputeAlignedRange()
    if rng.IsEmpty():
        return "empty"
    mn, mx = rng.GetMin(), rng.GetMax()
    dims = [round(mx[i] - mn[i], 2) for i in range(3)]
    return {"min": [round(mn[i], 2) for i in range(3)],
            "max": [round(mx[i], 2) for i in range(3)],
            "dims": dims}


print("UP_AXIS:", UsdGeom.GetStageUpAxis(stage),
      "| METERS_PER_UNIT:", UsdGeom.GetStageMetersPerUnit(stage))
print("WHOLE_VGR_BBOX:", world_bbox("/vgr/vgr"))

targets = {
    "Turm": "/vgr/vgr/Turm",
    "Turm_motor_135484": "/vgr/vgr/Turm/tn__135484_encodermotor_",
    "root_motor_135484": "/vgr/vgr/tn__135484_encodermotor_",
    "querausleger": "/vgr/vgr/querausleger",
    "querausleger_motor_153422": "/vgr/vgr/querausleger/tn__153422_encodermotor_",
    "querausleger_sauger": "/vgr/vgr/querausleger_sauger",
    "sauger": "/vgr/vgr/querausleger_sauger/sauger",
}
for name, path in targets.items():
    print(f"{name}:")
    print("   pos ", world_pos(path))
    print("   bbox", world_bbox(path))

root = stage.GetPrimAtPath("/vgr/vgr")
kids = [c.GetName() for c in root.GetChildren()] if root and root.IsValid() else []
print("TOP_LEVEL_CHILD_COUNT:", len(kids))
print("TOP_LEVEL_CHILDREN:", kids)
