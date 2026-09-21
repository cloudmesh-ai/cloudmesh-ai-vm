import os
import yaml
from cloudmesh.ai.command import vm
from cloudmesh.ai.command.vm._shared.context import state
from cloudmesh.ai.vm.state_manager import StateManager

def setup_cli_config(tmp_path, provider_name, config_data):
    """
    Sets up a temporary config file and injects it into the CLI's state proxy.
    """
    config_dir = tmp_path / ".config" / "cloudmesh"
    config_dir.mkdir(parents=True)
    config_file = config_dir / "clouds.yaml"
    
    # Merge provider config into the base config
    full_config = {
        "username": "smoke_test_user",
        "clouds": {
            provider_name: config_data
        }
    }
    
    with open(config_file, "w") as f:
        yaml.dump(full_config, f)
    
    # Inject a new StateManager instance into the global state proxy
    new_manager = StateManager(str(config_file))
    state.set_manager(new_manager)
    
    return str(config_file)
