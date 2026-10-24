import shutil
import subprocess
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import pytest
import yaml
from cloudmesh.ai.common.dotdict import DotDict
from cloudmesh.ai.common.stopwatch import StopWatch

from cloudmesh.ai.vm.factory import factory
from cloudmesh.ai.vm.state_manager import StateManager
from src.cloudmesh.ai.vm.local.LimaManager import Provider as LimaProvider
from src.cloudmesh.ai.vm.local.MultipassManager import Provider as MultipassProvider
from src.cloudmesh.ai.vm.local.VBoxManager import Provider as VBoxProvider
from src.cloudmesh.ai.vm.local.Wsl2Manager import Provider as Wsl2Provider

# Import Providers for registration
from src.cloudmesh.ai.vm.openstack.ChameleonManager import Provider as ChameleonProvider
from src.cloudmesh.ai.vm.openstack.OpenstackManager import OpenstackManager
from tests.smoke.benchmark_helper import save_benchmark


@dataclass
class ProviderTestConfig:
    name: str
    provider_class: Any
    cloud_config: dict[str, Any]
    running_status: str = "Running"
    stopped_status: str = "Stopped"
    connectivity_strategy: str = (
        "run_command"  # run_command, ssh_execute, multipass_exec
    )
    has_shelve: bool = False
    skip_condition: Callable[[], bool] | None = None
    # Custom hooks for provider-specific verification
    custom_verify_key: Callable[[Any, str, str, str], bool] | None = None


# --- Connectivity & Key Verification Strategies ---


def verify_connectivity_run_command(provider, vm_name):
    hostname = provider.run_command(vm_name, "hostname")
    return hostname is not None and "Error" not in hostname


def verify_connectivity_ssh_execute(
    provider, vm_name, priv_key_path, retries=12, delay=10
):
    info = provider.info(vm_name)
    ip = info.get("FloatingIP") or info.get("ip") or info.get("address")
    if not ip:
        return False
    user = provider.get_cloud_config(provider.cloud_name).get("user", "ubuntu")

    for attempt in range(retries):
        hostname = provider._execute_ssh_command(
            ip,
            user,
            priv_key_path,
            "hostname",
        )

        if "SSH Error" not in hostname:
            return True

        if attempt < retries - 1:
            time.sleep(delay)

    return False



def verify_connectivity_multipass_exec(provider, vm_name):
    # Multipass uses a specific CLI execution
    result = subprocess.run(
        ["multipass", "exec", vm_name, "--", "hostname"], check=False, capture_output=True, text=True
    )
    return result.returncode == 0


def verify_key_presence(provider, vm_name, pub_key_path, priv_key_path, strategy):
    with open(pub_key_path, "r") as f:
        pub_key_content = f.read().strip()
    escaped_key = pub_key_content.replace("'", "'\\''")
    verify_cmd = f"grep -q '{escaped_key}' ~/.ssh/authorized_keys"

    if strategy == "run_command":
        # We try to run it via run_command, but run_command usually returns stdout.
        # For grep -q, we might need to check if it didn't error.
        # However, run_command often returns "Error" on non-zero exit.
        result = provider.run_command(vm_name, verify_cmd)
        return "Error" not in result

    elif strategy == "ssh_execute":
        info = provider.info(vm_name)
        ip = info.get("FloatingIP") or info.get("ip") or info.get("address")
        user = provider.get_cloud_config(provider.cloud_name).get("user", "ubuntu")
        result = provider._execute_ssh_command(ip, user, priv_key_path, verify_cmd)
        return "SSH Error" not in result

    elif strategy == "multipass_exec":
        result = subprocess.run(
            ["multipass", "exec", vm_name, "--", "bash", "-c", verify_cmd],
            check=False, capture_output=True,
        )
        return result.returncode == 0

    return False


from pprint import pprint

from cloudmesh.ai.common.util import path_expand

# Open the file normally, then pass it to yaml.load with the Loader argument
with open(
    path_expand("~/.config/cloudmesh/clouds.yaml"), "r", encoding="utf-8"
) as file:
    data = yaml.load(file, Loader=yaml.FullLoader)

# Now 'data' is a standard Python dictionary
pprint(data)

config = DotDict(data)


PROVIDER_CONFIGS = [
    ProviderTestConfig(
        name="chameleon",
        provider_class=ChameleonProvider,
        cloud_config={
            "image": config.clouds.chameleon.image,
            "flavor": config.clouds.chameleon.flavor,
            "username": config.clouds.chameleon.username,
            "key_name": config.clouds.chameleon.key_name,
            "key_path": config.clouds.chameleon.key_path,
        },
        running_status="active",
        stopped_status="stopped",
        connectivity_strategy="ssh_execute",
    ),
    ProviderTestConfig(
        name="jetstream",
        provider_class=OpenstackManager,
        cloud_config={
            "image": "Featured-Ubuntu22",
            "flavor": config.clouds.jetstream.flavor,
        },
        running_status="active",
        stopped_status="Stopped",
        connectivity_strategy="run_command",
        skip_condition=lambda: not shutil.which("openstack"),
    ),
    ProviderTestConfig(
        name="lima",
        provider_class=LimaProvider,
        cloud_config={"image": "ubuntu-22.04"},
        running_status="Running",
        stopped_status="Stopped",
        connectivity_strategy="run_command",
    ),
    ProviderTestConfig(
        name="multipass",
        provider_class=MultipassProvider,
        cloud_config={"image": "22.04"},
        running_status="Running",
        stopped_status="Stopped",
        connectivity_strategy="multipass_exec",
        has_shelve=True,
    ),
    ProviderTestConfig(
        name="vbox",
        provider_class=VBoxProvider,
        cloud_config={"image": "ubuntu-22.04"},
        running_status="Running",
        stopped_status="Stopped",
        connectivity_strategy="run_command",
    ),
    ProviderTestConfig(
        name="wsl2",
        provider_class=Wsl2Provider,
        cloud_config={
            "rootfs": "C:\\path\\to\\rootfs.tar",
            "install_dir": "C:\\WSL_Smoke",
            "wsl_username": "smoke_user",
            "host_username": "smoke_host",
        },
        running_status="Running",
        stopped_status="Stopped",
        connectivity_strategy="run_command",
        skip_condition=lambda: not (shutil.which("wsl.exe") or shutil.which("wsl")),
    ),
]

# --- Fixtures ---


@pytest.fixture
def ssh_key(tmp_path):
    key_path = tmp_path / "id_rsa"
    pub_key_path = tmp_path / "id_rsa.pub"
    subprocess.run(
        ["ssh-keygen", "-t", "rsa", "-b", "2048", "-f", str(key_path), "-N", ""],
        check=True,
        capture_output=True,
    )
    return str(key_path), str(pub_key_path)


def create_temp_config(tmp_path, provider_cfg, pub_key_path=None):
    config_dir = tmp_path / ".config" / "cloudmesh"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "clouds.yaml"
    cloud_config = dict(provider_cfg.cloud_config)
    cloud_config.setdefault("username", "smoke_test_user")

    if provider_cfg.name == "chameleon" and pub_key_path:
        cloud_config["key_path"] = pub_key_path
        cloud_config["user"] = "cc"

    config_data = {
        "clouds": {
            provider_cfg.name: cloud_config

        }
    }

    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    return str(config_file)


# --- Unified Test ---


@pytest.mark.parametrize("provider_cfg", PROVIDER_CONFIGS, ids=lambda x: x.name)
def test_provider_lifecycle(provider_cfg, tmp_path, ssh_key):
    # Clear previous timers to prevent cross-provider pollution
    StopWatch.clear()

    if provider_cfg.skip_condition and provider_cfg.skip_condition():
        pytest.skip(f"Skip condition met for {provider_cfg.name}")

    priv_key_path, pub_key_path = ssh_key

    # Use the helper function to create config instead of a fixture
    temp_config = create_temp_config(tmp_path, provider_cfg, pub_key_path)
    state = StateManager(temp_config)

    # Register and create provider
    factory.register(provider_cfg.name, provider_cfg.provider_class)
    provider = factory.create(provider_cfg.name, state.config)

    # 1. Provider Level Checks
    if hasattr(provider, "check_requirements"):
        with StopWatch.timer(f"{provider_cfg.name}_check_reqs"):
            assert provider.check_requirements() is True

    with StopWatch.timer(f"{provider_cfg.name}_get_images"):
        images = provider.get_images()
        assert isinstance(images, list)

    with StopWatch.timer(f"{provider_cfg.name}_get_flavors"):
        flavors = provider.get_flavors()
        assert isinstance(flavors, list)
        assert len(flavors) > 0

    # VM Name generation
    cloud_config = provider.get_cloud_config(provider_cfg.name)
    raw_username = cloud_config.get("username", "user")
    username = raw_username.replace("_", "-")
    vm_name = f"test-{username}-smoke-{uuid.uuid4().hex[:6]}"

    try:
        # 0. Cleanup
        try:
            provider.delete(vm_name)
        except Exception:
            pass

        # 1. Start VM
        with StopWatch.timer(f"{provider_cfg.name}_start"):
            print(f"\nStarting VM {vm_name}...")
            # Some providers return server ID, some return None
            provider.start(name=vm_name)

        # Wait for running status
        with StopWatch.timer(f"{provider_cfg.name}_wait_running"):
            assert (
                provider.wait_for_status(
                    vm_name, provider_cfg.running_status, timeout=600
                )
                is True
            )

        # 2. Connectivity Check
        with StopWatch.timer(f"{provider_cfg.name}_connectivity"):
            if provider_cfg.connectivity_strategy == "run_command":
                assert verify_connectivity_run_command(provider, vm_name)
            elif provider_cfg.connectivity_strategy == "ssh_execute":
                assert verify_connectivity_ssh_execute(provider, vm_name, priv_key_path)
            elif provider_cfg.connectivity_strategy == "multipass_exec":
                assert verify_connectivity_multipass_exec(provider, vm_name)
            else:
                pytest.fail(
                    f"Unknown connectivity strategy: {provider_cfg.connectivity_strategy}"
                )

        # 3. SSH Key Management
        with StopWatch.timer(f"{provider_cfg.name}_upload_key"):
            assert provider.upload_key(pub_key_path, "smoke-key", vm_name) is True

        with StopWatch.timer(f"{provider_cfg.name}_verify_key"):
            assert (
                verify_key_presence(
                    provider,
                    vm_name,
                    pub_key_path,
                    priv_key_path,
                    provider_cfg.connectivity_strategy,
                )
                is True
            )

        with StopWatch.timer(f"{provider_cfg.name}_delete_key"):
            assert provider.delete_key("smoke-key", vm_name) is True

        with StopWatch.timer(f"{provider_cfg.name}_verify_key_deleted"):
            # We check that the key is NOT present
            assert not verify_key_presence(
                provider,
                vm_name,
                pub_key_path,
                priv_key_path,
                provider_cfg.connectivity_strategy,
            )

        # 4. Provider-specific features (e.g. Shelve)
        if provider_cfg.has_shelve:
            with StopWatch.timer(f"{provider_cfg.name}_shelve"):
                assert provider.shelve(vm_name) is True
                assert (
                    provider.wait_for_status(
                        vm_name, provider_cfg.stopped_status, timeout=60
                    )
                    is True
                )
            with StopWatch.timer(f"{provider_cfg.name}_unshelve"):
                assert provider.unshelve(vm_name) is True
                assert (
                    provider.wait_for_status(
                        vm_name, provider_cfg.running_status, timeout=60
                    )
                    is True
                )

        # 5. Info and List
        with StopWatch.timer(f"{provider_cfg.name}_info"):
            info = provider.info(vm_name)
            assert info is not None

        with StopWatch.timer(f"{provider_cfg.name}_list"):
            vms = provider.list()
            assert any(vm.get("name") == vm_name for vm in vms)

        # 6. Stop and Delete
        with StopWatch.timer(f"{provider_cfg.name}_stop"):
            assert provider.stop(vm_name) is True
            assert (
                provider.wait_for_status(
                    vm_name, provider_cfg.stopped_status, timeout=600
                )
                is True
            )

        with StopWatch.timer(f"{provider_cfg.name}_delete"):
            assert provider.delete(vm_name) is True
            vms = provider.list()
            assert not any(vm.get("name") == vm_name for vm in vms)

        print(f"\nSmoke test for {provider_cfg.name} passed successfully!")

    finally:
        save_benchmark(tag=f"{provider_cfg.name}-smoke", config_path=temp_config)
        try:
            if provider.exists(vm_name):
                provider.delete(vm_name)
        except Exception:
            pass
