import pytest
from cloudmesh.ai.vm.factory import factory
from cloudmesh.ai.vm.state_manager import StateManager

@pytest.fixture(scope="session", autouse=True)
def smoke_cleanup():
    """
    Session-level fixture to clean up all VMs starting with 'smoke-' 
    across all registered providers after all smoke tests have run.
    """
    yield
    
    try:
        # Use the default StateManager to get credentials from ~/.config/cloudmesh/clouds.yaml
        state = StateManager()
        config = state.config
    except Exception as e:
        print(f"Could not load default config for smoke cleanup: {e}")
        return

    # Iterate over all providers registered in the factory
    for p_name in list(factory._registry.keys()):
        try:
            # Create the provider instance using the default config
            provider = factory.create(p_name, config)
            
            # List all VMs for this provider
            vms = provider.list()
            if not vms:
                continue
            
            # Filter and delete VMs starting with 'smoke-'
            for vm in vms:
                name = vm.get("name")
                if name and name.startswith("smoke-"):
                    print(f"Cleaning up smoke VM {name} on {p_name}...")
                    provider.delete(name)
                    
        except Exception as e:
            # Ignore providers that are not configured or fail to initialize
            # We don't want to fail the test suite because a provider we don't use is missing
            pass
