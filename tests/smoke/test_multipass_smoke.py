import os
import yaml
import pytest
from cloudmesh.ai.vm.state_manager import StateManager
from cloudmesh.ai.vm.factory import factory
from cloudmesh.ai.vm.local.MultipassManager import Provider as MultipassProvider

# Register the provider in the factory for the test
factory.register("multipass", MultipassProvider)

@pytest.fixture
def temp_config(tmp_path):
    """Create a temporary clouds.yaml for testing."""
    config_dir = tmp_path / ".config" / "cloudmesh"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "clouds.yaml"
    
    config_data = {
        "username": "smoke_test_user",
        "clouds": {
            "multipass": {
                "image": "22.04"
            }
        }
    }
    
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
        
    return str(config_file)

def test_multipass_smoke(temp_config):
    """
    Smoke test for Multipass provider: 
    Start -> List -> Stop -> Delete
    """
    state = StateManager(temp_config)
    provider = factory.create("multipass", state.config)
    
    vm_name = "smoke-test-vm"
    
    try:
        # 0. Cleanup any existing VM with the same name
        print(f"Cleaning up existing VM {vm_name} if it exists...")
        provider.delete(vm_name)


        # 1. Start VM
        print(f"\nStarting VM {vm_name}...")
        provider.start(vm_name)
        
        # 2. List VM and verify it exists
        print("Verifying VM in list...")
        vms = provider.list()
        vm_exists = any(vm.get("Name") == vm_name for vm in vms)
        assert vm_exists, f"VM {vm_name} should exist in the list"
        
        # 3. Stop VM
        print(f"Stopping VM {vm_name}...")
        assert provider.stop(vm_name) is True, "Should successfully stop VM"
        
        # 4. Delete VM
        print(f"Deleting VM {vm_name}...")
        assert provider.delete(vm_name) is True, "Should successfully delete VM"
        
        # 5. Verify VM is gone
        print("Verifying VM is deleted...")
        vms = provider.list()
        vm_exists = any(vm.get("Name") == vm_name for vm in vms)
        assert not vm_exists, f"VM {vm_name} should be gone from the list"
        
        print("\nSmoke test passed successfully!")
        
    finally:
        # Cleanup in case of failure
        provider.delete(vm_name)
