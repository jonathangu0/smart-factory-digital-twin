# Smart Factory — Digital Twin Data Layer

The real-time data layer for a digital twin of the fischertechnik **Training
Factory Industry 4.0** (24V). This code reads live data from the physical
factory and turns it into things you can see and build on: a live 2D dashboard,
recorded history for replay/analysis, and a live 3D model of the robot.

> **New here? Read this whole file once (5 min), then jump to
> [Where to continue](#where-to-continue).** Everything you need is below.

---

## Contents
1. [Quick start](#quick-start)
2. [The two data sources (how the factory talks)](#the-two-data-sources)
3. [Repository layout](#repository-layout)
4. [What every file does](#what-every-file-does)
5. [How to run each tool](#how-to-run-each-tool)
6. [Network & access (must-read)](#network--access)
7. [Gotchas that will trip you up](#gotchas)
8. [VGR calibration reference](#vgr-calibration-reference)
9. [Where to continue](#where-to-continue)
10. [Glossary](#glossary)

---

## Quick start

**One-time setup** (from the project folder):
```bash
python3 -m venv venv                 # create the Python environment (Python 3.11+)
source venv/bin/activate             # activate it
pip install -r requirements.txt      # install the 2 libraries
```

**Run** (must be on the factory WiFi — see [Network](#network--access)):
```bash
source venv/bin/activate             # every new terminal
python3 run_factory.py               # live 2D dashboard  -> http://localhost:8420
python3 opcua/vgr_twin.py            # live 3D robot twin -> http://localhost:8500
```

**No factory nearby?** Try the offline demo — replay the bundled recording:
```bash
python3 run_factory.py --replay sample_recording.jsonl
```

Press **Ctrl+C** to stop anything.

---

## The two data sources

The factory exposes data in **two different ways**. Keeping them straight is the
single most important thing to understand.

```
   Physical factory (motors, sensors, workpieces)
              │
        ┌─────┴───────────────────────────┐
        │                                  │
   Siemens PLC (192.168.0.1)          TXT controller (192.168.0.10)
   speaks OPC UA                      runs an MQTT broker
        │                                  │
   raw low-level signals              clean high-level JSON
   (e.g. robot axis positions)        (station states, orders, sensors)
        │                                  │
   opcua/ scripts (asyncua)           live_data_feed.py (paho-mqtt)
```

- **MQTT** = the *easy, high-level* feed. The TXT controller publishes ready-made
  JSON (which station is active, orders, stock, sensors) to a broker. Programs
  *subscribe* to "topics" and receive messages. This is the primary feed.
- **OPC UA** = the *raw, low-level* source. The PLC exposes its internal
  variables (called *tags*) directly — like the robot's exact motor positions,
  which MQTT does not publish. You read these straight from the PLC.

**Rule of thumb:** need factory status/orders/sensors → MQTT. Need real
motor/axis numbers → OPC UA.

---

## Repository layout

```
infosys_factory_project/
├── run_factory.py          # ← START HERE: launches the live dashboard
├── live_data_feed.py       # MQTT feed (writes the data files)
├── factory_2d_view.py      # 2D dashboard + replay (localhost:8420)
├── twin_reader.py          # helper for the Isaac Sim (3D) team
├── opcua/
│   ├── vgr_live.py         # print robot positions in the terminal
│   └── vgr_twin.py         # live 3D robot twin (localhost:8500)
├── sample_recording.jsonl  # bundled recording for offline replay/testing
├── requirements.txt        # the 2 external libraries
└── README.md               # this file
```

Two files appear only at **runtime** (created when the feed runs, not shipped):
`factory_state.json` (current snapshot) and `factory_events.jsonl` (live history).

---

## What every file does

### MQTT pipeline (the core system, at the root)
These work together and share the data files by relative path, so they live at
the root. **Always run them from the project root.**

| File | What it does |
|------|--------------|
| `run_factory.py` | **Start here.** One command that launches the feed + dashboard together. |
| `live_data_feed.py` | Connects to the MQTT broker, keeps a live model of the whole factory, writes `factory_state.json` (now) and appends `factory_events.jsonl` (history). **Do not edit — everything depends on it.** |
| `factory_2d_view.py` | The 2D dashboard at `localhost:8420`. Shows stations, sensors, cycle times, and a live event log. Also **replays** recorded `.jsonl` files with play/pause/scrub. |
| `twin_reader.py` | A tiny helper the Isaac Sim (3D) team imports to read `factory_state.json` each frame. |

### OPC UA (in `opcua/`)
Direct-from-PLC signals, kept separate from the MQTT side.

| File | What it does |
|------|--------------|
| `opcua/vgr_live.py` | Simplest possible: prints the VGR robot's 3 live axis positions in the terminal. Good first test that OPC UA works. |
| `opcua/vgr_twin.py` | **Live 3D digital twin of the VGR robot** in the browser (`localhost:8500`). Fuses OPC UA axis positions + MQTT state and animates the robot. |

### Supporting files
| File | What it is |
|------|-----------|
| `sample_recording.jsonl` | A real recorded factory run (~22k events, several sessions). Use it to try the dashboard's replay without a live factory. |
| `requirements.txt` | The two external Python libraries (`paho-mqtt`, `asyncua`). |
| `factory_state.json` / `factory_events.jsonl` | **Generated at runtime** by the feed — not shipped. Snapshot + full history. |

---

## How to run each tool

> **Always** `source venv/bin/activate` first, and run from the project root.

### 1. Live 2D dashboard — `run_factory.py`
```bash
python3 run_factory.py
```
Launches the data feed + dashboard, opens `http://localhost:8420`. Watch the
factory live: stations glow when active, cycle times fill in, the event log
scrolls. Header dot: **green = live**, amber = idle, red = feed offline.

### 2. Replay a recording — `factory_2d_view.py`
```bash
python3 run_factory.py --replay sample_recording.jsonl
```
Same dashboard, but plays back a recorded log with play/pause/speed/scrub. It
auto-splits the file into **sessions** (separate factory runs) — pick one from
the dropdown. Needs no factory connection. (You can also load any `.jsonl` from
the **Load recording** button in the browser.)

### 3. Robot positions in the terminal — `opcua/vgr_live.py`
```bash
python3 opcua/vgr_live.py
```
Prints the VGR's 3 axis positions, refreshing live. The quickest check that the
OPC UA connection to the PLC works.

### 4. Live 3D robot twin — `opcua/vgr_twin.py`
```bash
python3 opcua/vgr_twin.py
```
Opens `http://localhost:8500` with a 3D VGR that moves with the real robot.
Drag to orbit, scroll to zoom. Run a real cycle and watch it rotate, raise, and
extend in sync.

---

## Network & access

Nothing works off the factory network. These are the fixed facts:

| Thing | Address |
|-------|---------|
| Factory WiFi | **`TP-Link_8911`** (you must be joined to this) |
| MQTT broker | `192.168.0.10:1883` — user `txt`, password `xtx` |
| PLC (OPC UA) | `opc.tcp://192.168.0.1:4840` — security: None (anonymous) |
| Node-RED dashboard | `http://192.168.0.5:1880/ui` |
| Node-RED flow editor | `http://192.168.0.5:1880` |

---

## Gotchas

Real things that have already caught people out:

- **TXT controller forgets its program on power-cycle.** After the factory is
  turned off/on, reload its program via *Files* before expecting the MQTT feed
  to work. This is normal, not a fault.
- **Two timestamps per event.** In the history log, the outer `ts` is when our
  feed logged it; the inner `data.ts` is the factory's own clock. **Use
  `data.ts` for any analysis.**
- **Empty warehouse slots look full.** An empty HBW slot still arrives as a
  workpiece object with blank fields. Only count a slot as occupied if it has a
  real `type`/`id` (already handled in `live_data_feed.py`).
- **OPC UA sessions drop.** The PLC caps sessions to 30s and WiFi can nap when
  idle; the OPC UA scripts auto-reconnect, so a brief "Reconnecting…" line is
  normal, not a crash.
- **The 3D twin needs internet in the browser** (it loads Three.js from a CDN).
  The WISP WiFi normally has it.
- **VGR positions are pulse counts, not millimetres** — see calibration below.

---

## VGR calibration reference

The robot reports each axis as a raw pulse count (dead-reckoned from a homing
switch — valid after homing, and it can drift). Measured mapping:

**Rotation** (0 = pointing south; count increases **counter-clockwise**):
| Count | Direction |
|-------|-----------|
| 0 | South (start) |
| 1736 | East (90°) |
| 3501 | North (180°) |
| 5331 | West (270°) |

**Vertical** (0 = top/resting; larger = lower):
| Count | Position |
|-------|----------|
| 0 | Top (resting) |
| 648 | Picking from High-Bay Warehouse |
| 2993 | Lowest (pickup station) |

**Horizontal** (0 = retracted; larger = extended):
| Count | Position |
|-------|----------|
| 0 | Retracted (resting) |
| 633 | Picking from High-Bay Warehouse |
| 3377 | Fully extended (drop at processing station) |

These numbers live in `opcua/vgr_twin.py` (`ROT_270`, `VERT_MAX`, `HORIZ_MAX`)
and drive the 3D model. Re-measure and update them if the robot is re-homed.

---

## Where to continue

The project's goal: a digital twin for **virtual commissioning** (test logic in
simulation before running hardware) and **predictive operations** (spot faults,
plan maintenance). Both need reliable live data + baseline cycle times — that
foundation exists. Open work, roughly in priority order:

**Done**
- ✅ Live MQTT feed + normalized state model (`live_data_feed.py`)
- ✅ 2D dashboard: live view, replay, sessions, cycle times, key events
- ✅ OPC UA proven: VGR axis positions read live (`opcua/vgr_live.py`)
- ✅ Live 3D VGR twin fusing OPC UA + MQTT (`opcua/vgr_twin.py`)

**Open — pick up here**
1. **Publish OPC UA into the main pipeline.** Right now `vgr_twin.py` reads OPC
   UA on its own. The cleaner long-term design: have **Node-RED** (already the
   PLC↔MQTT bridge, on `192.168.0.5`) publish the axis positions to a new MQTT
   topic like `i/opcua/vgr`, so `live_data_feed.py` records them like everything
   else. Then all data flows through one path.
2. **Calibrate counts → real units.** Move the robot to known positions, record
   the counts, and derive mm/degrees so the twin is dimensionally accurate.
3. **Extend the twin to other stations** (HBW, MPO, SLD…) using the same pattern
   as the VGR.
4. **Cycle-time deliverable.** The dashboard already computes cycle times; the
   outstanding ask is an **Excel/CSV export** (timestamp | station | action |
   details) from the history log, with sensor noise filtered out.
5. **Isaac Sim integration** (external team): they poll `factory_state.json` via
   `twin_reader.py` per frame. Keep that file's shape stable for them.

**How to explore the factory's raw signals:** open the Node-RED editor
(`192.168.0.5:1880`), look at the `read real values from PLC` and `hmi - *`
flows — that's where the PLC tags (NodeIds) are defined. Copy NodeIds from there
(or browse with the free **UaExpert** tool) to read new signals.

---

## Glossary

- **MQTT** — a lightweight messaging system. Devices *publish* messages to named
  *topics*; programs *subscribe* to receive them. A *broker* is the middleman.
- **OPC UA** — an industrial protocol to read a PLC's data directly. The PLC is
  the *server*; its variables are *nodes*, each with a unique *NodeId*.
- **PLC** — Programmable Logic Controller; the industrial computer (Siemens
  S7-1500) that actually runs the factory.
- **TXT controller** — the fischertechnik controller that hosts the MQTT broker.
- **Node-RED** — a visual flow tool (on the Raspberry Pi) that bridges OPC UA to
  MQTT and drives the factory's own dashboard.
- **Tag / Node** — one variable inside the PLC (e.g. a motor's position).
- **VGR** — Vacuum Gripper Robot: the 3-axis arm (rotate / vertical / horizontal).
- **HBW / MPO / SLD / DSI / DSO** — the factory's stations (warehouse, processing,
  sorting line, input, output).
- **Session** — one continuous factory run in the recorded log, separated from
  the next by a gap of downtime.
