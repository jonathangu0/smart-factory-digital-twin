"""Floating 'Run one cycle' button. Click it to play exactly one production cycle."""
import omni.ui as ui
import omni.timeline
import builtins


def _run_cycle():
    tl = omni.timeline.get_timeline_interface()
    tl.set_looping(False)
    tl.set_current_time(0.0)
    tl.play()


def main():
    if getattr(builtins, "_cycle_win", None):
        try:
            builtins._cycle_win.destroy()
        except Exception:
            pass
    win = ui.Window("Factory Cycle", width=240, height=110)
    with win.frame:
        with ui.VStack(spacing=8, height=0):
            ui.Label("Training Factory 4.0", height=20)
            ui.Button("▶  Run one cycle", height=40, clicked_fn=_run_cycle)
            ui.Label("(20 s: HBW -> VGR -> MPO -> SLD -> out)", height=16)
    builtins._cycle_win = win
    print("Run Cycle button window created.")


main()
