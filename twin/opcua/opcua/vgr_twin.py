"""
vgr_twin.py  -  a live 3D digital twin of JUST the VGR (vacuum gripper robot).

It fuses two live sources and renders the robot in your browser with Three.js:

  * OPC UA (the PLC, opc.tcp://192.168.0.1:4840) -> the three real axis
    positions (rotate / vertical / horizontal), plus their targets and
    "position reached" flags.
  * MQTT (f/i/state/vgr) -> the robot's live state (active/idle, code, target)
    and timestamp. Best-effort: the twin still runs if the broker is down.

A small web server exposes /vgr.json with the fused live data; the page polls it
and animates a 3D VGR whose motion is mapped from your measured calibration.

Run (on the factory WiFi):
    pip install asyncua paho-mqtt
    python3 opcua/vgr_twin.py           # opens http://localhost:8500

Ctrl+C to stop.  --no-browser to skip auto-opening the tab.
"""

import json
import time
import asyncio
import logging
import argparse
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from asyncua import Client
import paho.mqtt.client as mqtt

logging.getLogger("asyncua").setLevel(logging.CRITICAL)

# --- connections -----------------------------------------------------------
OPCUA_URL = "opc.tcp://192.168.0.1:4840"
BROKER_HOST, BROKER_PORT = "192.168.0.10", 1883
BROKER_USER, BROKER_PASS = "txt", "xtx"
PORT = 8500

# The 9 VGR tags, mapped to the keys we expose in /vgr.json.
OPCUA_TAGS = {
    "rotate":             'ns=3;s="gtyp_VGR"."rotate_Axis"."di_Actual_Position"',
    "vertical":           'ns=3;s="gtyp_VGR"."vertical_Axis"."di_Actual_Position"',
    "horizontal":         'ns=3;s="gtyp_VGR"."horizontal_Axis"."di_Actual_Position"',
    "rotate_target":      'ns=3;s="gtyp_VGR"."rotate_Axis"."di_Target_Position"',
    "vertical_target":    'ns=3;s="gtyp_VGR"."vertical_Axis"."di_Target_Position"',
    "horizontal_target":  'ns=3;s="gtyp_VGR"."horizontal_Axis"."di_Target_Position"',
    "rotate_reached":     'ns=3;s="gtyp_VGR"."rotate_Axis"."x_Position_Reached"',
    "vertical_reached":   'ns=3;s="gtyp_VGR"."vertical_Axis"."x_Position_Reached"',
    "horizontal_reached": 'ns=3;s="gtyp_VGR"."horizontal_Axis"."x_Position_Reached"',
}

# Shared live state, written by the reader threads, read by the web server.
# Dict values are replaced wholesale (atomic) rather than mutated in place.
LIVE = {
    "opcua": {"connected": False, "error": None},
    "mqtt": {"connected": False, "active": None, "code": None, "target": None, "ts": None},
}


# --- OPC UA reader (its own asyncio loop in a background thread) ------------
async def _opcua_loop():
    while True:
        client = Client(url=OPCUA_URL)
        try:
            await client.connect()
            nodes = {k: client.get_node(nid) for k, nid in OPCUA_TAGS.items()}
            while True:
                snap = {"connected": True, "error": None}
                for k, node in nodes.items():
                    snap[k] = await node.read_value()
                LIVE["opcua"] = snap
                await asyncio.sleep(0.1)
        except Exception as e:
            LIVE["opcua"] = {"connected": False, "error": str(e)}
        finally:
            try:
                await client.disconnect()
            except Exception:
                pass
        await asyncio.sleep(3)      # reconnect after a transient drop


def start_opcua():
    threading.Thread(target=lambda: asyncio.run(_opcua_loop()), daemon=True).start()


# --- MQTT reader (best-effort) ---------------------------------------------
def start_mqtt():
    def on_connect(client, userdata, flags, rc):
        client.subscribe("f/i/state/vgr")

    def on_message(client, userdata, msg):
        try:
            d = json.loads(msg.payload.decode())
        except Exception:
            return
        LIVE["mqtt"] = {"connected": True, "active": bool(d.get("active")),
                        "code": d.get("code"), "target": d.get("target"),
                        "ts": d.get("ts")}

    def run():
        while True:
            try:
                try:
                    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)
                except AttributeError:
                    client = mqtt.Client()
                client.username_pw_set(BROKER_USER, BROKER_PASS)
                client.on_connect = on_connect
                client.on_message = on_message
                client.connect(BROKER_HOST, BROKER_PORT, 60)
                client.loop_forever()
            except Exception:
                LIVE["mqtt"] = {**LIVE["mqtt"], "connected": False}
                time.sleep(3)

    threading.Thread(target=run, daemon=True).start()


INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>VGR Digital Twin</title>
<style>
  body{margin:0;background:#0e1117;color:#e6edf3;font-family:"SF Mono",Menlo,Consolas,monospace;overflow:hidden;}
  #hud{position:fixed;top:12px;left:12px;background:#161b22cc;border:1px solid #2b3444;
       border-radius:10px;padding:12px 14px;font-size:12px;line-height:1.7;min-width:280px;backdrop-filter:blur(4px);}
  #hud h1{font-size:13px;margin:0 0 8px;letter-spacing:.5px;}
  .row{display:flex;justify-content:space-between;gap:14px;}
  .k{color:#8b98a9;} .v{font-variant-numeric:tabular-nums;}
  .sep{border-top:1px solid #2b3444;margin:8px 0;}
  .dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:#6e7781;margin-right:6px;}
  .dot.on{background:#3fb950;box-shadow:0 0 8px #3fb950;}
  .dot.off{background:#e5484d;}
  .reached{color:#3fb950;} .moving{color:#e3b341;}
  #hint{position:fixed;bottom:10px;left:12px;color:#6e7781;font-size:11px;}
</style>
</head>
<body>
<div id="hud">
  <h1>&#129302; VGR DIGITAL TWIN</h1>
  <div class="row"><span class="k"><span id="d-opc" class="dot"></span>OPC UA (PLC)</span><span class="v" id="s-opc">…</span></div>
  <div class="row"><span class="k"><span id="d-mqtt" class="dot"></span>MQTT state</span><span class="v" id="s-mqtt">…</span></div>
  <div class="sep"></div>
  <div class="row"><span class="k">rotate</span><span class="v" id="v-rot">—</span></div>
  <div class="row"><span class="k">vertical</span><span class="v" id="v-ver">—</span></div>
  <div class="row"><span class="k">horizontal</span><span class="v" id="v-hor">—</span></div>
  <div class="sep"></div>
  <div class="row"><span class="k">target (rot/ver/hor)</span><span class="v" id="v-tgt">—</span></div>
  <div class="row"><span class="k">reached</span><span class="v" id="v-rch">—</span></div>
  <div class="row"><span class="k">last MQTT ts</span><span class="v" id="v-ts">—</span></div>
</div>
<div id="hint">drag to orbit · scroll to zoom · rotate 0 = south, increases counter-clockwise (S→E→N→W) · red axis = East (+X), blue axis = North (+Z)</div>

<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/build/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
<script>
const POLL_MS = __POLL__;

// ---- calibration (YOUR measured counts) ----
const ROT_270 = 5331;    // counts for 270 degrees (0 = south)
const VERT_MAX = 2993;   // counts at lowest arm position
const HORIZ_MAX = 3377;  // counts at maximum arm extension
// scene-unit travel these map onto (tweak to taste for looks)
const COLUMN_H = 4.2, MAX_DROP = 3.2, ARM_BASE = 0.7, MAX_REACH = 3.2;
const DEG = Math.PI/180;

// 0 counts = pointing south; counts increase counter-clockwise (S->E->N->W).
// Sign verified against the real robot on screen.
function rotRad(c){ return Math.PI/2 + (c/ROT_270)*270*DEG; }
function vDrop(c){ return (c/VERT_MAX)*MAX_DROP; }        // 0 = top, grows downward
function hExt(c){ return (c/HORIZ_MAX)*MAX_REACH; }       // 0 = retracted

// ---- scene ----
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0e1117);
const camera = new THREE.PerspectiveCamera(55, innerWidth/innerHeight, 0.1, 100);
camera.position.set(7, 6, 7);
const renderer = new THREE.WebGLRenderer({antialias:true});
renderer.setSize(innerWidth, innerHeight); document.body.appendChild(renderer.domElement);
const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.target.set(0, 2, 0);

scene.add(new THREE.AmbientLight(0xffffff, 0.6));
const dir = new THREE.DirectionalLight(0xffffff, 0.8); dir.position.set(6,10,6); scene.add(dir);
const grid = new THREE.GridHelper(16, 16, 0x2b3444, 0x1c2330); scene.add(grid);
scene.add(new THREE.AxesHelper(2));

function box(w,h,d,color){ return new THREE.Mesh(new THREE.BoxGeometry(w,h,d),
  new THREE.MeshStandardMaterial({color})); }

// base that rotates about Y
const baseGroup = new THREE.Group(); scene.add(baseGroup);
const plate = new THREE.Mesh(new THREE.CylinderGeometry(1.5,1.5,0.4,32),
  new THREE.MeshStandardMaterial({color:0xc0392b}));
plate.position.y = 0.2; baseGroup.add(plate);
const column = box(0.5, COLUMN_H, 0.5, 0x9aa4b2); column.position.set(0, COLUMN_H/2+0.4, 0);
baseGroup.add(column);

// carriage that slides down the column
const carriage = new THREE.Group(); baseGroup.add(carriage);
carriage.add(box(0.9,0.5,0.9,0xe74c3c));          // carriage block riding the column
// telescoping horizontal arm: a unit-length beam scaled in X each frame so it
// physically extends and retracts (0 = short stub, max = fully reached out).
const armBeam = box(1, 0.22, 0.22, 0x9aa4b2);
carriage.add(armBeam);
// gripper head sits at the tip of the arm
const head = new THREE.Group(); carriage.add(head);
head.add(box(0.5,0.45,0.5,0x3498db));
const suction = new THREE.Mesh(new THREE.CylinderGeometry(0.12,0.18,0.35,20),
  new THREE.MeshStandardMaterial({color:0xffffff}));
suction.position.y = -0.4; head.add(suction);

// smoothed display values (lerp toward live targets each frame)
const cur = {rot:0, ver:0, hor:0}, tgt = {rot:0, ver:0, hor:0};

function animate(){
  requestAnimationFrame(animate);
  for(const k of ["rot","ver","hor"]) cur[k] += (tgt[k]-cur[k])*0.15;
  baseGroup.rotation.y = rotRad(cur.rot);
  const cy = (0.4 + COLUMN_H) - vDrop(cur.ver);   // top of column, minus drop
  carriage.position.y = cy;
  const armLen = ARM_BASE + hExt(cur.hor);        // grows/shrinks with extension
  armBeam.scale.x = armLen; armBeam.position.x = armLen/2;   // spans column -> tip
  head.position.x = armLen;                       // gripper stays at the tip
  controls.update(); renderer.render(scene, camera);
}
animate();
addEventListener("resize", ()=>{ camera.aspect=innerWidth/innerHeight;
  camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });

// ---- live data ----
const $ = id => document.getElementById(id);
function setDot(id, on){ $(id).className = "dot " + (on?"on":"off"); }
async function poll(){
  try{
    const d = await fetch("/vgr.json", {cache:"no-store"}).then(r=>r.json());
    const o = d.opcua||{}, m = d.mqtt||{};
    setDot("d-opc", o.connected);
    $("s-opc").textContent = o.connected ? "connected" : "offline";
    setDot("d-mqtt", m.connected);
    $("s-mqtt").textContent = m.connected ? (m.active ? "ACTIVE (code "+m.code+")" : "idle") : "offline";

    if(o.connected){
      tgt.rot = o.rotate ?? 0; tgt.ver = o.vertical ?? 0; tgt.hor = o.horizontal ?? 0;
      const deg = (o.rotate/ROT_270*270).toFixed(0);
      $("v-rot").textContent = `${o.rotate}  (${deg}°)`;
      $("v-ver").textContent = `${o.vertical}`;
      $("v-hor").textContent = `${o.horizontal}`;
      $("v-tgt").textContent = `${o.rotate_target} / ${o.vertical_target} / ${o.horizontal_target}`;
      const rc = [o.rotate_reached,o.vertical_reached,o.horizontal_reached];
      $("v-rch").innerHTML = rc.map(x=> x
        ? '<span class="reached">✓</span>' : '<span class="moving">…</span>').join(" ");
      const allReached = rc.every(Boolean);
      suction.material.color.set(m.active ? 0x3fb950 : (allReached ? 0xffffff : 0xe3b341));
    }
    $("v-ts").textContent = m.ts || "—";
  }catch(e){ /* retry next tick */ }
}
poll(); setInterval(poll, POLL_MS);
</script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            html = INDEX_HTML.replace("__POLL__", "100")
            self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")
        elif path == "/vgr.json":
            self._send(200, json.dumps(LIVE).encode("utf-8"), "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def log_message(self, *args):
        pass


def main():
    ap = argparse.ArgumentParser(description="Live 3D digital twin of the VGR robot.")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()

    start_opcua()
    start_mqtt()

    url = f"http://localhost:{args.port}"
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"VGR digital twin at {url}")
    print(f"  OPC UA {OPCUA_URL}  +  MQTT f/i/state/vgr")
    print("  (needs the factory WiFi; Ctrl+C to stop)\n")
    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
