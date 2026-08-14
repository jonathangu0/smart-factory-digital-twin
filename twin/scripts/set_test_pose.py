"""Force a VGR test pose for verification (rotate ~90deg, mid lift, mid extend)."""
import builtins


def main():
    builtins._vgr_test_pose = (1736, 1500, 1800)
    print("test pose set:", builtins._vgr_test_pose)


main()
