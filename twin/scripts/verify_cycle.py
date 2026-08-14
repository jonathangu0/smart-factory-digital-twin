"""Jump the timeline to a mid-cycle frame and screenshot to verify puck+beacon."""
import os
import omni.usd
import omni.timeline

SHOT = r"C:/Users/icets/Downloads/digitaltwinsf/twin/shots/cycle_frame.png"
FRAME = 180  # ~ VGR pick, 7.5s in


def main():
    ctx = omni.usd.get_context()
    stage = ctx.get_stage()
    fps = stage.GetTimeCodesPerSecond()

    tl = omni.timeline.get_timeline_interface()
    tl.set_current_time(FRAME / fps)
    print("set time to frame", FRAME, "=", round(FRAME / fps, 2), "s")

    from omni.kit.viewport.utility import get_active_viewport, capture_viewport_to_file
    vp = get_active_viewport()
    vp.set_active_camera("/World/OverviewCam")
    os.makedirs(os.path.dirname(SHOT), exist_ok=True)
    capture_viewport_to_file(vp, SHOT)
    print("shot ->", SHOT)


main()
