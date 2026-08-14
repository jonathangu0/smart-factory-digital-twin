"""Hide camera gizmos, frame the factory (excluding gizmo meshes), capture."""
import os
import omni.usd
import carb
from pxr import Usd, UsdGeom, Gf

SHOT = r"C:/Users/icets/Downloads/digitaltwinsf/twin/shots/factory_final.png"


def main():
    # hide all camera model gizmos in the viewport
    s = carb.settings.get_settings()
    for key in ("/app/viewport/show/camera",
                "/persistent/app/viewport/Viewport/Viewport0/scene/cameras/visible"):
        try:
            s.set(key, False)
        except Exception:
            pass

    stage = omni.usd.get_context().get_stage()
    bc = UsdGeom.BBoxCache(Usd.TimeCode.Default(),
                           [UsdGeom.Tokens.default_, UsdGeom.Tokens.render], useExtentsHint=True)
    rng = Gf.Range3d()
    for p in Usd.PrimRange.Stage(stage, Usd.TraverseInstanceProxies()):
        if p.GetTypeName() != "Mesh":
            continue
        pathstr = p.GetPath().pathString
        if "CameraModel" in pathstr or "ViewportCameraMesh" in pathstr:
            continue  # exclude camera gizmos from framing
        rng.UnionWith(bc.ComputeWorldBound(p).ComputeAlignedRange())
    mn, mx = rng.GetMin(), rng.GetMax()
    C = Gf.Vec3d((mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2)
    d = max(mx[i] - mn[i] for i in range(3))
    print("factory bbox (no gizmos): center", [round(v, 2) for v in C], "d", round(d, 2))

    cam = UsdGeom.Camera.Define(stage, "/World/OverviewCam")
    eye = C + Gf.Vec3d(d * 1.7, -d * 1.9, d * 1.2)
    view = Gf.Matrix4d().SetLookAt(eye, C, Gf.Vec3d(0, 0, 1))
    cx = UsdGeom.Xformable(cam); cx.ClearXformOpOrder()
    cx.AddTransformOp().Set(view.GetInverse())
    cam.GetFocalLengthAttr().Set(28.0)

    from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
    vp = get_active_viewport()
    vp.set_active_camera("/World/OverviewCam")
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    capture_viewport_to_file(vp, SHOT)
    print("shot ->", SHOT)


main()
