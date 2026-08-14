"""Locate every camera gizmo mesh + find the setting that shows them."""
import omni.usd
import carb
from pxr import Usd, UsdGeom, Gf


def main():
    ctx = omni.usd.get_context()
    stage = ctx.get_stage()
    xc = UsdGeom.XformCache()

    print("=== CameraModel / gizmo meshes ===")
    for p in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()):
        nm = p.GetName()
        if "CameraModel" in nm or "OmniverseKitViewportCameraMesh" in nm:
            t = xc.GetLocalToWorldTransform(p).ExtractTranslation()
            vis = UsdGeom.Imageable(p).ComputeVisibility() if p.IsA(UsdGeom.Imageable) else "?"
            print(f"  {p.GetPath()}  active={p.IsActive()} vis={vis} pos={[round(v,2) for v in t]}")

    print("\n=== all Camera prims: active + pos ===")
    for p in stage.Traverse():
        if p.GetTypeName() == "Camera":
            t = xc.GetLocalToWorldTransform(p).ExtractTranslation()
            print(f"  {p.GetPath()}  active={p.IsActive()} pos={[round(v,2) for v in t]}")

    print("\n=== carb settings mentioning camera/gizmo/show ===")
    s = carb.settings.get_settings()
    for key in [
        "/app/viewport/show/camera",
        "/persistent/app/viewport/displayOptions",
        "/app/viewport/grid/enabled",
        "/persistent/app/viewport/camShowVisual",
        "/persistent/app/viewport/Viewport/Viewport0/scene/cameras/visible",
    ]:
        try:
            print(f"  {key} = {s.get(key)}")
        except Exception as e:
            print(f"  {key} -> {e}")


main()
