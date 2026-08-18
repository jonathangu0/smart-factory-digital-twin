# Stations

What each station does, which parts move, and how the motion is calibrated. All part
names are the imported CAD prims (`NAUOxxxx`) under
`/World/TrainingFactory/World/Factory/Assembly/Part_5/`.

Moving vs. static parts were confirmed against the official fischertechnik
documentation and the TXT‑controller source (`TxtVacuumGripperRobot`,
`TxtHighBayWarehouse`, `TxtMultiProcessingStation`, `TxtSortingLine`,
`TxtDeliveryPickupStation`).

---

## VGR - Vacuum Gripper Robot  (`NAUO2`)  ·  driver `01_vgr.py`

A 3‑axis robot on a rotating column. Reaches every neighbouring station.

| Axis | Motion | Moving parts | Calibration |
|------|--------|--------------|-------------|
| **Rotate** | whole tower turns about its vertical column | `NAUO2856` (mast) + `NAUO2857` (arm) + `NAUO2858` (gripper) | 270° = **5331** counts |
| **Lift (vertical)** | arm rides up/down the mast | `NAUO2857` + `NAUO2858` | 120 mm, max **2993** counts |
| **Extend (horizontal)** | gripper slides out along the arm | `NAUO2858` | 140 mm, max **3377** counts |

- Rotation pivot is the turntable axis at **(0.046, −0.173)** (the base discs
  `NAUO2811` / `NAUO2861`).
- The arm was offset ~0.108 m in X from the column in the raw CAD, so the driver applies
  a fixed **`ARM_CENTER_FIX`** so the horizontal beam runs *through* the column, as in
  the documentation.
- **Static** (correctly *not* moved): the base/turntable, the two vacuum cylinders
  (`NAUO2859` / `NAUO2860`), the compressor, valves, and the power adapter
  (`NAUO2862`). An early bug rotated these; now fixed.
- The driver publishes the suction point as `builtins._vgr_grip_pos`; `05_vgr_workpiece.py`
  rides a puck there (52 mm below the gripper centre, i.e. at the suction cup).

Live source: `vgr_rot` / `vgr_ver` / `vgr_hor` (encoder counts).

---

## HBW - High‑Bay Warehouse  (`NAUO11`)  ·  driver `02_hbw.py`

A stacker crane serving a 3×3 rack of nine stored workpieces.

| Axis | Motion | Moving parts |
|------|--------|--------------|
| **Travel (horizontal)** | crane moves along the rack (world **Y**) | mast `NAUO47` + fork `NAUO48` + `NAUO49` |
| **Lift (vertical)** | fork moves up/down the mast (world **Z**) | fork `NAUO48` + `NAUO49` |

- **Rack bays:** X = −0.239, columns Y ∈ {−0.068, 0.022, 0.112}, rows Z ∈ {0.12, 0.18, 0.234}.
- Nine flat pucks (blue/red/white) are placed in the bays at startup.
- The driver can be positioned two ways:
  - **`apply(hor, ver)`**: raw OPC‑UA counts (the live path). A tunable
    `_hbw_h_offset` (default 0.3 m) shifts the live Y range to match the model.
  - **`apply_pos(fork_Y, fork_Z)`**: drive the fork to an *exact* world spot
    (used by the demo / full cycle for precise bay picks).
- Publishes the fork position as `builtins._hbw_fork_pos`; a carried workpiece
  (`_hbw_carry`) rides it from bay to the transfer point.

Live source: `hbw_hor` / `hbw_ver`.

---

## MPO - Multi‑Processing Station  (`NAUO10`)  ·  driver `03_mpo.py`

Oven, turntable, saw, and conveyor. The moving part is the **turntable**.

- **Turntable disc** `NAUO1016` plus the **36 parts of the vacuum‑gripper assembly
  mounted on it** rotate together about **(0.241, 0.172)**. The driver auto‑selects
  those 36 parts by radius (≤ 0.052 m, Z ∈ [0.064, 0.140]) so the oven, saw and frame
  stay put.
- Motion is gated on `act_MPO`: it indexes back and forth while the MPO is active,
  and rests at 0 when idle. Force it by hand with `_mpo_test_angle`.

Live source: `act_MPO` (turntable position isn't exposed as a tag, so the twin
indexes to *show activity* rather than mirror an exact angle).

---

## SLD - Sorting Line  (`NAUO6`)  ·  driver `04_sld.py`

A conveyor belt with three pneumatic ejectors that push workpieces into colour bins.

- **Belt** `NAUO2105` runs along world **Y**; workpieces travel from the infeed
  toward the sorting zone.
- Three ejection stations at Y ∈ {−0.173 (white), −0.233 (red), −0.293 (blue)}.
- While `act_SLD` is on, a workpiece travels the belt and is ejected sideways into the
  bin matching the **live colour flag** (`sld_white` / `sld_red` / `sld_blue`). Three
  colour bin markers show the targets.

Live source: `act_SLD` plus the three colour counters.

---

## DPS - Delivery / Pickup Station  (`NAUO3`)

**Static, no axes.** Per the official docs it only has an NFC reader and a colour
sensor; the VGR services it. The twin correctly leaves it still. It is the start/end
of the order cycle (raw parts in, finished parts out).

---

## SSC - Sensor/Camera Station

A pan/tilt camera mounted near the MPO. Not articulated in this build (no position
tags available); listed for completeness.

---

## Where the numbers came from

Positions and calibration were measured directly from the geometry (world bounding
boxes of each part) and cross‑checked against the fischertechnik manuals in
[`reference/`](../reference) and the TXT‑controller axis definitions. If you move the
factory or re‑import the CAD, re‑measure with a bounding‑box query and update the
constants at the top of each driver. They are all named and grouped for that.
