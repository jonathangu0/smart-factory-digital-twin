"""Direct fresh read of key VGR/factory tags, 5x over ~5s, to see if they move."""
import asyncio
import logging
from asyncua import Client

logging.getLogger("asyncua").setLevel(logging.CRITICAL)
URL = "opc.tcp://192.168.0.1:4840"
DB = 'ns=3;s="gtyp_Interface_Dashboard"."Subscribe".'
TAGS = {
    "order": DB + '"State_Order"."s_state"',
    "VGR_active": DB + '"State_VGR"."x_active"',
    "HBW_active": DB + '"State_HBW"."x_active"',
    "vgr_rot": 'ns=3;s="gtyp_VGR"."rotate_Axis"."di_Actual_Position"',
    "vgr_ver": 'ns=3;s="gtyp_VGR"."vertical_Axis"."di_Actual_Position"',
    "vgr_hor": 'ns=3;s="gtyp_VGR"."horizontal_Axis"."di_Actual_Position"',
    "hbw_hor": 'ns=3;s="gtyp_HBW"."Horizontal_Axis"."di_Actual_Position"',
    "sld_blue": 'ns=3;s="gtyp_SLD"."i_CounterValue_Blue"',
}


async def main():
    c = Client(url=URL)
    c.session_timeout = 30000
    await c.connect()
    nodes = {k: c.get_node(v) for k, v in TAGS.items()}
    for i in range(5):
        vals = {}
        for k, node in nodes.items():
            try:
                vals[k] = await node.read_value()
            except Exception as e:
                vals[k] = f"ERR{e}"
        print(f"read {i}:", vals)
        await asyncio.sleep(1.0)
    await c.disconnect()


asyncio.run(main())
