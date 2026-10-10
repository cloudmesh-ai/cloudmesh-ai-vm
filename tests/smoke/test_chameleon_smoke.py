"""
Smoke test for the Chameleon (KVM@TACC) provider against the real cloud.

Lifecycle: start -> wait running -> info -> list -> floating IP -> run (SSH)
-> stop -> wait stopped -> restart -> wait running -> delete -> verify gone.

KVM@TACC boots regular flavors on demand (no lease needed). Optional
settings, with defaults:

    export CHAMELEON_FLAVOR=m1.small                    # or reservation:<id>
    export CHAMELEON_KEY_NAME=<keypair name in Chameleon>
    export CHAMELEON_KEY_PATH=~/.ssh/id_ed25519        # matching private key
    export CHAMELEON_SECURITY_GROUP=<group allowing tcp/22>
    pytest -s tests/smoke/test_chameleon_smoke.py

Credentials are read from the "chameleon" entry of
~/.config/openstack/clouds.yaml. The test writes its cmx config to a
temporary directory, allocates its own floating IP (tagged with the VM
name) and releases it at the end, so no IP is taken from other users of a
shared project.
"""
import getpass
import os
import shutil
import subprocess
import time
import uuid

import pytest
import yaml

from cloudmesh.ai.common.stopwatch import StopWatch
from cloudmesh.ai.vm.openstack.OpenstackManager import OpenstackManager

FLAVOR = os.environ.get("CHAMELEON_FLAVOR", "m1.small")
OS_CLOUDS = os.path.expanduser("~/.config/openstack/clouds.yaml")


def has_chameleon_credentials():
    try:
        with open(OS_CLOUDS) as f:
            return "chameleon" in (yaml.safe_load(f) or {}).get("clouds", {})
    except OSError:
        return False


pytestmark = pytest.mark.skipif(
    not (has_chameleon_credentials() and shutil.which("openstack")),
    reason="needs a 'chameleon' entry in ~/.config/openstack/clouds.yaml and the openstack CLI",
)


def openstack(*args):
    env = {**os.environ, "OS_CLOUD": "chameleon"}
    return subprocess.run(["openstack", *args], env=env, capture_output=True, text=True, check=True).stdout.strip()


def test_chameleon_smoke():
    config = {
        "clouds": {
            "chameleon": {
                "image": os.environ.get("CHAMELEON_IMAGE", "CC-Ubuntu22.04"),
                "flavor": FLAVOR,
                "key_name": os.environ.get("CHAMELEON_KEY_NAME"),
                "key_path": os.environ.get("CHAMELEON_KEY_PATH", "~/.ssh/id_ed25519"),
                "security_group": os.environ.get("CHAMELEON_SECURITY_GROUP", "default"),
                "user": "cc",
            }
        }
    }
    provider = OpenstackManager(config, cloud_name="chameleon")
    vm_name = f"smoke-{getpass.getuser()}-{uuid.uuid4().hex[:6]}"
    floating_ip = None

    try:
        with StopWatch.timer("chameleon_start"):
            print(f"\nStarting VM {vm_name} on {FLAVOR}...")
            assert provider.start(vm_name)

        with StopWatch.timer("chameleon_wait_running"):
            assert provider.wait_for_status(vm_name, "Running", timeout=600) is True

        with StopWatch.timer("chameleon_info"):
            info = provider.info(vm_name)
            assert info["Name"] == vm_name
            assert info["PrivateIPs"], "VM should have a private IP"

        with StopWatch.timer("chameleon_list"):
            assert any(vm.get("name") == vm_name for vm in provider.list())

        with StopWatch.timer("chameleon_floating_ip"):
            floating_ip = openstack("floating", "ip", "create", "public", "--tag", vm_name,
                                    "-f", "value", "-c", "floating_ip_address")
            openstack("server", "add", "floating", "ip", vm_name, floating_ip)
            for _ in range(12):  # nova reports the new address after a few seconds
                if provider._get_floating_ip(vm_name) == floating_ip:
                    break
                time.sleep(5)
            assert provider._get_floating_ip(vm_name) == floating_ip

        with StopWatch.timer("chameleon_run"):
            output = ""
            for _ in range(30):  # wait for sshd to come up
                output = provider.run_command(vm_name, "hostname")
                if output == vm_name:
                    break
                time.sleep(10)
            assert output == vm_name, f"run_command over SSH failed: {output}"

        with StopWatch.timer("chameleon_stop"):
            assert provider.stop(vm_name) is True
            assert provider.wait_for_status(vm_name, "Stopped", timeout=300) is True

        with StopWatch.timer("chameleon_restart"):
            assert provider.restart(vm_name) is True
            assert provider.wait_for_status(vm_name, "Running", timeout=300) is True

        with StopWatch.timer("chameleon_delete"):
            assert provider.delete(vm_name) is True
            for _ in range(30):
                if not provider.exists(vm_name):
                    break
                time.sleep(5)
            assert not provider.exists(vm_name), f"VM {vm_name} should be gone"

        print("\nChameleon smoke test passed successfully!")

    finally:
        StopWatch.benchmark(tag=f"Chameleon Smoke {vm_name}")
        try:
            if provider.exists(vm_name):
                provider.delete(vm_name)
        except Exception:
            pass
        if floating_ip:
            try:
                openstack("floating", "ip", "delete", floating_ip)
            except Exception:
                pass
