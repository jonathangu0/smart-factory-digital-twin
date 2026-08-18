"""Offline DEMO cycle that moves the whole twin cleanly. VGR does modest reaches,
HBW travels to the transfer side and back, MPO indexes slowly. Yields to live
OPC-UA on reconnect. Toggle builtins._demo_mode."""
import omni.usd
import omni.kit.app
import builtins

T = 32.0  # slow cycle (s)


def key(t, frames):
    if t <= frames[0][0]:
        return frames[0][1]
    for i in range(1, len(frames)):
        if t <= frames[i][0]:
            t0, v0 = frames[i-1]; t1, v1 = frames[i]
            a = (t - t0) / (t1 - t0)
            return v0 + (v1 - v0) * a
    return frames[-1][1]


# VGR: modest rotation only (<=90 deg), gentle vertical/horizontal picks. Stays
# looking like the documentation (arm centered over the tower).
VGR_ROT = [(0, 0), (7, 0), (11, 1500), (19, 1500), (24, 0), (32, 0)]      # 1500 ~= 76 deg
VGR_VER = [(0, 0), (3, 0), (5, 1700), (7, 1700), (9, 300), (21, 300),
           (23, 1700), (25, 1700), (27, 300), (32, 0)]
VGR_HOR = [(0, 0), (3, 0), (5, 1900), (7, 1900), (9, 500), (12, 500),
           (14, 3200), (17, 3200), (19, 500), (21, 500),
           (23, 1900), (25, 1900), (27, 500), (32, 0)]
# HBW crane by fork WORLD position: sit at the VGR transfer (Y=-0.12), go to a rack
# bay (Y=0.112), pick, carry back to the transfer. Stays within the rail (no overshoot).
FORK_Y = [(0, -0.12), (3, -0.12), (7, 0.112), (10, 0.112), (15, -0.12), (32, -0.12)]
FORK_Z = [(0, 0.150), (3, 0.150), (6, 0.180), (10, 0.180), (13, 0.150), (15, 0.150), (32, 0.150)]
# MPO turntable indexes slowly during processing
MPO_ANG = [(0, 0), (11, 0), (15, 110), (19, 110), (23, 0), (32, 0)]


def main():
    builtins._demo_mode = True
    builtins._demo_t = getattr(builtins, "_demo_t", 0.0)

    def _update(e):
        st = getattr(builtins, "_factory_state", {}) or {}
        # real order running? (mirror live). Otherwise, if forced, preview the demo.
        busy = st.get("order") not in (None, "", "WAITING_FOR_ORDER") or any(
            st.get(k) for k in ("act_HBW", "act_VGR", "act_MPO", "act_SLD"))
        yield_live = st.get("connected") and (busy or not getattr(builtins, "_demo_force", False))
        if yield_live:
            if getattr(builtins, "_demo_mode", False):
                builtins._demo_mode = False
                builtins._vgr_test_pose = None
                builtins._hbw_test_pose = None
                builtins._hbw_fork_target = None
                builtins._hbw_carry = False
                builtins._mpo_test_angle = None
                print("demo: live PLC detected, yielding to live data")
            return
        if not getattr(builtins, "_demo_mode", False):
            return
        dt = 1.0 / 60.0
        try:
            dt = float(e.payload.get("dt", dt)) or dt
        except Exception:
            pass
        # cap dt so a hitch never produces a big jump (keeps motion smooth)
        if dt > 0.05:
            dt = 0.05
        t = (builtins._demo_t + dt) % T
        builtins._demo_t = t
        builtins._vgr_test_pose = (key(t, VGR_ROT), key(t, VGR_VER), key(t, VGR_HOR))
        builtins._hbw_test_pose = None
        builtins._hbw_fork_target = (key(t, FORK_Y), key(t, FORK_Z))
        builtins._hbw_carry = (7.5 <= t < 14.0)   # holding a puck from bay to transfer
        builtins._mpo_test_angle = key(t, MPO_ANG)
        builtins._vgr_holding = True

    builtins._demo_sub = omni.kit.app.get_app().get_update_event_stream().create_subscription_to_pop(
        _update, name="demo_cycle")
    print("Gentle DEMO cycle running. Yields to live OPC-UA on reconnect.")


main()
