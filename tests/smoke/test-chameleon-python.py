import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

import yaml

# Add the project root to sys.path so 'src' can be imported
project_root = Path(__file__).resolve().parents[2]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from benchmark_helper import save_benchmark
from cloudmesh.ai.common.dotdict import DotDict
from cloudmesh.ai.common.io import banner
from cloudmesh.ai.common.stopwatch import StopWatch
from cloudmesh.ai.common.util import path_expand

from cloudmesh.ai.vm.factory import factory
from cloudmesh.ai.vm.state_manager import StateManager

# Import Providers for registration
from src.cloudmesh.ai.vm.openstack.ChameleonManager import Provider as ChameleonProvider


def create_temp_config(tmp_path: Path, config: DotDict):
    """Creates a temporary clouds.yaml for the StateManager."""
    config_path = tmp_path / "clouds.yaml"
    data = {
        "clouds": {
            config.cloud: {
                "username": config.username,
                "image": config.image,
                "flavor": config.flavor,
                "key_name": config.key_name,
                "key_path": config.key_path,
                "enabled": True,
            }
        },
        "username": config.username,
        "default_cloud": config.cloud,
    }
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
    return str(config_path)


def generate_ssh_key(tmp_path: Path):
    key_path = tmp_path / "id_rsa"
    pub_key_path = tmp_path / "id_rsa.pub"
    subprocess.run(
        ["ssh-keygen", "-t", "rsa", "-b", "2048", "-f", str(key_path), "-N", ""],
        check=True,
        capture_output=True,
    )
    return str(key_path), str(pub_key_path)


def verify_key_presence(provider, vm_name, priv_key_path):
    try:
        info = provider.info(vm_name)
        ip = info.get("FloatingIP") or info.get("ip") or info.get("address")
        user = provider.get_cloud_config(provider.cloud_name).get("username", "ubuntu")
        result = provider._execute_ssh_command(ip, user, priv_key_path, "hostname")
        return "SSH Error" not in result
    except Exception as e:
        print(f"Error verifying key: {e}")
        return False


def run_smoke_test():
    banner("Loading clouds.yaml configuration for smoke tests")
    with open(
        path_expand("~/.config/cloudmesh/clouds.yaml"), "r", encoding="utf-8"
    ) as file:
        data = yaml.load(file, Loader=yaml.FullLoader)

    clouds_config = DotDict(data).clouds
    cloud_name = "chameleon"

    if cloud_name not in clouds_config:
        print(f"Error: {cloud_name} not found in clouds.yaml")
        sys.exit(1)

    # Use a single config DotDict for everything
    config = DotDict(
        {
            "name": cloud_name,
            "cloud": cloud_name,
            "provider_class": ChameleonProvider,
            "username": clouds_config.chameleon.username,
            "image": clouds_config.chameleon.image,
            "flavor": clouds_config.chameleon.flavor,
            "key_name": clouds_config.chameleon.key_name,
            "key_path": clouds_config.chameleon.key_path,
            "connectivity_strategy": "ssh_execute",
        }
    )

    banner(f"Loaded Provider Configuration: {cloud_name}")
    os.environ["OS_CLOUD"] = config.cloud

    StopWatch.clear()

    with tempfile.TemporaryDirectory() as temp_dir:
        tmp_path = Path(temp_dir)
        _priv_key_path, pub_key_path = generate_ssh_key(tmp_path)
        temp_config = create_temp_config(tmp_path, config)

        state = StateManager(temp_config)
        factory.register(config.name, config.provider_class)
        provider = factory.create(config.name, state.config)

        # 1. Provider Level Checks
        banner(f"Starting smoke test for: {config.name}")

        if hasattr(provider, "check_requirements"):
            with StopWatch.timer(f"{cloud_name}_check_reqs"):
                assert provider.check_requirements() is True, (
                    "Requirements check failed"
                )

        with StopWatch.timer(f"{cloud_name}_get_images"):
            assert isinstance(provider.get_images(), list), (
                "get_images should return a list"
            )

        with StopWatch.timer(f"{cloud_name}_get_flavors"):
            flavors = provider.get_flavors()
            assert isinstance(flavors, list) and len(flavors) > 0, (
                "get_flavors should return a non-empty list"
            )

        with StopWatch.timer(f"{cloud_name}_get_keys"):
            keys = provider.get_keys()
            assert isinstance(keys, list) and len(keys) > 0, (
                "get_keys should return a non-empty list"
            )

        # 2. Key Management Tests
        banner("Testing Key Management")
        key_name = f"smoke-key-{uuid.uuid4().hex[:6]}"

        with StopWatch.timer(f"{cloud_name}_upload_key"):
            assert provider.upload_key(pub_key_path, key_name) is True, (
                "upload_key failed"
            )

        with StopWatch.timer(f"{cloud_name}_delete_key"):
            assert provider.delete_key(key_name) is True, "delete_key failed"

        assert key_name not in provider.get_keys(), "Key should have been deleted"

        # 3. VM Lifecycle Tests
        banner("Testing VM Lifecycle")
        username = config.username.replace("_", "-")
        vm_name = f"smoke-lifecycle-{username}-{uuid.uuid4().hex[:6]}"

        try:
            # Ensure VM doesn't exist
            provider.delete(vm_name)
        except Exception:
            pass

        try:
            with StopWatch.timer(f"{cloud_name}_create_vm"):
                provider.create(vm_name, image=config.image, flavor=config.flavor)

            with StopWatch.timer(f"{cloud_name}_verify_vm"):
                assert provider.exists(vm_name) is True, (
                    "VM should exist after creation"
                )

            with StopWatch.timer(f"{cloud_name}_list_vms"):
                vms = provider.list()
                assert any(vm.get("name") == vm_name for vm in vms), (
                    "VM should be in the list"
                )

            print(f"\nSmoke test for {cloud_name} passed successfully!")

        finally:
            save_benchmark(tag=f"{cloud_name}-smoke", config_path=temp_config)
            try:
                if provider.exists(vm_name):
                    provider.delete(vm_name)
            except Exception:
                pass


if __name__ == "__main__":
    try:
        run_smoke_test()
    except Exception as e:
        print(f"Smoke test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    sys.exit(0)
