"""Reload the clean saved factory scene and stop stale live threads."""
import omni.usd
import builtins

USD = r"C:/Users/icets/Downloads/digitaltwinsf/TrainingFactory_Industry40.usd"


def main():
    # stop any running live threads/subscriptions so we don't duplicate them
    builtins._factory_run = False
    builtins._vgr_opcua_run = False
    builtins._factory_sub = None
    builtins._vgr_artic_sub = None
    builtins._opcua_sub = None

    omni.usd.get_context().open_stage(USD)
    print("reloaded clean factory ->", USD)


main()
