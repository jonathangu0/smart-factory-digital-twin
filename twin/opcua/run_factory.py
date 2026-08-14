"""
run_factory.py  -  ONE command to start the whole thing.

Instead of opening two terminals, just run:

    python3 run_factory.py

That launches BOTH:
    * live_data_feed.py   (connects to the factory MQTT broker, writes the data)
    * factory_2d_view.py  (the live 2D dashboard at http://localhost:8420)

and streams both of their outputs into this one window, each line tagged
[feed] or [view] so you can tell them apart. Press Ctrl+C once to stop everything.

To review a past recording instead of the live factory (no WiFi needed), the
feed is skipped automatically:

    python3 run_factory.py --replay factory_events.jsonl
    python3 run_factory.py --replay old_run.jsonl --speed 4

Standard library only.
"""

import os
import sys
import time
import argparse
import threading
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
FEED = os.path.join(HERE, "live_data_feed.py")
VIEW = os.path.join(HERE, "factory_2d_view.py")

CYAN, GREEN, DIM, RESET = "\033[96m", "\033[92m", "\033[90m", "\033[0m"
procs = []  # list of (label, Popen)


def stream(proc, label, colour):
    """Print a child's output live, each line tagged with its label."""
    for line in iter(proc.stdout.readline, ""):
        if not line and proc.poll() is not None:
            break
        sys.stdout.write(f"{colour}[{label}]{RESET} {line}")
        sys.stdout.flush()


def launch(script_args, label, colour):
    """Start a child python process and pump its output through stream()."""
    proc = subprocess.Popen(
        [sys.executable, "-u", *script_args],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, bufsize=1, cwd=HERE,
    )
    procs.append((label, proc))
    threading.Thread(target=stream, args=(proc, label, colour), daemon=True).start()
    return proc


def stop_all():
    for label, proc in procs:
        if proc.poll() is None:
            proc.terminate()
    deadline = time.time() + 5
    for label, proc in procs:
        try:
            proc.wait(timeout=max(0, deadline - time.time()))
        except subprocess.TimeoutExpired:
            proc.kill()


def main():
    ap = argparse.ArgumentParser(description="Start the smart-factory feed + 2D view together.")
    ap.add_argument("--replay", nargs="?", const="factory_events.jsonl", metavar="FILE.jsonl",
                    help="Replay a recorded log instead of the live factory (skips the feed).")
    ap.add_argument("--speed", type=float, help="Replay speed multiplier.")
    ap.add_argument("--port", type=int, help="Dashboard HTTP port (default 8420).")
    args = ap.parse_args()

    for path, name in ((FEED, "live_data_feed.py"), (VIEW, "factory_2d_view.py")):
        if not os.path.exists(path):
            print(f"Missing {name} next to run_factory.py — cannot start.")
            return

    view_args = [VIEW]
    if args.port:
        view_args += ["--port", str(args.port)]

    print(f"{DIM}{'='*70}{RESET}")
    if args.replay:
        view_args += ["--replay", args.replay]
        if args.speed:
            view_args += ["--speed", str(args.speed)]
        print(f"  SMART FACTORY  ·  REPLAY MODE  ·  {args.replay}")
        print(f"{DIM}{'='*70}{RESET}")
        print(f"{DIM}Starting dashboard only (replay needs no live feed)…{RESET}\n")
        launch(view_args, "view", GREEN)
    else:
        print("  SMART FACTORY  ·  LIVE MODE")
        print(f"{DIM}{'='*70}{RESET}")
        print(f"{DIM}Starting data feed, then dashboard… (needs the factory WiFi){RESET}")
        print(f"{DIM}Dashboard will open in your browser at http://localhost:{args.port or 8420}{RESET}\n")
        launch([FEED], "feed", CYAN)
        time.sleep(1.5)   # let the feed connect and write an initial state file
        launch(view_args, "view", GREEN)

    print(f"\n{DIM}Press Ctrl+C to stop everything.{RESET}\n")
    try:
        while True:
            alive = [p for _, p in procs if p.poll() is None]
            if not alive:
                print(f"\n{DIM}All processes have exited.{RESET}")
                break
            time.sleep(0.5)
    except KeyboardInterrupt:
        print(f"\n{DIM}Stopping…{RESET}")
    finally:
        stop_all()
        print(f"{DIM}Done.{RESET}")


if __name__ == "__main__":
    main()
