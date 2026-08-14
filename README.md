# Training Factory Industry 4.0 — Live Digital Twin

A live, mechanically‑accurate **3D digital twin** of the fischertechnik *Training
Factory Industry 4.0 (24V)* built in **NVIDIA Isaac Sim**. The twin uses the real
factory's CAD geometry and is driven in **real time by the factory's OPC‑UA data** —
run a cycle on the physical factory and the 3D scene mirrors it.

It also runs fully **offline**: a built‑in demo and a full order‑cycle animation let
you watch every station move without the hardware connected.

<!-- Add a screenshot at docs/img/overview.png to show it here -->

---

## What it does

- **Live mirror** — polls the factory PLC over OPC‑UA (~10×/s) and reflects order
  state, the active station, and the VGR/HBW axis positions. A glowing beacon marks
  the active station and a HUD shows the live values.
- **Mechanical articulation** — each station physically moves the *correct* parts:
  - **VGR** (Vacuum Gripper Robot) — 3 axes: rotate, lift, arm extend; carries a workpiece.
  - **HBW** (High‑Bay Warehouse) — stacker crane travels the rack + fork lifts; 9 stored pucks.
  - **MPO** (Multi‑Processing Station) — turntable indexes with its vacuum gripper.
  - **SLD** (Sorting Line) — belt travel + colour ejection into bins.
  - **DPS** (Delivery/Pickup) — static (no axes; serviced by the VGR), per the official docs.
- **Full order cycle** — one product travels **HBW → VGR → MPO → SLD → VGR → DPS**,
  handed off between machines, on a 64‑second loop.

---

## Repository layout

```
digitaltwinsf/
├── scene/
│   └── TrainingFactoryDigitalTwin.usd   # THE scene (open this in Isaac Sim)
├── assets/
│   ├── training_factory_official.gltf   # factory CAD geometry
│   └── training_factory_official.bin    # geometry buffer (Git LFS — 400 MB)
├── drivers/                             # Python that brings the scene to life
│   ├── 00_factory_live.py               #   live OPC-UA mirror + HUD + beacon
│   ├── 01_vgr.py                        #   VGR 3-axis articulation
│   ├── 02_hbw.py                        #   HBW crane + rack pucks
│   ├── 03_mpo.py                        #   MPO turntable
│   ├── 04_sld.py                        #   SLD sorting line
│   ├── 05_vgr_workpiece.py              #   workpiece that rides the VGR gripper
│   ├── demo_cycle.py                    #   offline gentle demo (all stations)
│   ├── full_cycle.py                    #   full product journey animation
│   ├── camera_overview.py               #   frame the whole factory
│   └── screenshot.py                    #   save a viewport screenshot
├── analysis/                            # OPC-UA discovery deliverables
│   ├── opcua_catalog.json               #   every browsed node
│   ├── opcua_nodes.csv                  #   node list as a spreadsheet
│   ├── nodered_flows.json               #   exported Node-RED flows
│   ├── browse_opcua.py                  #   re-browse the PLC
│   ├── event_logger.py                  #   timestamp live events to JSONL
│   └── sample_events.jsonl              #   example event log
├── reference/                           # official fischertechnik manuals (PDF/text)
├── docs/                                # detailed documentation (start with SETUP)
├── Launch-IsaacSim-MCP.bat              # start Isaac Sim with the MCP extension
└── .mcp.json                            # MCP server config for the AI tooling
```

---

## Quick start

### One click (recommended)
Double‑click **`START_LIVE_TWIN.bat`**. It launches Isaac Sim, opens the scene,
enables the MCP server, waits for the geometry to load, and auto‑runs every station
driver — you land directly on the live twin. Keep the console window open.

*(First launch: install Isaac Sim 6.0.1 and clone the repo — see [docs/SETUP.md](docs/SETUP.md).
If using Git LFS for the 400 MB geometry buffer, run `git lfs install` before cloning.)*

### By hand
> Full step‑by‑step is in **[docs/RUNNING.md](docs/RUNNING.md)**. The short version:

1. **Open the scene**: launch Isaac Sim and open `scene/TrainingFactoryDigitalTwin.usd`.
2. **Bring it to life** — in the Script Editor, run the driver scripts in order:
   `00_factory_live.py` → `01_vgr.py` → `02_hbw.py` → `03_mpo.py` → `04_sld.py`
   → `05_vgr_workpiece.py`.

Either way, then pick a mode:

| Mode | How | What you see |
|------|-----|--------------|
| **Live twin** | be on the factory network; run a cycle on the real factory | the 3D scene mirrors the real machines in real time |
| **Offline demo** | run `demo_cycle.py` | every station moves through a gentle loop |
| **Full order cycle** | run `full_cycle.py` | one product travels the whole factory |

To frame the whole factory, run `camera_overview.py`.

---

## The live connection (at a glance)

| Thing | Value |
|-------|-------|
| Factory Wi‑Fi | `TP-Link_8911` |
| PLC (OPC‑UA) | `opc.tcp://192.168.0.1:4840` (anonymous) |
| Node‑RED | `http://192.168.0.5:1880` |
| MQTT broker | `192.168.0.10:1883` (user `txt` / pass `xtx`) |
| Isaac Sim MCP | WebSocket `localhost:8766` |

See **[docs/OPCUA.md](docs/OPCUA.md)** for the exact node IDs the twin reads.

---

## Documentation

- **[docs/SETUP.md](docs/SETUP.md)** — install Isaac Sim, the MCP server, and connect to the factory.
- **[docs/RUNNING.md](docs/RUNNING.md)** — open the scene, run every mode, and all the live controls.
- **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)** — how the scene + drivers + OPC‑UA loop fit together.
- **[docs/STATIONS.md](docs/STATIONS.md)** — each station's mechanics, moving parts, and calibration.
- **[docs/OPCUA.md](docs/OPCUA.md)** — the OPC‑UA node map and the analysis deliverables.

---

## Hardware

fischertechnik **Training Factory Industry 4.0, 24 V** (product 551584 / 554868).
Six stations — VGR, HBW, MPO, SLD, DPS, SSC — on a Siemens S7‑1500 PLC, with a
Node‑RED dashboard and MQTT broker.
