"""Author a one-cycle production-flow animation on the factory timeline:
a workpiece puck travels the station sequence while a glowing beacon marks the
active station. Press Play (or the Run Cycle button) to run one cycle.

Station XY positions are best-guess on the baseplate (X[-0.47,0.47] Y[-0.38,0.38])
and are easy to tune -- edit STATIONS and re-run.
"""
import omni.usd
from pxr import Usd, UsdGeom, UsdLux, Gf, Vt, Sdf

FPS = 24
SEG = 60          # frames per station segment (2.5 s)
HOLD = 26         # dwell frames at each station
Z_PUCK = 0.07     # conveyor level (realistic)
Z_BEACON = 0.44   # floats clearly above the ~0.33 m tall factory

# name, x, y  -- the production flow of the Training Factory 4.0
STATIONS = [
    ("HBW_retrieve", -0.34, 0.20),
    ("HBW_output",   -0.18, 0.10),
    ("VGR_pick",      0.00, 0.06),
    ("MPO_process",   0.28, 0.18),
    ("VGR_move",      0.10, -0.05),
    ("SLD_sort",      0.26, -0.22),
    ("DSO_output",    0.00, -0.30),
    ("DSI_return",   -0.30, -0.15),
]


def main():
    ctx = omni.usd.get_context()
    stage = ctx.get_stage()

    twin = UsdGeom.Xform.Define(stage, "/World/Twin")

    # workpiece puck (fischertechnik round token ~24mm)
    puck = UsdGeom.Cylinder.Define(stage, "/World/Twin/Workpiece")
    puck.GetRadiusAttr().Set(0.012)
    puck.GetHeightAttr().Set(0.012)
    puck.GetAxisAttr().Set("Z")
    puck.GetDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(0.05, 0.35, 0.9)]))  # blue token
    _pf = UsdGeom.Xformable(puck); _pf.ClearXformOpOrder(); puck_t = _pf.AddTranslateOp()

    # visible beacon marker = bright sphere hovering over the active station
    marker = UsdGeom.Sphere.Define(stage, "/World/Twin/ActiveMarker")
    marker.GetRadiusAttr().Set(0.022)
    marker.GetDisplayColorAttr().Set(Vt.Vec3fArray([Gf.Vec3f(1.0, 0.85, 0.2)]))
    _mf = UsdGeom.Xformable(marker); _mf.ClearXformOpOrder(); marker_t = _mf.AddTranslateOp()

    # glowing beacon = a sphere light that hovers over the active station
    beacon = UsdLux.SphereLight.Define(stage, "/World/Twin/ActiveBeacon")
    beacon.GetRadiusAttr().Set(0.02)
    beacon.GetIntensityAttr().Set(30000)
    beacon.GetColorAttr().Set(Gf.Vec3f(1.0, 0.85, 0.3))
    _bf = UsdGeom.Xformable(beacon); _bf.ClearXformOpOrder(); beacon_t = _bf.AddTranslateOp()

    # keyframes: arrive at each station, dwell, move to next
    frame = 0
    for i, (name, x, y) in enumerate(STATIONS):
        pos_puck = Gf.Vec3d(x, y, Z_PUCK)
        pos_beacon = Gf.Vec3d(x, y, Z_BEACON)
        puck_t.Set(pos_puck, Usd.TimeCode(frame))
        marker_t.Set(pos_beacon, Usd.TimeCode(frame))
        beacon_t.Set(pos_beacon, Usd.TimeCode(frame))
        # dwell (hold position)
        puck_t.Set(pos_puck, Usd.TimeCode(frame + HOLD))
        marker_t.Set(pos_beacon, Usd.TimeCode(frame + HOLD))
        beacon_t.Set(pos_beacon, Usd.TimeCode(frame + HOLD))
        frame += SEG

    end_frame = frame
    # close the loop back to the first station for a seamless repeat
    first = STATIONS[0]
    puck_t.Set(Gf.Vec3d(first[1], first[2], Z_PUCK), Usd.TimeCode(end_frame))
    marker_t.Set(Gf.Vec3d(first[1], first[2], Z_BEACON), Usd.TimeCode(end_frame))
    beacon_t.Set(Gf.Vec3d(first[1], first[2], Z_BEACON), Usd.TimeCode(end_frame))

    stage.SetTimeCodesPerSecond(FPS)
    stage.SetStartTimeCode(0)
    stage.SetEndTimeCode(end_frame)

    SAVE = r"C:/Users/icets/Downloads/digitaltwinsf/TrainingFactory_Industry40.usd"
    stage.GetRootLayer().Export(SAVE)
    print("cycle authored: stations", len(STATIONS), "end_frame", end_frame,
          "duration_s", round(end_frame / FPS, 1))
    print("saved ->", SAVE)


main()
