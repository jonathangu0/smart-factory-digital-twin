"""

Run it (on the factory WiFi, TP-Link_8911):

    pip install asyncua          # one-time
    python3 opcua/vgr_live.py

Press Ctrl+C to stop.
"""

import asyncio
import logging

from asyncua import Client

# asyncua logs noisy warnings when a session drops mid-request (e.g. "Future for
# request id .. is already done"). Silence them - drops are handled by
# reconnecting below, so the live output stays clean.
logging.getLogger("asyncua").setLevel(logging.CRITICAL)

# The PLC's OPC UA server. Same address as the "SIEMENS PLC@192.168.0.1"
# connector in Node-RED. 4840 is the standard OPC UA port.
URL = "opc.tcp://192.168.0.1:4840"

# The three VGR axes' ACTUAL positions - the live "where the robot is".
# These NodeIds came straight from the Node-RED OPC UA flow. They are pulse
# counts from the homing switch, not millimetres (calibration comes later).
NODES = {
    "horizontal": 'ns=3;s="gtyp_VGR"."horizontal_Axis"."di_Actual_Position"',
    "vertical":   'ns=3;s="gtyp_VGR"."vertical_Axis"."di_Actual_Position"',
    "rotate":     'ns=3;s="gtyp_VGR"."rotate_Axis"."di_Actual_Position"',
}


async def read_forever(client):
    """Read the three axis positions ~5x/second until the connection drops."""
    nodes = {name: client.get_node(nid) for name, nid in NODES.items()}
    print("Connected. Reading VGR axis positions (Ctrl+C to stop):\n")
    while True:
        vals = {name: await node.read_value() for name, node in nodes.items()}
        print(f"  horizontal={vals['horizontal']:>7}   "
              f"vertical={vals['vertical']:>7}   "
              f"rotate={vals['rotate']:>7}      ", end="\r", flush=True)
        await asyncio.sleep(0.2)


async def main():
    """Connect and stream. If the PLC drops the session (a transient network or
    idle timeout), reconnect and carry on - a data layer has to survive that
    unattended rather than crash. Ctrl+C still stops it cleanly."""
    print(f"Connecting to PLC at {URL} ...")
    while True:
        client = Client(url=URL)
        # If the PLC ever rejects anonymous access, set credentials first:
        #   client.set_user("your_user"); client.set_password("your_pass")
        try:
            await client.connect()
            await read_forever(client)
        except Exception as e:
            print(f"\nConnection lost: {e}")
            print("  Reconnecting in 3s ... (check WiFi TP-Link_8911 if this repeats)")
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass  # ignore noisy teardown when already disconnected
        await asyncio.sleep(3)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nstopped.")
