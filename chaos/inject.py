"""Fault injector — breaks ONE allowlisted container in a controlled, reversible way.

Plain English: each fault type has an "inject" (break it) and a matching "restore" (undo it).
Every injection has a hard time limit and is undone automatically when time runs out, when you
press Ctrl+C, or when the safety controller calls restore().

Fault types:
  kill   — crash the container instantly (like pulling the power plug). Restore: start it again.
  pause  — freeze the container (still "running" but answers nothing). Restore: unpause.
  delay  — add network latency inside the container only, using Pumba (tc/netem). Restore: remove it.
  loss   — drop a % of network packets inside the container only, using Pumba. Restore: remove it.

Run:  python chaos/inject.py kill recommendation --duration 60
      python chaos/inject.py delay product-catalog --duration 90 --ms 500
"""
import argparse
import json
import signal
import subprocess
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TARGETS = yaml.safe_load((ROOT / "config" / "targets.yaml").read_text())
MAX_SECONDS = yaml.safe_load((ROOT / "config" / "thresholds.yaml").read_text())["max_experiment_seconds"]

# Pumba runs in its own small container and only changes the network of the target container.
PUMBA_IMAGE = "gaiaadm/pumba:latest"                                     # TODO verify before first use
TC_IMAGE = "ghcr.io/alexei-led/pumba-alpine-nettools:latest"             # TODO verify before first use


DOCKER_TIMEOUT = 60  # seconds; a frozen Docker engine must never freeze the safety referee with it


def docker(*args, check=True):
    """Run one docker command. If Docker doesn't answer within DOCKER_TIMEOUT, fail loudly instead of hanging."""
    try:
        return subprocess.run(["docker", *args], capture_output=True, text=True, check=check,
                              timeout=DOCKER_TIMEOUT).stdout.strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"Docker did not answer within {DOCKER_TIMEOUT}s (docker {' '.join(args[:2])}). "
                           "Restart Docker Desktop, then run chaos\stop_all.ps1") from None


def check_target(name):
    """Refuse anything that is not on the allowlist, is on the denylist, or isn't in our compose project."""
    if name in TARGETS["denylist"] or name not in TARGETS["allowlist"]:
        raise SystemExit(f"REFUSED: '{name}' is not an allowed chaos target (see config/targets.yaml)")
    project = docker("inspect", "-f", '{{ index .Config.Labels "com.docker.compose.project" }}', name, check=False)
    if project != TARGETS["compose_project"]:
        raise SystemExit(f"REFUSED: '{name}' does not belong to compose project '{TARGETS['compose_project']}'")


def state(name):
    """Running / paused / exited, plus health if the container has a health check."""
    try:
        out = docker("inspect", "-f", "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}",
                     name, check=False)
    except RuntimeError:
        return "unknown (Docker not answering)"
    return out or "missing"


class Fault:
    kind = "base"

    def __init__(self, target, **params):
        check_target(target)
        self.target, self.params = target, params
        self.active = False

    def inject(self):
        raise NotImplementedError

    def restore(self):
        raise NotImplementedError

    def describe(self):
        return {"fault": self.kind, "target": self.target, **self.params}


class Kill(Fault):
    kind = "kill"

    def inject(self):
        docker("kill", self.target)
        self.active = True

    def restore(self):
        # Docker's restart policy may already have brought it back — that's a finding, not an error.
        if not state(self.target).startswith("running"):
            docker("start", self.target)
        self.active = False


class Pause(Fault):
    kind = "pause"

    def inject(self):
        docker("pause", self.target)
        self.active = True

    def restore(self):
        if state(self.target).startswith("paused"):
            docker("unpause", self.target)
        self.active = False


class Netem(Fault):
    """Network delay / packet loss applied INSIDE the target container only (never the laptop or venue network)."""

    def __init__(self, target, kind, duration, **params):
        super().__init__(target, **params)
        self.kind, self.duration = kind, duration
        self.helper = f"chaos-netem-{target}"

    def inject(self):
        if self.kind == "delay":
            action = ["delay", "--time", str(self.params.get("ms", 300)), "--jitter", str(self.params.get("jitter_ms", 50))]
        else:
            action = ["loss", "--percent", str(self.params.get("percent", 20))]
        # --duration makes Pumba remove the fault on its own even if our script crashes (extra seat belt).
        docker("run", "-d", "--rm", "--name", self.helper,
               "-v", "/var/run/docker.sock:/var/run/docker.sock", PUMBA_IMAGE,
               "netem", "--duration", f"{self.duration}s", "--tc-image", TC_IMAGE, *action, self.target)
        self.active = True

    def restore(self):
        # Stopping Pumba makes it clean up its tc rules; then double-check by deleting any leftover rule.
        docker("stop", self.helper, check=False)
        docker("run", "--rm", "--net", f"container:{self.target}", "--cap-add", "NET_ADMIN",
               TC_IMAGE, "tc", "qdisc", "del", "dev", "eth0", "root", check=False)
        self.active = False


def make_fault(kind, target, duration, **params):
    if kind == "kill":
        return Kill(target)
    if kind == "pause":
        return Pause(target)
    if kind in ("delay", "loss"):
        return Netem(target, kind, duration, **params)
    raise SystemExit(f"unknown fault type: {kind}")


def run_with_timer(fault, duration):
    """Inject, wait (printing container state), and ALWAYS restore — on timeout, Ctrl+C, or error."""
    duration = min(duration, MAX_SECONDS)
    restored = {"done": False}

    def restore_once(*_):
        if not restored["done"]:
            restored["done"] = True
            fault.restore()
            print(f"{time.strftime('%H:%M:%S')}  RESTORED {fault.target} -> {state(fault.target)}")

    signal.signal(signal.SIGINT, lambda *a: (restore_once(), sys.exit(1)))
    print(f"{time.strftime('%H:%M:%S')}  INJECT {json.dumps(fault.describe())} for max {duration}s")
    try:
        fault.inject()
        end = time.time() + duration
        while time.time() < end:
            print(f"{time.strftime('%H:%M:%S')}  {fault.target}: {state(fault.target)}")
            time.sleep(5)
    finally:
        restore_once()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Inject one controlled fault into one allowlisted container.")
    ap.add_argument("kind", choices=["kill", "pause", "delay", "loss"])
    ap.add_argument("target")
    ap.add_argument("--duration", type=int, default=60, help=f"seconds before auto-restore (max {MAX_SECONDS})")
    ap.add_argument("--ms", type=int, default=300, help="delay in milliseconds (delay only)")
    ap.add_argument("--percent", type=int, default=20, help="packet loss %% (loss only)")
    a = ap.parse_args()
    extra = {"ms": a.ms} if a.kind == "delay" else {"percent": a.percent} if a.kind == "loss" else {}
    run_with_timer(make_fault(a.kind, a.target, a.duration, **extra), a.duration)
