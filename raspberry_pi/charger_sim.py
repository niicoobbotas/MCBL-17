#!/usr/bin/env python3
"""
SmartEV CACCS — Raspberry Pi Charge Point Simulator
Connects to the SmartEV backend via WebSocket, receives a CACCS charging
schedule, and runs a slot-by-slot simulation with real-time progress feedback.

Usage:
  python charger_sim.py                        # backend on localhost:8000
  python charger_sim.py --host 192.168.1.5     # backend on another machine
"""
import argparse
import asyncio
import json
import sys

try:
    import websockets
except ImportError:
    print("ERROR: pip install websockets", file=sys.stderr)
    sys.exit(1)


async def run_sim(ws):
    paused = False
    schedule_msg = None

    async def listen():
        nonlocal paused, schedule_msg
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except Exception:
                    continue
                t = msg.get("type")
                if t == "schedule":
                    schedule_msg = msg
                    print(f"  Schedule received — {len(msg['slots'])} slots, "
                          f"{msg.get('slot_seconds', 10)} s each")
                elif t == "stop":
                    paused = True
                    await ws.send(json.dumps({"type": "paused"}))
                    print("  PAUSED by dashboard")
                elif t == "resume":
                    paused = False
                    print("  RESUMED by dashboard")
                elif t == "ping":
                    await ws.send(json.dumps({"type": "pong"}))
        except Exception:
            pass

    listener = asyncio.create_task(listen())

    await ws.send(json.dumps({"type": "pi_hello", "device": "rpi5"}))
    print("  Waiting for schedule from the dashboard...")

    while schedule_msg is None:
        await asyncio.sleep(0.2)

    slots = schedule_msg["slots"]
    slot_sec = float(schedule_msg.get("slot_seconds", 10))
    pmax = float(schedule_msg.get("pmax_kw", 11.0))
    tick = 0.1

    print(f"\n  Running: {len(slots)} slots x {slot_sec:.0f} s = "
          f"{len(slots) * slot_sec:.0f} s total  (pmax={pmax} kW)\n")

    async def wait(duration):
        """Wait for `duration` seconds, honouring pause/resume."""
        nonlocal paused
        elapsed = 0.0
        while elapsed < duration:
            if paused:
                await ws.send(json.dumps({"type": "paused"}))
                while paused:
                    await asyncio.sleep(0.1)
                await ws.send(json.dumps({"type": "resumed"}))
            await asyncio.sleep(tick)
            elapsed += tick

    for slot in slots:
        idx = slot["slot"]
        kw = float(slot["kw"])
        hour = int(slot["hour"])
        is_charging = kw > 0.01

        # How long to actually charge within this hour slot (at pmax)
        charge_frac = min(1.0, kw / pmax) if is_charging else 0.0
        charge_secs = charge_frac * slot_sec
        idle_secs = slot_sec - charge_secs

        await ws.send(json.dumps({
            "type": "slot_start",
            "slot": idx,
            "hour": hour,
            "kw": kw,
            "charge_secs": round(charge_secs, 1),
            "idle_secs": round(idle_secs, 1),
            "status": "charging" if is_charging else "idle",
        }))

        if is_charging:
            print(f"  Slot {idx:2d}  {hour:02d}:00  charging {kw:.1f} kW  "
                  f"({charge_secs:.1f}s charge + {idle_secs:.1f}s idle)")

            # ── Charging phase: progress bar fills ──
            elapsed = 0.0
            while elapsed < charge_secs:
                if paused:
                    await ws.send(json.dumps({"type": "paused"}))
                    while paused:
                        await asyncio.sleep(0.1)
                    await ws.send(json.dumps({"type": "resumed"}))
                await asyncio.sleep(tick)
                elapsed += tick
                if abs(elapsed % (charge_secs / 10)) < tick * 1.5:
                    await ws.send(json.dumps({
                        "type": "progress",
                        "slot": idx,
                        "progress": round(min(1.0, elapsed / charge_secs), 3),
                    }))

            # ── Charging done for this hour — go idle ──
            await ws.send(json.dumps({"type": "slot_idle", "slot": idx, "hour": hour}))
            print(f"          -> idle for remaining {idle_secs:.1f}s")
            await wait(idle_secs)
        else:
            print(f"  Slot {idx:2d}  {hour:02d}:00  idle (full slot)")
            await wait(slot_sec)

        await ws.send(json.dumps({
            "type": "slot_done",
            "slot": idx,
            "hour": hour,
            "kwh": round(kw * slot_sec / 3600, 4),
        }))

    total_kwh = sum(float(s["kw"]) for s in slots)
    await ws.send(json.dumps({
        "type": "session_done",
        "total_slots": len(slots),
        "total_kwh": round(total_kwh, 3),
    }))
    print(f"\n  Simulation complete — {total_kwh:.3f} kWh delivered")
    listener.cancel()


async def main_loop(host: str):
    url = f"ws://{host}/ws/pi"
    print(f"SmartEV Charge Simulator  |  backend: {url}")
    try:
        async with websockets.connect(url, ping_interval=20, ping_timeout=10) as ws:
            print("Connected\n")
            await run_sim(ws)
    except (OSError, ConnectionRefusedError,
            websockets.exceptions.WebSocketException) as exc:
        print(f"\nERROR: Cannot connect to {url}", file=sys.stderr)
        print(f"  {exc}", file=sys.stderr)
        print("\nMake sure the SmartEV backend is running:", file=sys.stderr)
        print("  cd website/backend && uvicorn main:app --host 0.0.0.0 --port 8000",
              file=sys.stderr)
    except KeyboardInterrupt:
        print("\n  Stopped.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="SmartEV RPi Charge Simulator")
    ap.add_argument(
        "--host", default="localhost:8000",
        help="SmartEV backend host:port  (default: localhost:8000)")
    args = ap.parse_args()
    asyncio.run(main_loop(args.host))
