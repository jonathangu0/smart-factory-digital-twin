# OPC‑UA reference

The live twin reads a small set of OPC‑UA nodes from the factory PLC. This page lists
exactly which ones, and describes the analysis deliverables in [`analysis/`](../analysis).

- **Endpoint:** `opc.tcp://192.168.0.1:4840`
- **Security:** anonymous (no username/password)
- **Namespace:** everything below is in namespace `3` (`ns=3`)
- **Client:** [`asyncua`](https://github.com/FreeOpcUa/opcua-asyncio), polled ~10×/s

---

## Nodes the twin reads

### Order + active station (dashboard interface)
Prefix: `ns=3;s="gtyp_Interface_Dashboard"."Subscribe".`

| Meaning | Node (append to prefix) |
|---------|-------------------------|
| Order state | `"State_Order"."s_state"` |
| HBW active | `"State_HBW"."x_active"` |
| VGR active | `"State_VGR"."x_active"` |
| MPO active | `"State_MPO"."x_active"` |
| SLD active | `"State_SLD"."x_active"` |
| DSI active (delivery in) | `"State_DSI"."x_active"` |
| DSO active (delivery out) | `"State_DSO"."x_active"` |

(Each `"State_*"` also has a `"s_target"` sibling.)

### VGR axis positions
| Meaning | Node |
|---------|------|
| Rotation | `ns=3;s="gtyp_VGR"."rotate_Axis"."di_Actual_Position"` |
| Vertical | `ns=3;s="gtyp_VGR"."vertical_Axis"."di_Actual_Position"` |
| Horizontal | `ns=3;s="gtyp_VGR"."horizontal_Axis"."di_Actual_Position"` |

(Each axis also exposes `"di_Target_Position"` and `"x_Position_Reached"`.)

### HBW axis positions
| Meaning | Node |
|---------|------|
| Horizontal | `ns=3;s="gtyp_HBW"."Horizontal_Axis"."di_Actual_Position"` |
| Vertical | `ns=3;s="gtyp_HBW"."Vertical_Axis"."di_Actual_Position"` |

### SLD colour counters
| Meaning | Node |
|---------|------|
| Blue count | `ns=3;s="gtyp_SLD"."i_CounterValue_Blue"` |
| White count | `ns=3;s="gtyp_SLD"."i_CounterValue_White"` |
| Red count | `ns=3;s="gtyp_SLD"."i_CounterValue_Red"` |

These map straight into `builtins._factory_state` (see
[ARCHITECTURE.md](ARCHITECTURE.md#the-shared-live-state)).

---

## Analysis deliverables (`analysis/`)

These were produced by browsing the PLC and are useful for exploring or extending the
twin.

| File | What it is |
|------|-----------|
| `opcua_catalog.json` | Every node found by browsing the server — full tree with node IDs, names, and types. |
| `opcua_nodes.csv` | The same nodes flattened into a spreadsheet for quick searching/filtering. |
| `nodered_flows.json` | The factory's Node‑RED flows, exported for reference. |
| `browse_opcua.py` | Re‑browse the live server and regenerate the catalog. |
| `opcua_to_csv.py` | Convert the catalog JSON into the CSV. |
| `event_logger.py` | Subscribe to the live tags and **timestamp every change to a JSONL file** for analysis. |
| `sample_events.jsonl` | An example of that timestamped event log. |

### Re‑browsing the server
On the factory network:

```bash
C:\isaacsim\python.bat analysis/browse_opcua.py     # -> opcua_catalog.json
C:\isaacsim\python.bat analysis/opcua_to_csv.py     # -> opcua_nodes.csv
```

### Logging live events
```bash
C:\isaacsim\python.bat analysis/event_logger.py     # -> JSONL, one line per change with a timestamp
```

Each line is a small JSON object like `{"t": "<ISO timestamp>", "node": "...", "value": ...}`,
so you can replay or analyse a real run afterward.

---

## Other services on the factory network

Not read by the twin, but part of the same system and handy for debugging:

| Service | Address | Notes |
|---------|---------|-------|
| Node‑RED | `http://192.168.0.5:1880` | dashboard + flows |
| MQTT broker | `192.168.0.10:1883` | user `txt`, password `xtx` |
