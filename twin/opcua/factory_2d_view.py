"""
factory_2d_view.py

A live, animated 2D digital-twin view of the fischertechnik smart factory,
viewable in your web browser.

TWO MODES
---------
1) LIVE (default) - reads the files that `live_data_feed.py` writes:
       factory_state.json    -> current state of every station/sensor/stock
       factory_events.jsonl  -> timestamped history (drives the event ticker)

       Terminal 1:  python3 live_data_feed.py
       Terminal 2:  python3 factory_2d_view.py

2) REPLAY - plays back a previously-recorded .jsonl log as if it were happening
   now, so you can review a past test run in the 2D view with play/pause, speed
   control and a scrub bar. No factory or feed needed.

       python3 factory_2d_view.py --replay factory_events.jsonl
       python3 factory_2d_view.py --replay old_run.jsonl --speed 4

Standard library only - no pip installs. Stop with Ctrl+C.
"""

import os
import json
import time
import bisect
import argparse
import threading
import webbrowser
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "factory_state.json")
EVENTS_FILE = os.path.join(HERE, "factory_events.jsonl")
PORT = 8420
POLL_MS = 500          # how often the browser re-fetches state
TICKER_LINES = 40      # how many recent events to show
SESSION_GAP = 120.0    # a gap this long (seconds) between events starts a new session

STATIONS = {
    "hbw": "High-Bay Warehouse",
    "vgr": "Vacuum Gripper",
    "mpo": "Processing Station",
    "sld": "Sorting Line",
    "dsi": "Input Station",
    "dso": "Output Station",
}

# Set by main()/loader when replaying. None means live mode.
PB = None                # the active Playback (scoped to one session, or whole file)
SOURCE = None            # the full loaded recording: {name, records, epochs, sessions}
ACTIVE_SESSION = None    # which session PB is scoped to: an int index, or "all"


def tail(path, n):
    """Return the last n non-blank lines of a text file (best-effort)."""
    try:
        with open(path) as f:
            lines = f.readlines()
    except OSError:
        return []
    return [ln.strip() for ln in lines[-n:] if ln.strip()]


# ---------------------------------------------------------------------------
# Replay engine: reconstruct factory state from a recorded event log and step
# through it in real time.
# ---------------------------------------------------------------------------

def parse_epoch(ts):
    """ISO-8601 string -> float epoch seconds, or None if unparseable."""
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def occupied(wp):
    """A warehouse slot is only really occupied if its workpiece has content."""
    if not wp:
        return False
    return bool((wp.get("type") or "").strip() or (wp.get("id") or "").strip())


def blank_state(source):
    return {
        "meta": {"updated": None, "updated_epoch": None,
                 "event_count": 0, "source_broker": source},
        "stations": {}, "sensors": {}, "stock": {},
        "orders": {}, "nfc": {}, "raw": {},
    }


def apply_event(state, ev):
    """Fold one recorded event into the running state (mirrors the handlers in
    live_data_feed.py so a replay looks identical to a live run)."""
    topic, data, ts = ev["topic"], ev.get("data") or {}, ev["ts"]

    if topic.startswith("f/i/state/"):
        station = data.get("station", topic.split("/")[-1])
        state["stations"][station] = {
            "name": STATIONS.get(station, station.upper()),
            "active": bool(data.get("active")),
            "code": data.get("code"),
            "description": (data.get("description") or "").strip(),
            "target": (data.get("target") or "").strip(),
            "seen": ts,
        }
    elif topic == "f/i/stock":
        items = data.get("stockItems", [])
        slots, filled = [], 0
        for item in items:
            wp = item.get("workpiece") or {}
            occ = occupied(wp)
            slots.append({
                "location": item.get("location", "?"),
                "occupied": occ,
                "workpiece": ({"type": (wp.get("type") or None),
                               "state": (wp.get("state") or None),
                               "id": (wp.get("id") or None)} if occ else None),
            })
            filled += 1 if occ else 0
        state["stock"] = {"slots": slots, "occupied": filled,
                          "capacity": len(items), "seen": ts}
    elif topic == "f/i/order":
        state["orders"] = {**data, "seen": ts}
    elif topic == "f/i/nfc/ds":
        state["nfc"] = {**data, "seen": ts}
    elif topic == "i/bme680":
        state["sensors"]["environment"] = {
            "temperature_c": data.get("t"), "humidity_pct": data.get("h"),
            "pressure_hpa": data.get("p"), "air_quality_index": data.get("iaq"),
            "air_quality_label": _aq_label(data.get("iaq")), "seen": ts,
        }
    elif topic == "i/ldr":
        state["sensors"]["brightness"] = {
            "brightness_pct": data.get("br"),
            "raw_resistance": data.get("ldr"), "seen": ts,
        }
    else:
        state["raw"][topic] = {"payload": data, "seen": ts}


def _aq_label(iaq):
    if iaq is None:
        return ""
    if iaq <= 50:
        return "good"
    if iaq <= 100:
        return "moderate"
    if iaq <= 150:
        return "unhealthy for sensitive groups"
    if iaq <= 200:
        return "unhealthy"
    if iaq <= 300:
        return "very unhealthy"
    return "hazardous"


# ---------------------------------------------------------------------------
# Cycle-time analysis. Fold an event stream into per-order timings so the
# dashboard can show baseline cycle times and the current order's flow.
#
# Instrument (the fixed measurement rule):
#   * order START  = f/i/order state becomes "ORDERED"  (the demand signal)
#   * order END    = f/i/order state becomes "SHIPPED"
#   * stage times  = how long each station was `active` inside that window
#   * flow         = the order stations first went active (material flow)
#   * PLC response = time from ORDERED to the warehouse (hbw) first going active
# Timestamps use the factory's own inner data.ts. Orders are treated as
# serialized (one ORDERED..SHIPPED at a time), which matches the kit's PLC.
# ---------------------------------------------------------------------------

def _event_ts(e):
    d = e.get("data") or {}
    return d.get("ts") or e.get("ts")


def compute_cycles(events):
    evs = []
    for e in events:
        d = e.get("data") or {}
        ts = _event_ts(e)
        ep = parse_epoch(ts)
        if ep is not None:
            evs.append((ep, ts, e.get("topic", ""), d))
    evs.sort(key=lambda x: x[0])

    open_active = {}          # station -> (start_ep, code)
    intervals = []            # (station, code, start_ep, end_ep)
    activations = []          # (station, code, ep, ts) rising edges, in order
    order_marks = []          # (state, ep, ts)
    for ep, ts, topic, d in evs:
        if topic.startswith("f/i/state/"):
            st = d.get("station", topic.split("/")[-1])
            if bool(d.get("active")) and st not in open_active:
                open_active[st] = (ep, d.get("code"))
                activations.append((st, d.get("code"), ep, ts))
            elif not d.get("active") and st in open_active:
                s, c = open_active.pop(st)
                intervals.append((st, c, s, ep))
        elif topic == "f/i/order":
            order_marks.append((d.get("state") or d.get("type"), ep, ts))

    last_ep = evs[-1][0] if evs else 0.0
    for st, (s, c) in open_active.items():       # close still-active intervals
        intervals.append((st, c, s, last_ep))

    # pair ORDERED..SHIPPED into cycles; a trailing ORDERED is the live order
    cycles, cur = [], None
    for state, ep, ts in order_marks:
        if state == "ORDERED" and cur is None:
            cur = {"start_ep": ep, "start_ts": ts}
        elif state == "SHIPPED" and cur is not None:
            cur["end_ep"], cur["end_ts"] = ep, ts
            cycles.append(cur)
            cur = None

    def stages(s_ep, e_ep):
        agg = {}
        for st, c, s, e in intervals:
            ov = min(e, e_ep) - max(s, s_ep)
            if ov > 0:
                agg[st] = agg.get(st, 0.0) + ov
        return agg

    def flow(s_ep, e_ep):
        return [a for a in activations if s_ep <= a[2] <= e_ep]

    out = []
    for i, cy in enumerate(cycles, 1):
        s_ep, e_ep = cy["start_ep"], cy["end_ep"]
        fl = flow(s_ep, e_ep)
        hbw_first = next((a[2] for a in fl if a[0] == "hbw"), None)
        st_agg = stages(s_ep, e_ep)
        out.append({
            "order": i, "start_ts": cy["start_ts"], "end_ts": cy["end_ts"],
            "total_s": round(e_ep - s_ep, 1),
            "response_latency_s": round(hbw_first - s_ep, 1) if hbw_first else None,
            "stages": [{"station": st, "name": STATIONS.get(st, st.upper()),
                        "seconds": round(sec, 1)}
                       for st, sec in sorted(st_agg.items(), key=lambda kv: -kv[1])],
        })

    current = None
    if cur is not None:
        fl = flow(cur["start_ep"], last_ep)
        current = {
            "start_ts": cur["start_ts"],
            "elapsed_s": round(last_ep - cur["start_ep"], 1),
            "active_station": next(iter(open_active), None),
            "flow": [{"station": a[0], "name": STATIONS.get(a[0], a[0].upper()),
                      "code": a[1], "ts": a[3]} for a in fl],
        }

    totals = [c["total_s"] for c in out]
    summary = {"count": len(out),
               "avg_total_s": round(sum(totals) / len(totals), 1) if totals else None,
               "min_total_s": min(totals) if totals else None,
               "max_total_s": max(totals) if totals else None}
    return {"cycles": out[-8:], "current": current, "summary": summary}


# The "big" discrete events worth pinning as clickable milestones.
_ORDER_LABELS = {"ORDERED": "Order placed", "IN_PROCESS": "Order processing",
                 "SHIPPED": "Order delivered", "WAITING_FOR_ORDER": "Waiting for order"}


def compute_milestones(events):
    """Pick out the notable, discrete events (order lifecycle + NFC scans),
    de-duplicating order heartbeats so only real state changes appear. Each
    carries the outer `ts` used for seeking, so a click can jump straight to it."""
    out, last_order = [], None
    for e in events:
        topic, d = e.get("topic", ""), (e.get("data") or {})
        ts = e.get("ts")                       # outer ts = the playback timeline
        if topic == "f/i/order":
            state = d.get("state") or d.get("type")
            if state and state != last_order:
                last_order = state
                # only the real order actions, not the idle "waiting" reset
                if state in ("ORDERED", "IN_PROCESS", "SHIPPED"):
                    out.append({"ts": ts, "kind": "order", "state": state,
                                "label": _ORDER_LABELS.get(state, state)})
        elif topic == "f/i/nfc/ds":
            w = d.get("workpiece") or {}
            typ = (w.get("type") or "").strip()
            if typ and typ.upper() != "NONE":     # skip empty/failed tag reads
                label = f"Workpiece scanned: {typ} {w.get('state', '')}".strip()
                out.append({"ts": ts, "kind": "nfc", "label": label})
    return out


# Live analysis reads the events file but scopes to the CURRENT session only -
# the latest run, split off by the downtime gap - so cycle times and key events
# start EMPTY each run instead of showing the whole recorded history.
_live_cache = {"key": None, "records": []}


def _live_session_records():
    try:
        key = (os.path.getmtime(EVENTS_FILE), os.path.getsize(EVENTS_FILE))
    except OSError:
        return _live_cache["records"]
    if _live_cache["key"] != key:
        try:
            with open(EVENTS_FILE) as f:
                recs = Playback._records_from_lines(f)
        except OSError:
            return _live_cache["records"]
        withep = [(parse_epoch(r.get("ts")), r) for r in recs]
        withep = [(ep, r) for ep, r in withep if ep is not None]
        withep.sort(key=lambda x: x[0])
        srecs = [r for _, r in withep]
        eps = [ep for ep, _ in withep]
        bounds = _sessions_from_epochs(eps)
        _live_cache["key"] = key
        _live_cache["records"] = srecs[bounds[-1][0]:bounds[-1][1]] if bounds else []
    return _live_cache["records"]


def live_cycles_json():
    return json.dumps(compute_cycles(_live_session_records()))


def live_milestones_json():
    return json.dumps(compute_milestones(_live_session_records()))


class Playback:
    def __init__(self, records, name, speed=1.0):
        self.name = name
        self.source = f"replay: {name}"
        self.events = []
        for rec in records:
            ts = rec.get("ts")
            ep = parse_epoch(ts)
            if ep is None:
                continue
            self.events.append({"ts": ts, "topic": rec.get("topic", ""),
                                "data": rec.get("data") or {}, "epoch": ep})
        self.events.sort(key=lambda e: e["epoch"])
        self.epochs = [e["epoch"] for e in self.events]
        self.n = len(self.events)
        self.t0 = self.epochs[0] if self.n else 0.0
        self.duration = (self.epochs[-1] - self.t0) if self.n else 0.0

        self.pos = 0.0                 # seconds into the timeline
        self.speed = speed
        self.playing = self.n > 0
        self.last_wall = time.monotonic()

        self._built_index = 0
        self._state = blank_state(self.source)
        self._idx = 0
        self.lock = threading.Lock()

    @staticmethod
    def _records_from_lines(lines):
        recs = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                recs.append(json.loads(line))
            except json.JSONDecodeError:
                pass
        return recs

    @classmethod
    def from_path(cls, path, speed=1.0):
        with open(path) as f:
            recs = cls._records_from_lines(f)
        return cls(recs, os.path.basename(path), speed)

    @classmethod
    def from_text(cls, text, name, speed=1.0):
        return cls(cls._records_from_lines(text.splitlines()), name, speed)

    # --- internals (assume lock is held) -----------------------------------
    def _advance_clock(self):
        now = time.monotonic()
        if self.playing:
            self.pos += (now - self.last_wall) * self.speed
            if self.pos >= self.duration:
                self.pos = self.duration
                self.playing = False
        self.last_wall = now

    def _build_to(self, index):
        if index < self._built_index:            # seeked backward -> rebuild
            self._state = blank_state(self.source)
            self._built_index = 0
        for i in range(self._built_index, index):
            apply_event(self._state, self.events[i])
        self._built_index = index

    def _sync(self):
        self._advance_clock()
        idx = bisect.bisect_right(self.epochs, self.t0 + self.pos)
        self._build_to(idx)
        if idx > 0:
            self._state["meta"]["updated"] = self.events[idx - 1]["ts"]
            self._state["meta"]["updated_epoch"] = self.epochs[idx - 1]
        self._state["meta"]["event_count"] = idx
        self._idx = idx
        return idx

    # --- public API ---------------------------------------------------------
    def state_json(self):
        with self.lock:
            self._sync()
            return json.dumps(self._state)

    def events_json(self, n):
        with self.lock:
            idx = self._sync()
            sl = self.events[max(0, idx - n):idx]
            return json.dumps([{"ts": e["ts"], "topic": e["topic"], "data": e["data"]}
                               for e in sl])

    def status(self):
        with self.lock:
            idx = self._sync()
            return {"mode": "replay", "playing": self.playing, "speed": self.speed,
                    "pos": self.pos, "duration": self.duration,
                    "index": idx, "total": self.n,
                    "current_ts": self.events[idx - 1]["ts"] if idx > 0 else None,
                    "file": self.name}

    def cycles_json(self):
        with self.lock:
            idx = self._sync()
            return json.dumps(compute_cycles(self.events[:idx]))

    def control(self, action, value):
        with self.lock:
            self._advance_clock()
            if action == "play":
                self.playing = self.pos < self.duration
            elif action == "pause":
                self.playing = False
            elif action == "restart":
                self.pos = 0.0
                self.playing = self.n > 0
            elif action == "speed":
                try:
                    self.speed = max(0.1, min(64.0, float(value)))
                except (TypeError, ValueError):
                    pass
            elif action == "seek":
                try:
                    self.pos = max(0.0, min(self.duration, float(value) * self.duration))
                except (TypeError, ValueError):
                    pass
            elif action == "seekts":          # jump to an absolute event time (epoch s)
                try:
                    self.pos = max(0.0, min(self.duration, float(value) - self.t0))
                except (TypeError, ValueError):
                    pass
            self.last_wall = time.monotonic()


INDEX_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Smart Factory - Live 2D Twin</title>
<style>
  :root{
    --bg:#0e1117; --panel:#161b22; --panel2:#1c2330; --edge:#2b3444;
    --txt:#e6edf3; --dim:#8b98a9; --active:#3fb950; --idle:#6e7781;
    --hbw:#8957e5; --mpo:#b8a534; --sld:#3b82f6; --vgr:#e5484d; --dps:#3fb950;
    --white:#f0f3f6; --red:#e5484d; --blue:#3b82f6;
  }
  *{box-sizing:border-box;}
  body{margin:0;background:var(--bg);color:var(--txt);height:100vh;
       display:flex;flex-direction:column;overflow:hidden;
       font-family:"SF Mono",Menlo,Consolas,monospace;}
  header{display:flex;align-items:center;gap:16px;padding:10px 18px;
         background:var(--panel);border-bottom:1px solid var(--edge);}
  header h1{font-size:16px;margin:0;font-weight:700;letter-spacing:.5px;}
  .status{margin-left:auto;display:flex;align-items:center;gap:8px;font-size:12px;color:var(--dim);}
  .dot{width:10px;height:10px;border-radius:50%;background:var(--idle);}
  .dot.live{background:var(--active);box-shadow:0 0 10px var(--active);animation:pulse 1.6s infinite;}
  .dot.stale{background:#d29922;}
  .dot.off{background:var(--vgr);}
  .srcbar{display:flex;gap:8px;margin-left:8px;}
  .srcbar button{background:#21334a;color:var(--txt);border:1px solid var(--edge);
                 border-radius:6px;padding:5px 12px;cursor:pointer;font-family:inherit;font-size:12px;}
  .srcbar button:hover{background:#2a4160;}
  #btn-live{border-color:#2ea043;}
  #loadpanel{display:none;position:fixed;top:52px;right:16px;z-index:50;width:340px;
             background:var(--panel2);border:1px solid var(--edge);border-radius:10px;
             padding:12px;box-shadow:0 12px 30px #000a;}
  #loadpanel .lp-h{font-size:12px;font-weight:700;margin-bottom:8px;}
  .lp-file{display:flex;justify-content:space-between;width:100%;text-align:left;
           background:#0d1117;border:1px solid var(--edge);border-radius:6px;color:var(--txt);
           padding:7px 10px;margin-bottom:5px;cursor:pointer;font-family:inherit;font-size:12px;}
  .lp-file:hover{border-color:var(--sld);background:#10203a;}
  .lp-file .lp-sz{color:var(--dim);}
  .lp-empty{color:var(--dim);font-size:11px;padding:4px 0 8px;}
  .lp-up{display:block;margin-top:8px;font-size:11px;color:var(--dim);cursor:pointer;
         border-top:1px solid var(--edge);padding-top:10px;}
  .lp-up input{display:block;margin-top:6px;font-size:11px;color:var(--txt);}
  #lp-msg{font-size:11px;color:var(--sld);margin-top:8px;min-height:14px;}
  /* playback controls (replay mode only) */
  #controls{display:none;align-items:center;gap:12px;padding:8px 18px;
            background:var(--panel2);border-bottom:1px solid var(--edge);font-size:12px;}
  #controls button{background:#21334a;color:var(--txt);border:1px solid var(--edge);
                   border-radius:6px;padding:5px 12px;cursor:pointer;font-family:inherit;font-size:12px;}
  #controls button:hover{background:#2a4160;}
  #controls select{background:#21334a;color:var(--txt);border:1px solid var(--edge);
                   border-radius:6px;padding:4px 6px;font-family:inherit;}
  #pb-seek{flex:1;accent-color:var(--sld);cursor:pointer;}
  #pb-time{color:var(--dim);white-space:nowrap;}
  .main{display:flex;flex:1;min-height:0;}
  #stagewrap{flex:2;position:relative;padding:18px;}
  #stage{position:relative;width:100%;height:100%;
         background:radial-gradient(circle at 50% 40%,#141b26,#0e1117);
         border:1px solid var(--edge);border-radius:10px;overflow:hidden;}
  #links{position:absolute;inset:0;width:100%;height:100%;}
  .link{stroke:#2b3444;stroke-width:1.2;fill:none;}
  .link.hot{stroke:#3fb950;stroke-width:1.6;stroke-dasharray:3 3;
            animation:flow 1s linear infinite;filter:drop-shadow(0 0 3px #3fb95088);}
  @keyframes flow{to{stroke-dashoffset:-12;}}
  .station{position:absolute;background:var(--panel2);border:1.5px solid var(--edge);
           border-radius:9px;padding:8px 10px;transition:box-shadow .4s,border-color .4s,transform .2s;}
  .station .nm{font-size:12px;font-weight:700;}
  .station .meta{font-size:10.5px;color:var(--dim);margin-top:3px;line-height:1.5;}
  .badge{display:inline-block;font-size:10px;font-weight:700;padding:1px 7px;
         border-radius:10px;background:#30363d;color:var(--idle);margin-top:5px;}
  .station.on{border-color:var(--active);box-shadow:0 0 0 1px var(--active),0 0 22px #3fb95055;
              animation:glow 1.5s ease-in-out infinite;}
  .station.on .badge{background:#12351d;color:var(--active);}
  @keyframes glow{0%,100%{box-shadow:0 0 0 1px var(--active),0 0 16px #3fb95044;}
                  50%{box-shadow:0 0 0 1px var(--active),0 0 30px #3fb95099;}}
  @keyframes pulse{0%,100%{opacity:1;}50%{opacity:.35;}}
  .tag{position:absolute;top:6px;right:8px;width:9px;height:9px;border-radius:2px;opacity:.8;}
  .grid{display:grid;grid-template-columns:repeat(3,1fr);gap:4px;margin-top:7px;}
  .cell{aspect-ratio:1;border-radius:4px;background:#0d1117;border:1px solid #30363d;
        display:flex;align-items:center;justify-content:center;font-size:9px;color:#0d1117;
        transition:background .5s,box-shadow .5s;}
  .cell.wp{color:#0d1117;font-weight:700;}
  .cell.WHITE{background:var(--white);box-shadow:0 0 8px #ffffff33;}
  .cell.RED{background:var(--red);box-shadow:0 0 8px #e5484d55;color:#fff;}
  .cell.BLUE{background:var(--blue);box-shadow:0 0 8px #3b82f655;color:#fff;}
  #side{flex:1;min-width:320px;max-width:430px;display:flex;flex-direction:column;
        border-left:1px solid var(--edge);background:var(--panel);}
  .card{padding:12px 16px;border-bottom:1px solid var(--edge);}
  .card h2{font-size:11px;letter-spacing:1px;color:var(--dim);margin:0 0 9px;text-transform:uppercase;}
  .gauges{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
  .gauge{background:var(--panel2);border:1px solid var(--edge);border-radius:8px;padding:9px 11px;}
  .gauge .v{font-size:20px;font-weight:700;}
  .gauge .l{font-size:10px;color:var(--dim);margin-top:2px;}
  .kv{display:flex;justify-content:space-between;font-size:12px;padding:3px 0;}
  .kv .k{color:var(--dim);}
  .aq{font-size:10px;padding:1px 7px;border-radius:9px;font-weight:700;}
  .aq.good{background:#12351d;color:#3fb950;}
  .aq.moderate{background:#3a3312;color:#d4b106;}
  .aq.bad{background:#3a1518;color:#e5484d;}
  #ticker{flex:1;overflow:hidden;display:flex;flex-direction:column;}
  #tickerlist{overflow-y:auto;padding:4px 10px;font-size:11.5px;}
  .ev{display:flex;gap:9px;padding:4px 4px;border-bottom:1px solid #1c2330;animation:slidein .45s ease;}
  @keyframes slidein{from{opacity:0;transform:translateX(-12px);}to{opacity:1;transform:none;}}
  .ev .t{color:var(--dim);flex:0 0 auto;}
  .ev .cat{flex:0 0 62px;font-weight:700;}
  .ev .cat.STATION{color:#58a6ff;}.ev .cat.STOCK{color:#d2a8ff;}
  .ev .cat.ORDER{color:#e3b341;}.ev .cat.NFC{color:#79c0ff;}
  .ev .cat.ENV,.ev .cat.LIGHT{color:#39c5cf;}
  .ev .d{color:var(--txt);}
  /* bottom row: cycle time / order flow / event log */
  #bottom{display:flex;height:35vh;min-height:210px;border-top:1px solid var(--edge);}
  .bpanel{flex:1;min-width:0;display:flex;flex-direction:column;
          border-right:1px solid var(--edge);background:var(--panel);}
  .bpanel:last-child{border-right:none;}
  .bpanel h2{font-size:11px;letter-spacing:1px;color:var(--dim);margin:0;
             padding:10px 14px 4px;text-transform:uppercase;}
  .bpanel .sub{font-size:10.5px;color:var(--dim);padding:0 14px 6px;}
  .bpanel .body{flex:1;overflow-y:auto;padding:4px 12px 10px;}
  .cyc{border:1px solid var(--edge);border-radius:8px;padding:8px 10px;
       margin-bottom:8px;background:var(--panel2);}
  .cyc .top{display:flex;justify-content:space-between;font-size:12px;font-weight:700;}
  .cyc.live{border-color:var(--active);box-shadow:0 0 0 1px var(--active),0 0 16px #3fb95033;
            animation:glow 1.6s ease-in-out infinite;}
  .cyc.live .top{color:var(--active);}
  #live-timer{font-variant-numeric:tabular-nums;}
  .cyc .csub{font-size:10px;color:var(--dim);margin:2px 0 6px;}
  .bar{display:flex;align-items:center;gap:6px;font-size:10px;margin:2px 0;}
  .bar .lb{flex:0 0 92px;color:var(--dim);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
  .bar .track{flex:1;height:8px;background:#0d1117;border-radius:4px;overflow:hidden;}
  .bar .fill{height:100%;border-radius:4px;transition:width .4s;}
  .bar .val{flex:0 0 52px;text-align:right;}
  .step{display:flex;align-items:center;gap:10px;padding:7px 10px;margin-bottom:6px;
        border-radius:7px;border:1px solid var(--edge);background:var(--panel2);
        opacity:.4;transition:opacity .3s,border-color .3s,box-shadow .3s;}
  .step.done{opacity:1;border-color:#2ea043;}
  .step.active{opacity:1;border-color:var(--active);
               box-shadow:0 0 14px #3fb95044;animation:glow 1.5s infinite;}
  .step .ic{width:11px;height:11px;border-radius:50%;background:var(--idle);flex:0 0 auto;}
  .step.done .ic{background:#2ea043;}
  .step.active .ic{background:var(--active);}
  .step .nm{flex:1;font-size:12px;}
  .step .ts{font-size:10px;color:var(--dim);}
  /* session picker + key-events toggle + clickable events */
  #pb-session{max-width:250px;}
  .tog{float:right;display:inline-flex;gap:4px;}
  .tog button{background:#0d1117;color:var(--dim);border:1px solid var(--edge);border-radius:5px;
              padding:2px 8px;font-size:10px;cursor:pointer;font-family:inherit;}
  .tog button.on{background:#21334a;color:var(--txt);border-color:var(--sld);}
  body.replay .ev,body.replay .cyc{cursor:pointer;}
  body.replay .ev:hover,body.replay .cyc:hover{background:#182238;}
  .ev.key{border-left:3px solid var(--active);padding-left:6px;cursor:pointer;}
  .ev.key .cat{color:var(--active);}
  .ev.key.nfc{border-left-color:#79c0ff;}
  .ev.key.nfc .cat{color:#79c0ff;}
  #keylist .ev:hover{background:#182238;}
</style>
</head>
<body>
<header>
  <h1>&#9881; FISCHERTECHNIK SMART FACTORY &mdash; 2D TWIN</h1>
  <div class="srcbar">
    <button id="btn-load">&#128193; Load recording</button>
    <button id="btn-live" style="display:none;">&#9679; Back to live</button>
  </div>
  <div class="status"><span id="dot" class="dot"></span><span id="statustext">connecting&hellip;</span></div>
</header>
<div id="loadpanel">
  <div class="lp-h">Load a recording to replay</div>
  <div id="lp-files"></div>
  <label class="lp-up">&#8593; Upload a .jsonl from your computer
    <input type="file" id="lp-file" accept=".jsonl,.json,.txt">
  </label>
  <div id="lp-msg"></div>
</div>
<div id="controls">
  <button id="pb-play">&#9208; Pause</button>
  <button id="pb-restart">&#8635; Restart</button>
  <span>session</span>
  <select id="pb-session"></select>
  <span>speed</span>
  <select id="pb-speed">
    <option value="0.5">0.5&times;</option>
    <option value="1" selected>1&times;</option>
    <option value="2">2&times;</option>
    <option value="4">4&times;</option>
    <option value="8">8&times;</option>
    <option value="16">16&times;</option>
    <option value="32">32&times;</option>
  </select>
  <input type="range" id="pb-seek" min="0" max="1000" value="0">
  <span id="pb-time">--</span>
</div>
<div class="main">
  <div id="stagewrap">
    <div id="stage">
      <svg id="links" viewBox="0 0 100 100" preserveAspectRatio="none">
        <line class="link" data-a="hbw" data-b="vgr" x1="15" y1="45" x2="49" y2="54"></line>
        <line class="link" data-a="vgr" data-b="mpo" x1="49" y1="54" x2="51" y2="20"></line>
        <line class="link" data-a="mpo" data-b="sld" x1="51" y1="20" x2="85" y2="50"></line>
        <line class="link" data-a="vgr" data-b="dso" x1="49" y1="54" x2="57" y2="84"></line>
        <line class="link" data-a="vgr" data-b="dsi" x1="49" y1="54" x2="38" y2="84"></line>
      </svg>
    </div>
  </div>
  <div id="side">
    <div class="card"><h2>Environment &amp; Light</h2>
      <div class="gauges">
        <div class="gauge"><div class="v" id="g-temp">--</div><div class="l">temperature &deg;C</div></div>
        <div class="gauge"><div class="v" id="g-hum">--</div><div class="l">humidity %</div></div>
        <div class="gauge"><div class="v" id="g-pres">--</div><div class="l">pressure hPa</div></div>
        <div class="gauge"><div class="v" id="g-light">--</div><div class="l">brightness %</div></div>
      </div>
      <div class="kv" style="margin-top:9px;"><span class="k">air quality index</span>
        <span><span id="g-iaq">--</span> <span id="g-aq" class="aq"></span></span></div>
    </div>
    <div class="card"><h2>Order &amp; Warehouse</h2>
      <div class="kv"><span class="k">order state</span><span id="o-state">&mdash;</span></div>
      <div class="kv"><span class="k">order type</span><span id="o-type">&mdash;</span></div>
      <div class="kv"><span class="k">warehouse</span><span id="o-stock">&mdash;</span></div>
      <div class="kv"><span class="k">last NFC tag</span><span id="o-nfc">&mdash;</span></div>
    </div>
  </div>
</div>
<div id="bottom">
  <div class="bpanel">
    <h2>Cycle Times</h2>
    <div class="sub" id="cyc-summary">no completed orders yet</div>
    <div class="body" id="cyc-body"></div>
  </div>
  <div class="bpanel">
    <h2>Order Flow</h2>
    <div class="sub" id="flow-head">no order in progress</div>
    <div class="body" id="flow-body"></div>
  </div>
  <div class="bpanel">
    <h2>Event Log <span class="tog"><button id="tog-all" class="on">All</button><button id="tog-key">Key events</button></span></h2>
    <div class="body" id="tickerlist"></div>
    <div class="body" id="keylist" style="display:none;"></div>
  </div>
</div>
<script>
const POLL_MS = __POLL_MS__;
const NAMES = {dsi:"Input Station", dso:"Output Station", hbw:"High-Bay Warehouse",
               vgr:"Vacuum Gripper", mpo:"Processing Station", sld:"Sorting Line"};
const TINT  = {dsi:"var(--dps)", dso:"var(--dps)", hbw:"var(--hbw)",
               vgr:"var(--vgr)", mpo:"var(--mpo)", sld:"var(--sld)"};
const POS = {
  hbw:{l:4, t:14, w:20, h:62}, mpo:{l:31,t:6, w:40, h:26}, sld:{l:76,t:26, w:20, h:50},
  vgr:{l:40,t:40, w:19, h:28}, dsi:{l:29,t:78, w:16, h:17}, dso:{l:49,t:78, w:16, h:17},
};

const stage = document.getElementById("stage");
const cards = {};
for(const code of Object.keys(POS)){
  const p = POS[code];
  const el = document.createElement("div");
  el.className = "station";
  el.style.left=p.l+"%"; el.style.top=p.t+"%"; el.style.width=p.w+"%"; el.style.height=p.h+"%";
  el.style.borderColor = TINT[code];
  el.innerHTML = `<span class="tag" style="background:${TINT[code]}"></span>
    <div class="nm">${NAMES[code]}</div><div class="meta" data-meta></div>
    <span class="badge" data-badge>&mdash;</span>
    ${code==="hbw" ? '<div class="grid" data-grid></div>' : ''}`;
  stage.appendChild(el);
  cards[code] = el;
}

function occupied(wp){ if(!wp) return false;
  return !!((wp.type||"").trim() || (wp.id||"").trim()); }

function renderStations(st){
  const stations = st.stations || {};
  for(const code of Object.keys(POS)){
    const s = stations[code], el = cards[code];
    const meta = el.querySelector("[data-meta]"), badge = el.querySelector("[data-badge]");
    if(!s){ el.classList.remove("on"); badge.textContent="no data"; meta.innerHTML=""; continue; }
    el.classList.toggle("on", !!s.active);
    badge.textContent = s.active ? "ACTIVE" : "idle";
    let m = `code ${s.code}`;
    if(s.description) m += `<br>${s.description}`;
    if(s.target) m += `<br>&rarr; ${s.target}`;
    meta.innerHTML = m;
  }
  document.querySelectorAll(".link").forEach(l=>{
    const a=stations[l.dataset.a], b=stations[l.dataset.b];
    l.classList.toggle("hot", (a&&a.active)||(b&&b.active));
  });
  const grid = cards.hbw.querySelector("[data-grid]");
  const slots = (st.stock && st.stock.slots) || [];
  if(grid){
    grid.innerHTML = "";
    for(const slot of slots){
      const wp = slot.workpiece;
      const c = document.createElement("div");
      const type = wp && occupied(wp) ? (wp.type||"").toUpperCase() : "";
      c.className = "cell" + (type ? " wp "+type : "");
      c.textContent = slot.location || "";
      c.title = type ? `${slot.location}: ${type} ${(wp.state||"")}` : `${slot.location}: empty`;
      grid.appendChild(c);
    }
  }
}

function renderSide(st){
  const env = (st.sensors||{}).environment, light = (st.sensors||{}).brightness;
  const set=(id,v)=>document.getElementById(id).textContent=(v==null?"--":v);
  if(env){ set("g-temp",env.temperature_c); set("g-hum",env.humidity_pct);
    set("g-pres",env.pressure_hpa); set("g-iaq",env.air_quality_index);
    const aq=document.getElementById("g-aq"); aq.textContent=env.air_quality_label||"";
    const iaq=env.air_quality_index||0;
    aq.className="aq "+(iaq<=50?"good":iaq<=150?"moderate":"bad");
  }
  if(light){ set("g-light", light.brightness_pct); }
  const o=st.orders||{}, n=(st.nfc||{}).workpiece, stock=st.stock;
  document.getElementById("o-state").textContent = o.state || "—";
  document.getElementById("o-type").textContent = o.type || "none";
  document.getElementById("o-stock").textContent = stock ? `${stock.occupied}/${stock.capacity} slots` : "—";
  document.getElementById("o-nfc").textContent = n ? `${n.type||"?"} ${n.state||""}` : "—";
}

function updateStatusLive(st){
  const dot=document.getElementById("dot"), txt=document.getElementById("statustext");
  const upd=(st.meta||{}).updated;
  if(!upd){ dot.className="dot off"; txt.textContent="waiting for factory_state.json"; return; }
  const age=(Date.now()-new Date(upd).getTime())/1000;
  if(age<8){ dot.className="dot live"; txt.textContent="LIVE  ·  "+((st.meta.event_count)||0)+" events"; }
  else if(age<60){ dot.className="dot stale"; txt.textContent="idle  ·  last change "+Math.round(age)+"s ago"; }
  else { dot.className="dot off"; txt.textContent="feed offline?  last change "+Math.round(age)+"s ago"; }
}

// ---- playback controls ----
let controlsInit=false, seeking=false, lastIdx=-1;
function fmt(sec){ sec=Math.max(0,Math.floor(sec)); const m=Math.floor(sec/60), s=sec%60;
  return m+":"+String(s).padStart(2,"0"); }
function initControls(){
  document.getElementById("controls").style.display="flex";
  const play=document.getElementById("pb-play");
  play.onclick=()=>fetch("/control?action="+(play.dataset.playing==="1"?"pause":"play"));
  document.getElementById("pb-restart").onclick=()=>{ lastIdx=1e9; fetch("/control?action=restart"); };
  document.getElementById("pb-speed").onchange=e=>fetch("/control?action=speed&value="+e.target.value);
  const seek=document.getElementById("pb-seek");
  seek.oninput=()=>{ seeking=true; };
  seek.onchange=e=>{ fetch("/control?action=seek&value="+(e.target.value/1000)); seeking=false; };
  controlsInit=true;
}
function updatePlayback(pb){
  if(!controlsInit) initControls();
  const play=document.getElementById("pb-play");
  play.dataset.playing = pb.playing?"1":"0";
  play.innerHTML = pb.playing?"&#9208; Pause":"&#9654; Play";
  if(!seeking) document.getElementById("pb-seek").value = pb.duration? Math.round(pb.pos/pb.duration*1000):0;
  const clock = tFull(pb.current_ts);
  document.getElementById("pb-time").textContent =
    clock+"   ("+fmt(pb.pos)+" / "+fmt(pb.duration)+")   ["+pb.index+"/"+pb.total+"]";
  const dot=document.getElementById("dot"), txt=document.getElementById("statustext");
  dot.className="dot "+(pb.playing?"live":"stale");
  txt.textContent="REPLAY "+pb.file+"  ·  "+pb.speed+"×  ·  "+clock;
  if(pb.index < lastIdx){ seen.clear(); list.innerHTML=""; }   // seeked/restarted -> reset ticker
  lastIdx=pb.index;
}

// ---- event ticker ----
const seen = new Set();
const list = document.getElementById("tickerlist");
function describe(ev){
  const t=ev.topic, d=ev.data||{}, time=tClock(ev.ts);
  if(t.startsWith("f/i/state/")){ const s=t.split("/").pop();
    return {time,cat:"STATION",d:`${NAMES[s]||s} ${d.active?"ACTIVE":"idle"} (code ${d.code})`+(d.target?` → ${d.target}`:"")}; }
  if(t==="f/i/stock"){ const items=d.stockItems||[];
    const occ=items.filter(it=>occupied(it.workpiece)).length;
    return {time,cat:"STOCK",d:`warehouse ${occ}/${items.length} occupied`}; }
  if(t==="f/i/order") return {time,cat:"ORDER",d:`${d.state||""} ${d.type||""}`.trim()};
  if(t==="f/i/nfc/ds"){ const w=d.workpiece||{}; return {time,cat:"NFC",d:`${w.type||"?"} ${w.state||""} id=${(w.id||"").slice(0,8)}`}; }
  if(t==="i/bme680") return {time,cat:"ENV",d:`${d.t}°C  ${d.h}%  ${d.p}hPa  IAQ ${d.iaq}`};
  if(t==="i/ldr") return {time,cat:"LIGHT",d:`brightness ${d.br}%`};
  return {time,cat:"RAW",d:t};
}
function renderEvents(events){
  for(const ev of events){
    const sig = ev.ts+"|"+ev.topic+"|"+JSON.stringify(ev.data);
    if(seen.has(sig)) continue;
    seen.add(sig);
    const info=describe(ev);
    const row=document.createElement("div");
    row.className="ev";
    row.title="click to jump to this moment";
    row.onclick=()=>seekTo(ev.ts);
    row.innerHTML=`<span class="t">${info.time}</span><span class="cat ${info.cat}">${info.cat}</span><span class="d">${info.d}</span>`;
    list.prepend(row);
  }
  while(list.children.length>80) list.removeChild(list.lastChild);
  if(seen.size>4000) seen.clear();
}

// ---- cycle times + order flow ----
const FLOW_ORDER=[["dsi","Input Station"],["hbw","High-Bay Warehouse"],["vgr","Vacuum Gripper"],
                  ["mpo","Processing (kiln+mill)"],["sld","Sorting Line"],["dso","Output / Delivery"]];
function fmtDur(s){ if(s==null) return "—"; s=Math.round(s);
  if(s<60) return s+"s"; const m=Math.floor(s/60),r=s%60; return m+"m"+String(r).padStart(2,"0")+"s"; }
// clear, unambiguous time helpers (24-hour local clock, with date when useful)
function pad2(n){ return String(n).padStart(2,"0"); }
const MON=["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
function tClock(ts){ if(!ts) return "--"; const d=new Date(ts);
  return pad2(d.getHours())+":"+pad2(d.getMinutes())+":"+pad2(d.getSeconds()); }
function tDate(ts){ if(!ts) return "--"; const d=new Date(ts); return MON[d.getMonth()]+" "+d.getDate(); }
function tFull(ts){ if(!ts) return "--"; return tDate(ts)+", "+tClock(ts); }
function seekTo(ts){ if(ts) fetch("/control?action=seekts&value="+(Date.parse(ts)/1000)); }

function renderCycles(data){
  const sum=data.summary||{};
  document.getElementById("cyc-summary").textContent = sum.count
    ? `${sum.count} orders · avg ${fmtDur(sum.avg_total_s)} · fastest ${fmtDur(sum.min_total_s)} · slowest ${fmtDur(sum.max_total_s)}`
    : "no completed orders yet";
  const box=document.getElementById("cyc-body"); box.innerHTML="";
  if(data.current){   // an order is running right now -> live card with a ticking timer
    const cur=data.current;
    const where = cur.active_station ? (NAMES[cur.active_station]||cur.active_station) : "…";
    const card=document.createElement("div"); card.className="cyc live"; card.id="live-order";
    card.dataset.base = (cur.elapsed_s==null?0:cur.elapsed_s); card.dataset.at = Date.now();
    card.title="order in progress";
    card.innerHTML=`<div class="top"><span>&#9679; Order in progress</span><span id="live-timer">${fmtDur(cur.elapsed_s)}</span></div>
      <div class="csub">placed ${tClock(cur.start_ts)} &middot; working at ${where}</div>`;
    box.appendChild(card);
  }
  for(const c of (data.cycles||[]).slice().reverse()){   // newest first
    const maxstage=Math.max(1,...c.stages.map(s=>s.seconds));
    let bars="";
    for(const s of c.stages){
      bars+=`<div class="bar"><span class="lb">${s.name}</span>
        <span class="track"><span class="fill" style="width:${Math.round(s.seconds/maxstage*100)}%;background:${TINT[s.station]||'#888'}"></span></span>
        <span class="val">${fmtDur(s.seconds)}</span></div>`;
    }
    const el=document.createElement("div"); el.className="cyc";
    el.title="click to jump to this order";
    el.onclick=()=>seekTo(c.start_ts);
    el.innerHTML=`<div class="top"><span>Order #${c.order}</span><span>${fmtDur(c.total_s)}</span></div>
      <div class="csub">start ${tClock(c.start_ts)} · PLC response ${fmtDur(c.response_latency_s)}</div>${bars}`;
    box.appendChild(el);
  }
}

function renderFlow(cur){
  const head=document.getElementById("flow-head"), box=document.getElementById("flow-body");
  const visited={}, tsmap={}; let active=null;
  if(cur){
    for(const f of cur.flow){ visited[f.station]=true; if(!tsmap[f.station]) tsmap[f.station]=f.ts; }
    active=cur.active_station;
    head.textContent=`in progress · ${fmtDur(cur.elapsed_s)} · started ${tClock(cur.start_ts)}`;
  } else {
    head.textContent="no order in progress";
  }
  box.innerHTML="";
  for(const [code,label] of FLOW_ORDER){
    let cls="step"; if(active===code) cls+=" active"; else if(visited[code]) cls+=" done";
    const el=document.createElement("div"); el.className=cls;
    el.innerHTML=`<span class="ic"></span><span class="nm">${label}</span>
      <span class="ts">${tsmap[code]?tClock(tsmap[code]):""}</span>`;
    box.appendChild(el);
  }
}

// live order timer: tick the in-progress card up smoothly between polls.
// Only in live mode (in replay the elapsed time follows the playhead, not wall clock).
let liveMode=true;
setInterval(()=>{
  if(!liveMode) return;
  const c=document.getElementById("live-order"); if(!c) return;
  const t=document.getElementById("live-timer"); if(!t) return;
  t.textContent=fmtDur((+c.dataset.base)+(Date.now()-(+c.dataset.at))/1000);
}, 250);

// ---- load recording (in-browser replay import) ----
const btnLoad=document.getElementById("btn-load");
const btnLive=document.getElementById("btn-live");
const panel=document.getElementById("loadpanel");
const filesBox=document.getElementById("lp-files");
const upInput=document.getElementById("lp-file");
const lpMsg=document.getElementById("lp-msg");
function speedVal(){ const s=document.getElementById("pb-speed"); return s?s.value:"1"; }
function resetTicker(){ seen.clear(); list.innerHTML=""; lastIdx=1e9; mileSig=null; }
async function loadFileList(){
  filesBox.innerHTML="<div class='lp-empty'>scanning…</div>";
  let files=[]; try{ files=await fetch("/files.json").then(r=>r.json()); }catch(e){}
  filesBox.innerHTML = files.length? "" : "<div class='lp-empty'>no .jsonl files in the project folder</div>";
  for(const f of files){
    const row=document.createElement("button"); row.className="lp-file";
    row.innerHTML=`<span>${f.name}</span><span class="lp-sz">${Math.max(1,Math.round(f.size/1024))} KB</span>`;
    row.onclick=()=>doLoad("/load?file="+encodeURIComponent(f.name)+"&speed="+speedVal());
    filesBox.appendChild(row);
  }
}
async function doLoad(url, opts){
  lpMsg.textContent="loading…";
  try{
    const r=await fetch(url, opts||{}).then(r=>r.json());
    if(r.ok){ lpMsg.textContent="loaded "+r.events+" events — playing"; resetTicker();
      setTimeout(()=>{ panel.style.display="none"; lpMsg.textContent=""; }, 1000); }
    else lpMsg.textContent="could not load: "+(r.error||"unknown");
  }catch(e){ lpMsg.textContent="error: "+e; }
}
btnLoad.onclick=async()=>{
  const show = panel.style.display!=="block";
  panel.style.display = show?"block":"none";
  if(show) await loadFileList();
};
btnLive.onclick=async()=>{ await fetch("/live"); resetTicker(); panel.style.display="none"; };
upInput.onchange=()=>{
  const file=upInput.files[0]; if(!file) return;
  const rd=new FileReader();
  rd.onload=()=>doLoad("/upload?name="+encodeURIComponent(file.name)+"&speed="+speedVal(),
                       {method:"POST", body:rd.result});
  rd.readAsText(file);
  upInput.value="";
};

// ---- session picker (split one long file into separate connections) ----
let sessionSig=null;
const selSession=document.getElementById("pb-session");
selSession.onchange=()=>{ fetch("/session?i="+selSession.value+"&speed="+speedVal()).then(()=>resetTicker()); };
function updateSessions(data){
  const sessions=data.sessions||[];
  const sig=JSON.stringify(sessions.map(s=>[s.start_ts,s.count]))+"|"+data.active;
  if(sig===sessionSig) return;
  sessionSig=sig;
  selSession.innerHTML="";
  const all=document.createElement("option");
  all.value="all"; all.textContent="All ("+sessions.length+" sessions)"; selSession.appendChild(all);
  for(const s of sessions){
    const o=document.createElement("option"); o.value=s.i;
    o.textContent="#"+(s.i+1)+"  "+tFull(s.start_ts)+"  ·  "+fmtDur(s.duration)+"  ·  "+s.count+" ev";
    selSession.appendChild(o);
  }
  selSession.value=(data.active==null||data.active==="all")?"all":String(data.active);
  refreshMilestones(true);
}

// ---- key events (milestones) list ----
let mileSig=null;
async function refreshMilestones(force){
  let ms=[]; try{ ms=await fetch("/milestones.json",{cache:"no-store"}).then(r=>r.json()); }catch(e){ return; }
  const sig=ms.length+"|"+(ms[0]&&ms[0].ts)+"|"+(ms.length&&ms[ms.length-1].ts);
  if(!force && sig===mileSig) return; mileSig=sig;
  const box=document.getElementById("keylist"); box.innerHTML="";
  if(!ms.length){ box.innerHTML="<div class='lp-empty'>no key events in this session</div>"; return; }
  for(const m of ms){
    const row=document.createElement("div"); row.className="ev key "+(m.kind||"");
    row.title="click to jump to this event";
    row.onclick=()=>seekTo(m.ts);
    row.innerHTML=`<span class="t">${tClock(m.ts)}</span><span class="cat">${m.kind==="order"?"ORDER":"NFC"}</span><span class="d">${m.label}</span>`;
    box.appendChild(row);
  }
}
function setLogView(v){
  document.getElementById("tickerlist").style.display=v==="all"?"":"none";
  document.getElementById("keylist").style.display=v==="key"?"":"none";
  document.getElementById("tog-all").classList.toggle("on",v==="all");
  document.getElementById("tog-key").classList.toggle("on",v==="key");
  if(v==="key") refreshMilestones(true);
}
document.getElementById("tog-all").onclick=()=>setLogView("all");
document.getElementById("tog-key").onclick=()=>setLogView("key");

let tickN=0;
async function tick(){
  try{
    const [s,e,pb,cy]=await Promise.all([
      fetch("/state.json",{cache:"no-store"}).then(r=>r.json()),
      fetch("/events.json",{cache:"no-store"}).then(r=>r.json()),
      fetch("/playback.json",{cache:"no-store"}).then(r=>r.json()),
      fetch("/cycles.json",{cache:"no-store"}).then(r=>r.json()),
    ]);
    renderStations(s); renderSide(s); renderEvents(e);
    renderCycles(cy); renderFlow(cy.current);
    if(pb && pb.mode==="replay"){
      liveMode=false;
      updatePlayback(pb); btnLive.style.display=""; document.body.classList.add("replay");
      if(tickN%3===1){
        try{ updateSessions(await fetch("/sessions.json",{cache:"no-store"}).then(r=>r.json())); }catch(e2){}
      }
    } else {
      liveMode=true;
      updateStatusLive(s); document.getElementById("controls").style.display="none";
      btnLive.style.display="none"; document.body.classList.remove("replay");
    }
    if(tickN%3===1) refreshMilestones();   // keep Key events current in both modes
  }catch(err){ /* transient; retry next tick */ }
}
tick(); setInterval(()=>{ tickN++; tick(); }, POLL_MS);
</script>
</body>
</html>
"""


def _to_float(v, default):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _sessions_from_epochs(epochs, gap=SESSION_GAP):
    """Split an ascending list of event times into (start, end) index ranges,
    breaking wherever there's a gap longer than `gap` (i.e. downtime between
    two separate connections to the factory)."""
    if not epochs:
        return []
    bounds, start = [], 0
    for i in range(1, len(epochs)):
        if epochs[i] - epochs[i - 1] > gap:
            bounds.append((start, i))
            start = i
    bounds.append((start, len(epochs)))
    return bounds


def build_source(records, name):
    """Sort the loaded records by time and split them into sessions."""
    global SOURCE
    withep = [(parse_epoch(r.get("ts")), r) for r in records]
    withep = [(ep, r) for ep, r in withep if ep is not None]
    withep.sort(key=lambda x: x[0])
    recs = [r for _, r in withep]
    eps = [ep for ep, _ in withep]
    sessions = []
    for k, (s, e) in enumerate(_sessions_from_epochs(eps)):
        sessions.append({"i": k, "start_ts": recs[s]["ts"], "end_ts": recs[e - 1]["ts"],
                         "count": e - s, "duration": round(eps[e - 1] - eps[s], 1),
                         "start_idx": s, "end_idx": e})
    SOURCE = {"name": name, "records": recs, "epochs": eps, "sessions": sessions}
    return SOURCE


def select_session(which, speed=1.0):
    """Scope playback to one session index, or "all" for the whole file."""
    global PB, ACTIVE_SESSION
    if SOURCE is None:
        return {"ok": False, "error": "no recording loaded", "events": 0}
    sessions = SOURCE["sessions"]
    if which in (None, "all"):
        recs, ACTIVE_SESSION = SOURCE["records"], "all"
    else:
        try:
            k = int(which)
        except (TypeError, ValueError):
            return {"ok": False, "error": "bad session id", "events": 0}
        if not 0 <= k < len(sessions):
            return {"ok": False, "error": "no such session", "events": 0}
        s = sessions[k]
        recs, ACTIVE_SESSION = SOURCE["records"][s["start_idx"]:s["end_idx"]], k
    pb = Playback(recs, SOURCE["name"], speed)
    if pb.n == 0:
        return {"ok": False, "error": "no usable events", "events": 0}
    PB = pb
    return {"ok": True, "error": "", "events": pb.n,
            "file": SOURCE["name"], "session": ACTIVE_SESSION,
            "sessions": len(sessions)}


def _load_records(records, name, speed):
    build_source(records, name)
    default = SOURCE["sessions"][-1]["i"] if SOURCE["sessions"] else "all"  # newest run
    return select_session(default, speed)


def replay_from_file(name, speed):
    if not str(name).endswith(".jsonl"):
        return {"ok": False, "error": "need a .jsonl file", "events": 0}
    full = os.path.join(HERE, os.path.basename(name))   # basename = no path traversal
    if not os.path.exists(full):
        return {"ok": False, "error": "file not found in project folder", "events": 0}
    try:
        with open(full) as f:
            return _load_records(Playback._records_from_lines(f), os.path.basename(name), speed)
    except Exception as ex:
        return {"ok": False, "error": str(ex), "events": 0}


def replay_from_text(text, name, speed):
    try:
        return _load_records(Playback._records_from_lines(text.splitlines()), name, speed)
    except Exception as ex:
        return {"ok": False, "error": str(ex), "events": 0}


def go_live():
    global PB, SOURCE, ACTIVE_SESSION
    PB, SOURCE, ACTIVE_SESSION = None, None, None
    return {"ok": True}


class Handler(BaseHTTPRequestHandler):
    # HTTP/1.1 so browsers' large POST uploads (Expect: 100-continue) complete;
    # every response sets Content-Length, which keep-alive requires.
    protocol_version = "HTTP/1.1"

    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            html = INDEX_HTML.replace("__POLL_MS__", str(POLL_MS))
            self._send(200, html.encode("utf-8"), "text/html; charset=utf-8")

        elif path == "/state.json":
            if PB:
                body = PB.state_json().encode("utf-8")
            else:
                try:
                    with open(STATE_FILE, "rb") as f:
                        body = f.read()
                except OSError:
                    body = b"{}"
            self._send(200, body, "application/json")

        elif path == "/events.json":
            if PB:
                body = PB.events_json(TICKER_LINES).encode("utf-8")
            else:
                body = ("[" + ",".join(tail(EVENTS_FILE, TICKER_LINES)) + "]").encode("utf-8")
            self._send(200, body, "application/json")

        elif path == "/cycles.json":
            if PB:
                body = PB.cycles_json().encode("utf-8")
            else:
                body = live_cycles_json().encode("utf-8")
            self._send(200, body, "application/json")

        elif path == "/playback.json":
            if PB:
                body = json.dumps(PB.status()).encode("utf-8")
            else:
                body = b'{"mode":"live"}'
            self._send(200, body, "application/json")

        elif path == "/control":
            if PB:
                PB.control(query.get("action", [""])[0], query.get("value", [None])[0])
            self._send(200, b'{"ok":true}', "application/json")

        elif path == "/files.json":
            files = []
            try:
                for fn in sorted(os.listdir(HERE)):
                    if fn.endswith(".jsonl"):
                        try:
                            sz = os.path.getsize(os.path.join(HERE, fn))
                        except OSError:
                            sz = 0
                        files.append({"name": fn, "size": sz})
            except OSError:
                pass
            self._send(200, json.dumps(files).encode("utf-8"), "application/json")

        elif path == "/load":
            res = replay_from_file(query.get("file", [""])[0],
                                   _to_float(query.get("speed", ["1"])[0], 1.0))
            self._send(200, json.dumps(res).encode("utf-8"), "application/json")

        elif path == "/live":
            self._send(200, json.dumps(go_live()).encode("utf-8"), "application/json")

        elif path == "/sessions.json":
            if SOURCE:
                body = json.dumps({
                    "file": SOURCE["name"], "active": ACTIVE_SESSION, "gap": SESSION_GAP,
                    "sessions": [{k: v for k, v in s.items() if k not in ("start_idx", "end_idx")}
                                 for s in SOURCE["sessions"]],
                }).encode("utf-8")
            else:
                body = b'{"sessions":[]}'
            self._send(200, body, "application/json")

        elif path == "/session":
            res = select_session(query.get("i", ["all"])[0],
                                 _to_float(query.get("speed", ["1"])[0], 1.0))
            self._send(200, json.dumps(res).encode("utf-8"), "application/json")

        elif path == "/milestones.json":
            if PB:
                body = json.dumps(compute_milestones(PB.events)).encode("utf-8")
            else:
                body = live_milestones_json().encode("utf-8")
            self._send(200, body, "application/json")

        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        parsed = urlparse(self.path)
        path, query = parsed.path, parse_qs(parsed.query)
        if path == "/upload":
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length).decode("utf-8", "replace") if length else ""
            name = os.path.basename(query.get("name", ["uploaded.jsonl"])[0])
            res = replay_from_text(raw, name, _to_float(query.get("speed", ["1"])[0], 1.0))
            self._send(200, json.dumps(res).encode("utf-8"), "application/json")
        elif path == "/load":
            res = replay_from_file(query.get("file", [""])[0],
                                   _to_float(query.get("speed", ["1"])[0], 1.0))
            self._send(200, json.dumps(res).encode("utf-8"), "application/json")
        elif path == "/live":
            self._send(200, json.dumps(go_live()).encode("utf-8"), "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def log_message(self, *args):
        pass


def main():
    global PB
    ap = argparse.ArgumentParser(description="Live/replay 2D view of the smart factory.")
    ap.add_argument("--replay", nargs="?", const=EVENTS_FILE, metavar="FILE.jsonl",
                    help="Replay a recorded .jsonl log instead of showing live data. "
                         "Defaults to factory_events.jsonl if no file is given.")
    ap.add_argument("--speed", type=float, default=1.0, help="Initial playback speed (replay mode).")
    ap.add_argument("--port", type=int, default=PORT, help="HTTP port (default 8420).")
    ap.add_argument("--no-browser", action="store_true",
                    help="Don't auto-open a browser tab (useful for testing).")
    args = ap.parse_args()

    port = args.port
    if args.replay:
        if not os.path.exists(args.replay):
            print(f"Replay file not found: {args.replay}")
            return
        with open(args.replay) as f:
            _load_records(Playback._records_from_lines(f), os.path.basename(args.replay), args.speed)
        if PB is None or PB.n == 0:
            print(f"No usable events in {args.replay} (need lines with a 'ts' field).")
            return

    url = f"http://localhost:{port}"
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    if PB:
        nsess = len(SOURCE["sessions"]) if SOURCE else 1
        print(f"REPLAY mode: {args.replay}")
        print(f"  {nsess} session(s) detected; showing the most recent "
              f"({PB.n} events over {PB.duration:.0f}s at {args.speed}× speed)")
        print(f"  Pick another session or jump to events in the browser at {url}")
    else:
        print(f"LIVE mode: 2D twin at {url}")
        print(f"  reading {STATE_FILE}")
        print("  (make sure live_data_feed.py is running so the data stays fresh)")
    print("  Press Ctrl+C to stop.\n")

    if not args.no_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped.")
        server.shutdown()


if __name__ == "__main__":
    main()
