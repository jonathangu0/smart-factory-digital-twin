"""Print the current live STATE from the running factory twin."""
import builtins


def main():
    s = getattr(builtins, "_factory_state", None)
    if s is None:
        print("factory_live not running")
        return
    print("connected:", s.get("connected"), "| error:", s.get("error"))
    print("order:", s.get("order"), "| ACTIVE:", s.get("active"))
    print("active flags:", {st: s.get("act_" + st) for st in ["HBW", "VGR", "MPO", "SLD", "DSI", "DSO"]})
    print("VGR r/v/h:", s.get("vgr_rot"), s.get("vgr_ver"), s.get("vgr_hor"))
    print("HBW h/v:", s.get("hbw_hor"), s.get("hbw_ver"))
    print("SLD B/W/R:", s.get("sld_blue"), s.get("sld_white"), s.get("sld_red"))


main()
