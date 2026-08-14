"""Resume live VGR articulation (clear the forced test pose)."""
import builtins


def main():
    builtins._vgr_test_pose = None
    print("VGR resumed live driving")


main()
