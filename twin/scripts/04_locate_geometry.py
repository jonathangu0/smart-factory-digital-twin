"""Find where the CAD geometry actually is in world space + which camera is active."""
import omni.usd
from pxr import Usd, UsdGeom, Gf


def main():
    ctx = omni.usd.get_context()
    stage = ctx.get_stage()

    # active viewport camera
    try:
        from omni.kit.viewport.utility import get_active_viewport
        vp = get_active_viewport()
        cam_path = str(vp.get_active_camera())
    except Exception as e:
        cam_path = f"(err {e})"
    print("ACTIVE CAMERA:", cam_path)
    cam_prim = stage.GetPrimAtPath(cam_path) if cam_path.startswith("/") else None
    if cam_prim and cam_prim.IsValid():
        xc = UsdGeom.XformCache()
        t = xc.GetLocalToWorldTransform(cam_prim).ExtractTranslation()
        print("  camera world pos:", [round(v, 1) for v in t])

    # whole-model world bbox (fresh)
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)
    rng = bc.ComputeWorldBound(stage.GetPrimAtPath("/vgr")).ComputeAlignedRange()
    print("WHOLE /vgr world bbox:", [round(v, 1) for v in rng.GetMin()],
          [round(v, 1) for v in rng.GetMax()])

    # per-mesh: world bbox of first few real meshes (instance proxies)
    it = Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies())
    meshes = [p for p in it if p.GetTypeName() == "Mesh"]
    print("mesh count:", len(meshes))
    for m in meshes[:4]:
        wb = bc.ComputeWorldBound(m).ComputeAlignedRange()
        vis = UsdGeom.Imageable(m).ComputeVisibility()
        print(" ", m.GetPath(), "vis=", vis,
              "wbbox=", [round(v, 1) for v in wb.GetMin()], [round(v, 1) for v in wb.GetMax()])

    # is /vgr itself visible, and does it have a scale?
    vgr = stage.GetPrimAtPath("/vgr")
    print("/vgr visibility:", UsdGeom.Imageable(vgr).ComputeVisibility())
    xc2 = UsdGeom.XformCache()
    m = xc2.GetLocalToWorldTransform(vgr)
    print("/vgr world xform translation:", [round(v, 1) for v in m.ExtractTranslation()])


main()
