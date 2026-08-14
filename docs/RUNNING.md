# Running the twin

This guide takes you from an open scene to a moving factory — live, demo, or full
cycle — plus every live control you can tweak.

All scripts live in `drivers/`. You run them inside Isaac Sim's **Script Editor**
(Window → Script Editor → open a file → Run), or via the MCP tooling if you set it
up. Each script is self‑contained and safe to re‑run.

---

## 1. Open the scene

Launch Isaac Sim and open:

```
scene/TrainingFactoryDigitalTwin.usd
```

You should see the whole factory on a baseplate, lit, with the six stations. It is
static until you start the drivers.

---

## 2. Start the drivers (in order)

Run these six once, in this order. `00_factory_live.py` **must be first** — it
creates the shared live‑state object the other drivers read.

| Order | Script | What it starts |
|-------|--------|----------------|
| 1 | `00_factory_live.py` | OPC‑UA polling loop, the HUD window, the active‑station beacon |
| 2 | `01_vgr.py` | VGR rotate / lift / arm‑extend articulation |
| 3 | `02_hbw.py` | HBW crane + the 9 rack pucks |
| 4 | `03_mpo.py` | MPO turntable |
| 5 | `04_sld.py` | SLD sorting line |
| 6 | `05_vgr_workpiece.py` | the puck that rides the VGR gripper |

Now choose a mode below.

---

## 3a. Live mode (mirror the real factory)

Nothing else to run. If you are on the factory network (see
[SETUP.md](SETUP.md#c-connect-to-the-physical-factory-live-mirror-only)), the HUD
shows **● LIVE — connected to PLC**. **Run an order on the real factory** and the
twin follows it: the beacon jumps to the active station, and the VGR/HBW positions
track the real axes in real time.

When the factory is idle (`order: WAITING_FOR_ORDER`) nothing moves — that is
correct, the twin is faithfully showing an idle factory.

## 3b. Offline demo (no hardware)

Run `demo_cycle.py`. Every station moves through a slow, clean loop so you can see
the mechanics working. It **automatically steps aside** the moment a real order
runs, handing back to live data.

## 3c. Full order cycle (one product, whole factory)

Run `full_cycle.py`. An **orange product** travels the documented order flow:

```
HBW bay → HBW fork → VGR → MPO turntable → VGR → SLD belt → colour bin → VGR → DPS
```

It loops every 64 seconds. Restart it from the beginning anytime:

```python
import builtins
builtins._fc_t = 0.0
```

---

## 4. Camera & screenshots

- `camera_overview.py` — frames the entire factory and makes that camera active.
- `screenshot.py` — saves the current view to `shots/twin.png`. Run it in a
  **separate** step from any camera change (there is a one‑frame timing race if you
  change the camera and capture in the same call).

---

## 5. Live controls (paste into the Script Editor)

The drivers communicate through a few `builtins` flags you can set live — no reload
needed.

**Switch modes**
```python
import builtins
builtins._fullcycle = False   # stop the full cycle
builtins._demo_mode = True    # start the offline demo
# for pure live mirroring, set both False:
builtins._fullcycle = False; builtins._demo_mode = False
```

**Force the demo to preview even while connected to the PLC**
```python
import builtins
builtins._demo_force = True    # demo runs even though live is connected
builtins._demo_mode  = True
# it still yields to live automatically once a REAL order starts
```

**Nudge the HBW crane's live position** (if the live crane sits off from the demo)
```python
import builtins
builtins._hbw_h_offset = 0.30   # metres; bigger shifts the live crane one way, smaller/negative the other
```

**Pose the VGR by hand** (counts; rotate 0–5331 = 0–270°, lift 0–2993, extend 0–3377)
```python
import builtins
builtins._vgr_test_pose = (1500, 800, 1200)   # (rotate, lift, extend)
builtins._vgr_test_pose = None                # release back to live/demo
```

**Put the HBW fork at an exact spot** (world metres)
```python
import builtins
builtins._hbw_fork_target = (0.112, 0.180)    # (Y along rack, Z height) -> a bay
builtins._hbw_fork_target = None              # release
```

**Spin the MPO turntable by hand** (degrees)
```python
import builtins
builtins._mpo_test_angle = 60.0
builtins._mpo_test_angle = None
```

---

## 6. Troubleshooting

| Symptom | Fix |
|---------|-----|
| HUD says **offline** | Check you are on `TP-Link_8911` and can ping `192.168.0.1`. The driver auto‑reconnects. |
| Nothing moves in live mode | The factory is idle — start an order on the real machine. |
| A station is frozen | A leftover manual override is pinning it. Clear it: set its `_..._test_pose` / `_hbw_fork_target` / `_mpo_test_angle` to `None`. |
| Scene opens but geometry is missing | `assets/` isn't next to `scene/`, or the `.bin` didn't download (Git LFS). See [SETUP.md](SETUP.md#b-get-the-scene). |
| Two things move at once | The demo *and* full cycle are both on. Turn one off (section 5). |

More on how it all fits together: **[ARCHITECTURE.md](ARCHITECTURE.md)**.
