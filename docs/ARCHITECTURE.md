# Architecture

How the pieces fit together.

---

## Overview

```
   Physical factory (PLC)                 Isaac Sim (3D)
   ─────────────────────                  ──────────────
   Siemens S7-1500                        scene/TrainingFactoryDigitalTwin.usd
   OPC-UA @ 192.168.0.1:4840                   │ references
        │                                      ▼
        │  asyncua client (10x/s)         assets/…gltf  (+ .bin geometry)
        ▼                                      │
   00_factory_live.py  ──writes──►  builtins._factory_state  ──read──►  station drivers
        │                                (shared live state)            01_vgr … 04_sld
        └──► HUD window + active-station beacon                              │
                                                                            ▼
                                             move the correct USD prims each frame
```

Three layers:

1. **The scene**: a lightweight USD file that references the real CAD geometry and
   adds lights and cameras.
2. **The live feed**: one background thread polls the PLC and stores the numbers in
   a shared object.
3. **The drivers**: small scripts that read that object every frame and move the
   right parts of the 3D model.

---

## The scene

`scene/TrainingFactoryDigitalTwin.usd` is only a few kilobytes. It **references** the
factory geometry from `../assets/training_factory_official.gltf` (whose 400 MB `.bin`
holds the actual meshes) and adds a dome light, a distant light, and cameras.

The geometry is one big imported tree. Every station lives under:

```
/World/TrainingFactory/World/Factory/Assembly/Part_5/
    NAUO2   → VGR      NAUO10  → MPO      NAUO6  → SLD
    NAUO11  → HBW      NAUO3   → DPS      NAUO1  → baseplate
```

Each station is hundreds of small parts named `NAUOxxxx`. The drivers move only the
handful that actually move on the real machine (see [STATIONS.md](STATIONS.md)).

---

## The shared live state

`00_factory_live.py` creates one dictionary and stores it where every other script
can see it:

```python
builtins._factory_state = {
    "connected": True/False,
    "order":     "IN_PROCESS" / "WAITING_FOR_ORDER" / …,
    "active":    "HBW" / "VGR" / … / None,
    "act_HBW": bool, "act_VGR": bool, "act_MPO": bool, "act_SLD": bool, …,
    "vgr_rot": int, "vgr_ver": int, "vgr_hor": int,   # VGR axis encoder counts
    "hbw_hor": int, "hbw_ver": int,                   # HBW axis encoder counts
    "sld_blue": int, "sld_white": int, "sld_red": int # SLD colour counters
}
```

Using `builtins` is a simple, dependency‑free way for independent scripts to share
one object inside the same Isaac Sim process. Every driver reads it; none of them
import each other.

---

## The live loop (how mirroring works)

Inside `00_factory_live.py`:

- A **daemon thread** runs an `asyncio` loop that connects to the PLC with
  `asyncua`, then reads a fixed set of nodes about **10 times a second** and writes
  the values into `_factory_state`.
- Each read has a **2‑second timeout**. If a read hangs (dropped session) the loop
  breaks out, disconnects, waits 3 seconds, and **reconnects**, so a flaky network
  self‑heals without freezing the twin.
- A separate **Kit update subscription** (runs every rendered frame) updates the HUD
  window and moves the green beacon to whichever station is active.

The exact node IDs are in [OPCUA.md](OPCUA.md).

---

## The station drivers

Each of `01_vgr`…`04_sld` follows the same shape:

1. On start, record each moving part's **home transform** (`L0`).
2. Subscribe to the per‑frame update event.
3. Every frame, read the target pose (from live state, or a manual override) and set
   each part's transform to `L0` composed with a **world‑space** delta.

The motion is built in world space because the imported CAD parts have rotated local
frames. Translating a part along its *local* axes sends it in the wrong direction (an
early bug made the HBW "fly" and the VGR arm swing sideways). Building the motion in
**world space** and converting it into each part's local frame fixes that:

```
new_local = L0 · (Pp · D_world · Pp⁻¹)
```

where `Pp` is the parent's local‑to‑world matrix and `D_world` is the desired
rotation/translation expressed in world axes. This keeps lifts vertical, arm
extension along the arm, and rotations about the true column axis.

Published hand‑off points: the VGR driver publishes the gripper's suction point
(`builtins._vgr_grip_pos`) and the HBW driver publishes the fork position
(`builtins._hbw_fork_pos`) each frame, so a workpiece can ride the tool exactly.

---

## Overrides (how demo / full cycle drive the same rig)

The station drivers accept **manual overrides** through more `builtins` flags:

- `_vgr_test_pose = (rot, ver, hor)`: force the VGR pose (else it follows live).
- `_hbw_fork_target = (Y, Z)`: put the fork at an exact world spot.
- `_hbw_test_pose = (hor, ver)`: drive the HBW by raw counts (live path).
- `_mpo_test_angle = degrees`: force the turntable angle.

`demo_cycle.py` and `full_cycle.py` are just orchestrators. Every frame they
compute keyframed values and write these overrides, so the same station rigs animate
without any live data. When the PLC is connected and a **real order** runs, the demo
detects it (`connected` plus a station active) and yields, so live always wins.

The HBW has one extra knob, `_hbw_h_offset` (metres). The live axis counts land in a
Y range shifted from the demo's, so this constant shifts the *live* mapping back to
match. It is runtime‑tweakable.

---

## Coordinate notes

- Stage is **Z‑up, metres**. The baseplate spans roughly X ∈ [−0.47, 0.47],
  Y ∈ [−0.38, 0.38].
- VGR axis calibration: rotate **270° = 5331 counts**, lift **120 mm (max 2993)**,
  arm extend **140 mm (max 3377)**, from the official docs plus the fischertechnik TXT
  controller source.

For the per‑station part IDs and calibration, see **[STATIONS.md](STATIONS.md)**.
