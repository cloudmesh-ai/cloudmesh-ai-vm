import sys
import os
import yaml
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from cloudmesh.ai.vm.state_manager import StateManager
from cloudmesh.ai.vm.factory import factory
from cloudmesh.ai.vm.local.MultipassManager import Provider as MultipassProvider

#register the Multipass provider
factory.register("multipass", MultipassProvider)

@pytest.fixture
def temp_config(tmp_path):
    """Create a temporary configuration file for testing."""
    config_dir = tmp_path / ".config" / "cloudmesh"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.yaml"
    config_data = {
        "username": "smoke_test_user",
        "clouds": {
            "multipass": {
                "image": "22.04",
                "cpus": 1,
                "memory": "1GiB",
                "disk": "5GiB"
            }
        }
    }
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)

    return str(config_file)

def test_multipass_lifecycle(temp_config):
    state = StateManager(temp_config)
    provider = factory.create("multipass", state.config)

    vm_name = "test-vm-user"

    try:
       print(f"Cleaning up VM {vm_name} before test.")
       provider.delete(vm_name)
    except Exception as e:
        print(f"Error cleaning up VM {vm_name}: {e}")

    #Start VM
    print (f"\n[Starting VM]: {vm_name}...")
    start_res = provider.start(name=vm_name)
    assert start_res is not None

    #Wait for the VM to be ready
    provider.wait_for_status(name=vm_name, target_status = "Running", timeout=60)

    #Test info/status
    print (f"[Fetching info for VM]: {vm_name}")
    info = provider.info(name=vm_name)
    assert info is not None

    #Test List
    print (f"[Listing VMs]")
    vm_list = provider.list()
    assert any(vm.get("name") == vm_name for vm in vm_list), f"VM {vm_name} not found in the list"

    #Test Stop
    print (f"[Stopping VM]: {vm_name}")
    provider.stop(name=vm_name)
    provider.wait_for_status(name=vm_name, target_status = "Stopped", timeout=60)

    #Test Delete
    print(f"[Deleting VM]: {vm_name}")
    provider.delete(name=vm_name)
