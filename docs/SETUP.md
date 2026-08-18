# Setup

Getting from a fresh machine to a running twin. Three parts: (A) install the
software, (B) get the scene onto your machine, and (C) connect to the physical
factory (only needed for the live mirror).

---

## A. Software

### 1. NVIDIA Isaac Sim 6.0.1
Install Isaac Sim (Omniverse Kit 6.0.1). This is the 3D engine that opens the scene
and runs the driver scripts. The twin was built and tested on **6.0.1**.

### 2. Python packages for the live link
The live driver talks to the PLC using **asyncua** (an OPC‑UA client). Install it
into the Python that Isaac Sim uses:

```bash
# from the Isaac Sim install (adjust the path to your install)
C:\isaacsim\python.bat -m pip install asyncua
```

For the analysis scripts (optional), the same package is enough.

### 3. (Optional) the MCP server for AI‑assisted control
This project was built with an AI assistant driving Isaac Sim through an **MCP
server** (a small bridge that lets tools run Python inside Isaac Sim over a
WebSocket). You do **not** need it to run the twin by hand, but it is included:

- `Launch-IsaacSim-MCP.bat` starts Isaac Sim with the MCP extension
  (`omni.mcp_extension`) enabled, listening on `localhost:8766`.
- `.mcp.json` tells the AI tool how to reach that server.

To run the twin yourself, skip this and use the built‑in **Script Editor**
(Window → Script Editor).

---

## B. Get the scene

Clone the repository. The 3D geometry lives in `assets/` and includes a **400 MB**
binary buffer (`training_factory_official.bin`), which is stored with **Git LFS**.

```bash
git lfs install          # once per machine
git clone <your-repo-url>
```

If you are **not** using Git LFS, make sure `assets/training_factory_official.bin`
and `assets/training_factory_official.gltf` are present next to each other. The
scene references the `.gltf`, which in turn loads the `.bin`.

> **The relative path matters.** `scene/TrainingFactoryDigitalTwin.usd`
> references the geometry as `../assets/training_factory_official.gltf`. Keep the
> `scene/` and `assets/` folders side by side and the scene loads anywhere you put
> the repo.

---

## C. Connect to the physical factory (live mirror only)

You only need this for the **live** mode. The demo and full‑cycle animations run
completely offline.

1. **Join the factory Wi‑Fi:** `TP-Link_8911`.
2. **Check you can reach the PLC** at `192.168.0.1`. The twin reads OPC‑UA from
   `opc.tcp://192.168.0.1:4840` (anonymous, no username/password).
3. Other services on the same network (not required by the twin, but handy):
   - Node‑RED dashboard: `http://192.168.0.5:1880`
   - MQTT broker: `192.168.0.10:1883` (user `txt`, password `xtx`)

If the network drops, the live driver keeps trying to reconnect on its own. See
[ARCHITECTURE.md](ARCHITECTURE.md).

---

## Next

Go to **[RUNNING.md](RUNNING.md)** to open the scene and start the twin.
