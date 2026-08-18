# Supervisor signal map

Maps each signal requested by the supervisor to an actual OPC-UA node on the
factory PLC, with an honest status for what is and isn't available.

- **Endpoint:** `opc.tcp://192.168.0.1:4840` (anonymous)
- **Namespace:** everything is `ns=3`
- **Source:** browsed catalog in [`analysis/opcua_nodes.csv`](../analysis/opcua_nodes.csv) (2,511 nodes)

## Read this first — what OPC-UA exposes vs. what it doesn't

The Siemens S7-1500 OPC-UA server does **not** expose raw physical I/O the way the
request list assumes. It exposes the PLC *program's* global data blocks (`gtyp_*`),
which give three clean categories:

1. **Axis positions** — VGR, HBW, SSC, as `di_Actual_Position` in **encoder counts** (not mm/deg).
2. **Station process state** — `x_active`, target/handshake flags, order state.
3. **Motor setpoints + counters** — PWM values (conveyor, vacuum, turntable) and SLD colour counts.

The discrete **light barriers**, **pneumatic cylinder triggers**, and per-part
**colour/NFC** are **not** published as simple boolean/enum tags on OPC-UA. NFC and
colour surface on **MQTT** (broker `192.168.0.10:1883`, topics `f/i/nfc/ds`, colour
topics). Individual light barriers and cylinders stay internal to the PLC/TXT and
are not published as clean tags anywhere observed.

**Legend:** ✅ clean node exists · 🟡 partial (needs conversion, or is a struct/PWM/counter) · ❌ not exposed on OPC-UA

Node IDs below all take the form `ns=3;s="..."`.

---

## VGR (Vacuum Gripper Robot)

| Requested | Status | OPC-UA node |
|---|---|---|
| rotate 0–270° | ✅ | `"gtyp_VGR"."rotate_Axis"."di_Actual_Position"` — counts, convert to degrees |
| vertical 0–120 mm | ✅ | `"gtyp_VGR"."vertical_Axis"."di_Actual_Position"` — counts, convert to mm |
| horizontal 0–140 mm | ✅ | `"gtyp_VGR"."horizontal_Axis"."di_Actual_Position"` — counts, convert to mm |
| vacuum surface gripper on/off | ❌ | No VGR vacuum tag on OPC-UA. Available via MQTT only. |

Each axis also exposes `"di_Target_Position"` and `"x_Position_Reached"`.
Reference target positions per destination exist as `di_Pos_*_rotate/_vertical/_horizontal`
(e.g. `di_Pos_HBW_rotate` = 5338), useful for calibrating the counts→mm/deg scaling.

---

## Warehouse (HBW — High-Bay Warehouse)

| Requested | Status | OPC-UA node |
|---|---|---|
| vertical | ✅ | `"gtyp_HBW"."Vertical_Axis"."di_Actual_Position"` — counts |
| horizontal | ✅ | `"gtyp_HBW"."Horizontal_Axis"."di_Actual_Position"` — counts |
| conveyor on/off | 🟡 | `"gtyp_HBW"."i_PWM_ConveyorBelt"` — PWM setpoint (0 = off, >0 = on) |
| light sensor detection true/false | ❌ | No light-barrier tag on OPC-UA. |

Belt position references: `"gtyp_HBW"."di_PosBelt_Horizontal"`, `"...di_PosBelt_Vertical"`.

---

## Substation (MPO — Multi-Processing Station) — least exposed

| Requested | Status | OPC-UA node |
|---|---|---|
| vacuum surface gripper state | 🟡 | `"gtyp_MPO"."i_PWM_Vacuum"` — PWM setpoint (≈1000 when active) |
| rotate milling machine 0–90° | 🟡 | `"gtyp_MPO"."i_PWM_TurnTable"` — turntable PWM, **not** an angle |
| vertical arm / horizontal arm | ❌ | No MPO axis position nodes are published. |
| light sensor detection | ❌ | Not exposed. |
| light sensor of milling machine | ❌ | Not exposed. |
| pneumatic cylinder ejection trigger | 🟡 | `"gtyp_MPO"."x_Discard_Ready"`, `"...x_MPO_Discards_Accepted"` — process flags, not the cylinder itself |

MPO exposes only PWM setpoints and process/handshake flags — its arm position and
discrete sensors are not in the OPC-UA namespace.

---

## Sorting station (SLD — Sorting Line with Detection)

| Requested | Status | OPC-UA node |
|---|---|---|
| colour detection white/red/blue | 🟡 | Counts: `"gtyp_SLD"."i_CounterValue_White"` / `"..._Red"` / `"..._Blue"`. Live decision uses thresholds `"gtyp_SLD"."w_Threshold_White_Red"`, `"...w_Threshold_Red_Blue"`. Not a live per-part enum. |
| 3× light sensors true/false | ❌ | Not exposed. |
| 3× pneumatic cylinder ejection triggers | ❌ | Not exposed. |

`"gtyp_SLD"."i_Counter_Actual"` tracks the current in-process piece count.

---

## Delivery station (DPS = DSI in / DSO out)

| Requested | Status | OPC-UA node |
|---|---|---|
| NFC workpiece id | 🟡 | `"gtyp_Interface_TXT_Controler"..."Workpiece"` (ExtensionObject struct) or MQTT `f/i/nfc/ds`. Struct not expanded in the offline browse. |
| colour detection white/red/blue | 🟡 | Same `Workpiece` struct (`s_type`) or MQTT. |

Delivery active state: `"gtyp_Interface_Dashboard"."Subscribe"."State_DSI"."x_active"` and
`"...State_DSO"."x_active"`.

---

## Bonus: signals available on OPC-UA that the list didn't ask for

- **Order + active station:** `"gtyp_Interface_Dashboard"."Subscribe"."State_Order"."s_state"` and per-station `"State_<HBW|VGR|MPO|SLD|DSI|DSO>"."x_active"`.
- **SSC station** (2-axis gantry with colour thresholds): `"gtyp_SSC"."Horizontal_Axis"."di_Actual_Position"`, `"...Vertical_Axis"..."di_Actual_Position"`.
- **Environment sensor (BME680):** temperature `r_t`, humidity `r_h`, pressure `r_p`, air-quality `i_iaq` under `"gtyp_Interface_Dashboard"."Subscribe"."EnvironmentSensor"`.
- **Brightness sensor:** `"...BrightnessSensor"."r_br"` (%) and `"...i_ldr"` (raw).

---

## To fully close the gaps (requires the factory network)

The ❌/🟡 items — vacuum on/off, light barriers, cylinders, NFC id, live colour — are
not resolvable from the offline catalog. On the factory Wi-Fi (`TP-Link_8911`):

1. **Expand the structs:** read into the `Workpiece` / TXT-controller ExtensionObjects live to recover NFC id and colour.
2. **Read MQTT:** subscribe to broker `192.168.0.10:1883` (`txt`/`xtx`) topics `f/i/nfc/ds`, colour, and state topics — that's where the TXT controllers publish what the PLC keeps internal.
3. **Re-browse with values:** rerun [`analysis/browse_opcua.py`](../analysis/browse_opcua.py) to confirm nothing changed on the PLC.
