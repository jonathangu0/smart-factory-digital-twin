"""
twin_reader.py

Tiny, dependency-free helper for reading the live factory state that
`live_data_feed.py` writes to `factory_state.json`.

Designed to be imported from an Isaac Sim (Omniverse) script so the simulation
loop can pull the latest factory state each frame WITHOUT doing any MQTT,
threading, or networking itself. The data feed process owns all of that; the
twin just reads a small JSON file.

Typical Isaac Sim usage (inside your extension / script):

    from twin_reader import TwinReader

    reader = TwinReader("factory_state.json")

    # ...called from your per-frame / physics callback:
    state = reader.poll()          # returns cached dict; re-reads only if changed
    if state:
        for code, st in state["stations"].items():
            prim = station_prims[code]        # your USD prim for this station
            set_active_visual(prim, st["active"])
            # drive lights / labels / animations from st["code"], st["target"], ...

        env = state["sensors"].get("environment")
        if env:
            update_hud(temp=env["temperature_c"], iaq=env["air_quality_index"])

`poll()` is cheap: it stats the file and only re-parses when the file has
actually changed on disk, so you can safely call it every frame.
"""

import json
import os


class TwinReader:
    def __init__(self, path="factory_state.json"):
        self.path = path
        self._mtime = None       # last modification time we parsed
        self._cache = None       # last successfully parsed state

    def poll(self):
        """Return the latest state dict, re-reading the file only when it has
        changed since the previous call. Returns None if no state exists yet.
        Never raises on a transient read (e.g. mid-write) - returns the last
        good cache instead."""
        try:
            mtime = os.path.getmtime(self.path)
        except OSError:
            return self._cache  # file not there yet

        if mtime == self._mtime and self._cache is not None:
            return self._cache   # unchanged -> hand back the cached parse

        try:
            with open(self.path) as f:
                data = json.load(f)
            self._cache = data
            self._mtime = mtime
        except (json.JSONDecodeError, OSError):
            # Reader raced the writer; keep the last good state.
            pass
        return self._cache

    # --- convenience accessors (all read from the cached poll) --------------

    def station(self, code):
        """State dict for one station code (e.g. 'hbw'), or None."""
        state = self.poll()
        return (state or {}).get("stations", {}).get(code)

    def is_active(self, code):
        """True if the given station is currently active/running."""
        st = self.station(code)
        return bool(st and st.get("active"))

    def environment(self):
        """Latest environment sensor reading, or None."""
        state = self.poll()
        return (state or {}).get("sensors", {}).get("environment")

    def brightness(self):
        """Latest brightness sensor reading, or None."""
        state = self.poll()
        return (state or {}).get("sensors", {}).get("brightness")

    def stock(self):
        """Latest warehouse stock model, or None."""
        state = self.poll()
        return (state or {}).get("stock")

    def last_updated(self):
        """ISO-8601 timestamp of the last change, or None."""
        state = self.poll()
        return (state or {}).get("meta", {}).get("updated")


if __name__ == "__main__":
    # Quick manual test: print a live view of the state from the terminal.
    import time

    reader = TwinReader()
    print(f"Watching {os.path.abspath(reader.path)} ... (Ctrl+C to stop)\n")
    try:
        while True:
            state = reader.poll()
            if not state:
                print("waiting for factory_state.json ...", end="\r")
            else:
                stations = state.get("stations", {})
                active = [c for c, s in stations.items() if s.get("active")]
                print(f"[{reader.last_updated()}] "
                      f"stations={len(stations)}  active={active or 'none'}   ",
                      end="\r")
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nstopped.")
