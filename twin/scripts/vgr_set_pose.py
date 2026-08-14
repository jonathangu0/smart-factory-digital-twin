"""Set builtins._vgr_pose_next as the forced VGR pose (camera untouched)."""
import builtins


def main():
    p = getattr(builtins, "_vgr_pose_next", (0, 0, 0))
    builtins._vgr_test_pose = tuple(p)
    print("VGR pose set to", builtins._vgr_test_pose)


main()
