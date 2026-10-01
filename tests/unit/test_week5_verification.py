"""Exercise the shell verifier with a simulated CLI, without any real VMs."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest

ROOT = Path(__file__).resolve().parents[2]

FAKE_MULTIPASS = r'''import json, os, sys
from pathlib import Path
path = Path(os.environ["FAKE_MULTIPASS_STATE"])
state = json.loads(path.read_text())
args = sys.argv[1:]
state["commands"].append(args)
path.write_text(json.dumps(state))
operation = args[0]
if os.environ.get("FAKE_MULTIPASS_FAIL") == operation:
    print("Simulated provider failure", file=sys.stderr)
    sys.exit(4)
vms = state["vms"]

def save():
    path.write_text(json.dumps(state))

def error(message):
    print(message, file=sys.stderr)
    sys.exit(1)

if operation == "list":
    print(json.dumps({"errors": [], "list": [
        {"name": name, "state": details["state"], "ipv4": [],
         "release": "24.04 LTS"} for name, details in vms.items()
    ]}))
elif operation == "info":
    name = args[1]
    if name not in vms:
        error("VM not found")
    print(json.dumps({"errors": [], "info": {name: {
        "state": vms[name]["state"], "ipv4": [], "cpu_count": 1,
        "release": "Ubuntu 24.04 LTS"
    }}}))
elif operation == "launch":
    name = args[args.index("-n") + 1]
    if name in vms:
        error("VM already exists")
    vms[name] = {"state": "Running"}
    save()
elif operation in ("stop", "start", "restart", "suspend"):
    name = args[1]
    if name not in vms:
        error("VM not found")
    if operation in ("restart", "suspend") and vms[name]["state"] != "Running":
        error("VM is not running")
    vms[name]["state"] = {"stop": "Stopped", "start": "Running",
                          "restart": "Running", "suspend": "Suspended"}[operation]
    save()
elif operation == "delete":
    if args[1] != "--purge" or len(args) != 3:
        error("Unsafe deletion")
    vms.pop(args[2], None)
    save()
elif operation == "exec":
    if args[1] not in vms or vms[args[1]]["state"] != "Running":
        error("VM is not running")
    if args[-1] == "hostname":
        print(args[1])
    elif args[-1] == "false":
        sys.exit(1)
    elif args[-1] != "true":
        error("Unknown simulated guest command")
elif operation == "find":
    print(json.dumps({"images": {"24.04": {"release": "noble"}}}))
elif operation == "version":
    print("multipass 1.16.2\nmultipassd 1.16.2")
else:
    error("Unknown simulated operation")
'''


@pytest.fixture
def simulated_host(tmp_path):
    binary_dir = tmp_path / "bin"
    binary_dir.mkdir()
    cmx = binary_dir / "cmx"
    cmx.write_text(f"#!{sys.executable}\nfrom cloudmesh.ai.command.vm import cmx\ncmx()\n")
    multipass = binary_dir / "multipass"
    multipass.write_text(f"#!{sys.executable}\n" + FAKE_MULTIPASS)
    cmx.chmod(0o755)
    multipass.chmod(0o755)
    original = {
        "sports-midterm": {"state": "Running"},
        "week4-local": {"state": "Stopped"},
        "unrelated-deleted-vm": {"state": "Deleted"},
    }
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps({"vms": original, "commands": []}))
    environment = {
        **os.environ, "PATH": str(binary_dir) + os.pathsep + os.environ["PATH"],
        "PYTHON": sys.executable, "PYTHONPATH": str(ROOT / "src"),
        "FAKE_MULTIPASS_STATE": str(state_file),
    }
    return environment, state_file, original


def run_verifier(simulated_host, failure=None):
    environment, _, _ = simulated_host
    if failure:
        environment["FAKE_MULTIPASS_FAIL"] = failure
    return subprocess.run(
        ["bash", str(ROOT / "tests/bin/verify_multipass_week5.sh")],
        env=environment, capture_output=True, text=True, timeout=90
    )


def test_verifier_checks_states_counters_and_targeted_cleanup(simulated_host):
    result = run_verifier(simulated_host)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "0 failed" in result.stdout
    state = json.loads(simulated_host[1].read_text())
    assert state["vms"] == simulated_host[2]
    deleted = [args for args in state["commands"] if args[0] == "delete"]
    assert len(deleted) == 3
    assert all(args[1] == "--purge" and args[2].startswith("sugwu-week5-") for args in deleted)
    assert "Original VM names and states preserved" in result.stdout


def test_verifier_aborts_when_preflight_inventory_fails(simulated_host):
    result = run_verifier(simulated_host, "list")
    assert result.returncode == 2
    state = json.loads(simulated_host[1].read_text())
    assert state["vms"] == simulated_host[2]
    assert all(args[0] == "list" for args in state["commands"])


def test_verifier_returns_nonzero_when_lifecycle_state_check_fails(simulated_host):
    result = run_verifier(simulated_host, "suspend")
    assert result.returncode != 0
    assert "FAIL: Suspend VM" in result.stdout
    assert "FAIL: Suspended state" in result.stdout
    assert json.loads(simulated_host[1].read_text())["vms"] == simulated_host[2]


def test_verifier_aborts_after_failed_creation_without_touching_other_vms(simulated_host):
    result = run_verifier(simulated_host, "launch")
    assert result.returncode != 0
    assert "FAIL: Start with --name" in result.stdout
    assert json.loads(simulated_host[1].read_text())["vms"] == simulated_host[2]
