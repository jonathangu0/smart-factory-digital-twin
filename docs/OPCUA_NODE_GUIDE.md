# Understanding the OPC-UA nodes — a decoder guide

The factory's OPC-UA server exposes **2,510 nodes** ([`analysis/opcua_nodes.csv`](../analysis/opcua_nodes.csv)).
That number is intimidating, but most of it is repetition, plumbing, and timestamps.
This guide gives you the key to read any node name at a glance, and a map of what
each group actually is.

**Endpoint:** `opc.tcp://192.168.0.1:4840` (anonymous) · everything meaningful is in namespace `ns=3`.

---

## The 30-second summary

Of the 2,510 nodes:

| Bucket | Count | Do you care? |
|---|---:|---|
| OPC-UA server plumbing (`ns=1`, `i=`, `ns=2`) | ~912 | ❌ Ignore — server internals & device identity |
| Timestamps (`ldt_ts`) | 363 | ❌ Ignore — "when did this last change" |
| History / log entries (`i_code`) | 347 | 🟡 Only if auditing past events |
| **Actual live factory signals + config** | **~890** | ✅ **This is the real content** |

And within that last bucket, the same **Axis** structure repeats seven times and the
same **Interface** pattern repeats hundreds of times — so the number of *distinct ideas*
you need to learn is closer to **~150**.

---

## The one key that unlocks everything: the name prefix

Every factory node is named in Siemens style, where the **first letters encode the data
type**. Learn this table and most names explain themselves:

| Prefix | Type | Meaning | Example |
|---|---|---|---|
| `x_` | Bool | a true/false flag | `x_Referenced`, `x_active`, `x_Position_Reached` |
| `i_` | Int | a whole number (count, code, PWM level) | `i_CounterValue_Blue`, `i_PWM` |
| `di_` | DInt | a large integer — almost always a **position** in encoder counts | `di_Actual_Position`, `di_Pos_HBW_rotate` |
| `w_` | Word | a raw 16-bit value — used for colour/thresholds | `w_Threshold_White_Red`, `w_Actual_ColorValue` |
| `r_` | Real | a floating-point **sensor reading** | `r_t` (temp), `r_h` (humidity), `r_br` (brightness) |
| `s_` | String | text — a state, id, or command | `s_state`, `s_id`, `s_cmd`, `s_type` |
| `ldt_` | LDT | a **timestamp** (`ldt_ts`) attached to a published value | `ldt_ts` |
| `gtyp_` | — | a top-level **data block** (a whole machine) | `gtyp_VGR`, `gtyp_HBW` |

Two more conventions worth knowing:

- **`di_Pos_...`** means a *stored target position* (a calibrated setpoint), e.g.
  `di_Pos_HBW_rotate = 5338` is the rotation count for "arm pointing at the warehouse."
  These are constants, not live movement.
- **`di_Actual_Position`** is the *live* position right now. This is the one you read to
  see the machine move.

So `di_Actual_Position` reads as "DInt / actual position / live" and
`x_Position_Reached` reads as "Bool / has the axis arrived / yes-no" — no guessing needed.

---

## The map: 9 data blocks (`gtyp_*`)

All factory data lives under nine top-level blocks. Node counts are approximate (they
include each block's timestamps and history).

| Block | ~Nodes | What it is |
|---|---:|---|
| `gtyp_HBW` | 741 | High-Bay Warehouse. Large because it stores a **history log** (≈200 `i_code`+`ldt_ts` pairs) and a rack-position grid (`di_PosRack_*`). |
| `gtyp_Interface_Dashboard` | 210 | The bridge to the dashboard/cloud. **Publish** = data sent out; **Subscribe** = state/commands coming in. |
| `gtyp_VGR` | 167 | Vacuum Gripper Robot. Three Axis blocks + many `di_Pos_*` calibrated destinations. |
| `gtyp_Interface_TXT_Controler` | 138 | The TXT controllers' interface — NFC/workpiece structs and history. |
| `gtyp_SSC` | 107 | A 2-axis gantry with colour thresholds and a workpiece slot. |
| `gtyp_SLD` | 73 | Sorting Line — colour counters and thresholds. |
| `gtyp_MPO` | 73 | Multi-Processing station — turntable & vacuum **PWM setpoints** + process flags. |
| `gtyp_Setup` | 34 | Global calibration (colour sensor calibration values, etc.). |
| `gtyp_SetupAxis` | 21 | Axis calibration constants. |

---

## Repeating structure #1: the Axis block (learn it once, know all 7)

VGR (rotate/vertical/horizontal), HBW (H/V), and SSC (H/V) are all the **same UDT**.
Every axis has exactly these fields:

| Field | Meaning |
|---|---|
| `di_Actual_Position` | live position, in encoder counts |
| `di_Target_Position` | where it's been told to go |
| `di_Increment` | step size for the current move |
| `x_Start_Positioning` | command: begin moving |
| `x_Reference` / `x_Referenced` | command to home / has it been homed |
| `x_Position_Reached` | true when it has arrived |
| `i_PWM` | motor speed/power for this axis |
| `Config` (sub-block) | soft limits (`di_Pos_Soft_Switch`, `di_Neg_Soft_Switch`), reference position, and arrival tolerance (`di_Pos_Window`) |

So "understand one axis" genuinely means "understand all seven."

> **Note on counts vs. units:** positions are raw encoder counts, not mm or degrees.
> Convert using the calibrated `di_Pos_*` reference values in the same block.

---

## Repeating structure #2: the Interface Publish/Subscribe pattern

`gtyp_Interface_Dashboard` splits into two directions:

- **`Publish` (~45 nodes)** — data the factory *sends out* to the dashboard/cloud.
- **`Subscribe` (~375 nodes)** — state and commands the factory *receives/mirrors*, e.g.
  `State_VGR.x_active`, `State_Order.s_state`, and the environment/brightness sensors.

The Subscribe side looks huge only because every field carries its own `ldt_ts`
timestamp and some carry a `History` array. Strip those and it's a modest set of
real values.

---

## Why the count is so high (where the "noise" comes from)

If you're scanning for real signals, mentally delete these first:

- **~912 plumbing nodes** — anything with a node id of `ns=1;...`, `ns=2;...`, or `i=...`.
  These are the OPC-UA server's own type system and the Siemens device identity
  (model, serial, firmware). Not factory data.
- **363 `ldt_ts`** — timestamps. One hangs off nearly every published value.
- **347 `i_code`** (+ their paired `ldt_ts`) — mostly the **HBW history log** and TXT
  history arrays: a record of past events, not a live signal.

What's left — the axis blocks, the counters, the process flags, the sensor reals, and
the calibration constants — is the ~150 distinct things worth reasoning about.

---

## How to filter the CSV for just the useful nodes

The CSV columns are `station, browse_name, node_class, value_type, value, node_id, path`.
Practical filters:

- **Only real factory data:** keep rows whose `node_id` contains `ns=3`.
- **Only live signals (drop timestamps & history):** additionally exclude `browse_name`
  of `ldt_ts` and `i_code`.
- **Only positions:** `browse_name` = `di_Actual_Position`.
- **Only on/off states:** `value_type` = `bool`.
- **By machine:** filter the `station` column (`VGR`, `HBW`, `MPO`, `SLD`, `SSC`, …).

For the specific signals a supervisor might ask for (per-station), see
[SUPERVISOR_SIGNALS.md](SUPERVISOR_SIGNALS.md). For the node IDs the live twin reads,
see [OPCUA.md](OPCUA.md).
