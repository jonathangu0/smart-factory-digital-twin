# How I Built It - dev notes

My notes on how the code works and why I put it together this way. First‑person,
focused on the implementation.

---

## The core idea

The 3D scene is just the factory's CAD geometry. All the motion, live data, and the
product moving around is **Python running inside Isaac Sim**; nothing is baked
into the USD. The pipeline:

```
real PLC ──OPC-UA──► one background thread ──► shared state ──► per-frame drivers ──► move USD parts
```

Every driver is **independent and self‑contained**. They don't import each other, and
they talk through one shared object, so I can start, stop, or re‑run any of them
without breaking the others.

---

## How the pieces talk: `builtins`

Every driver reads and writes `builtins._factory_state` (and a few `_flag` variables).
`builtins` is global across the whole Isaac Sim Python process, so independent scripts
share one object with zero plumbing:

```python
import builtins
builtins._factory_state = { "connected": ..., "vgr_rot": ..., "act_HBW": ..., ... }
```

- `00_factory_live.py` **writes** the live values into it.
- Each station driver **reads** it every frame.
- The demo / full‑cycle scripts **write override flags** into it to puppet the same
  rigs (`_vgr_test_pose`, `_hbw_fork_target`, `_mpo_test_angle`, …).

Because of this I can flip between live, demo, and full cycle at runtime by setting a
flag, with no reloading.

---

## The live feed (`00_factory_live.py`)

I run the OPC‑UA client on a **daemon thread** so it never blocks rendering:

```python
threading.Thread(target=lambda: asyncio.run(_loop()), daemon=True).start()
```

Inside `_loop()` I connect with `asyncua`, then read a fixed list of nodes ~10×/s and
dump them into the shared state. Every read has a timeout, and if it hangs (dropped
session) I break out, disconnect, wait, and reconnect, so a flaky Wi‑Fi self‑heals
instead of freezing the twin:

```python
STATE[k] = await asyncio.wait_for(node.read_value(), timeout=2.0)
```

Separately, a **Kit update subscription** (fires every rendered frame) reads the same
state to update the HUD window and move a glowing beacon onto whichever station is
active. Threads do the network, the update event does the UI, and there are no locking
headaches.

---

## The driver pattern (every station is the same shape)

Each station driver does three things:

1. **On start**: grab each moving part's home transform `L0` and reset its xform ops.
2. **Subscribe** to the per‑frame update event.
3. **Each frame**: read the target pose, then set each part's transform.

```python
xf = UsdGeom.Xformable(prim)
L0 = xf.GetLocalTransformation()        # home
...
xf.GetOrderedXformOps()[0].Set(L0 * delta)   # move it
```

### World‑space motion
The imported CAD parts have **rotated local frames**. If I translate a part along its
*local* axes, it goes in the wrong direction, which is what made the HBW "fly up" and
the VGR arm swing off to the side. The fix was to build the motion in **world space**
and convert it into the part's local frame:

```python
# D_world = the rotation/translation I want, expressed in WORLD axes
new_local = L0 * (Pp * D_world * Pp.GetInverse())
```

where `Pp` is the parent's local‑to‑world matrix. Conjugating by `Pp` re‑expresses a
world delta in the child's frame. Once I did this, lifts went straight down, arm
extension went along the arm, and rotation spun about the real column axis. I checked
each one numerically (e.g. VGR vertical = pure −Z, X/Y unchanged) before trusting it.

I worked out *which* parts to move by measuring world bounding boxes of every
sub‑part and picking the ones that actually move on the real machine, excluding
static stuff like the vacuum cylinders. For the MPO turntable I auto‑select
the disc plus everything mounted on it by radius, so the oven and saw stay put.

### Hand‑offs
The VGR driver publishes the gripper's suction point and the HBW driver publishes the
fork position each frame (`builtins._vgr_grip_pos`, `_hbw_fork_pos`). That let me hang
a workpiece exactly on the tool, and let the full‑cycle product ride whichever machine
is carrying it.

---

## Live vs. demo vs. full cycle

The station rigs don't care where their targets come from:

- **Live:** drivers read the real axis counts from `_factory_state`.
- **Demo (`demo_cycle.py`):** an orchestrator that, every frame, computes keyframed
  poses and writes the override flags. It checks `connected` plus whether a real order
  is running and **yields to live automatically** when the factory actually does
  something.
- **Full cycle (`full_cycle.py`):** same idea, but it also moves one product puck.
  Instead of a fixed path, the product **follows the active machine's published
  tool position** each frame, so the hand‑offs track the real motion.

Keyframing is a small linear interpolator over `(time, value)` lists, no animation
library:

```python
def key(t, frames):   # linear-interpolate a value at time t
    ...
```

---

## One‑click startup (`START_LIVE_TWIN.bat` + `start_twin.py`)

Isaac Sim is launched with `--enable omni.mcp_extension` (MCP server) and
`--exec drivers\start_twin.py`. That startup script opens the scene, then uses an
update subscription to **wait until the geometry has actually loaded** (checks a deep
prim plus a short settle) before `exec()`‑ing the six drivers in order. One double‑click
gets me all the way to the live twin.

---

## Stuff that bit me (so I remember)
- **Local vs. world transforms**: the whole "flying / sideways" saga. Always build
  motion in world space and conjugate into the local frame.
- **`GetChildren()` skips inactive prims**: had to use `GetAllChildren()`.
- **OPC‑UA reads can hang silently** on a dropped session, so I needed the timeout and
  reconnect loop.
- **Camera set plus screenshot in the same call races**: set the camera in one step,
  capture in the next.
- **Stale override flags pin a rig**: if a station "won't move," a leftover
  `_..._test_pose` / `_hbw_fork_target` is still set; clear it to `None`.
