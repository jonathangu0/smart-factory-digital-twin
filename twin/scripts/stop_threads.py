"""Signal all live reader threads to stop."""
import builtins


def main():
    builtins._factory_run = False
    builtins._vgr_opcua_run = False
    print("stop signalled")


main()
