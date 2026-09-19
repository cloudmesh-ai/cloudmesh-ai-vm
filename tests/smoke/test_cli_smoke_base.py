import os
import yaml
import pytest
from click.testing import CliRunner
from cloudmesh.ai.command.vm import vm_group

class CLISmokeTestBase:
    def __init__(self, provider_name, config_data):
        self.provider_name = provider_name
        self.config_data = config_data
        self.runner = CliRunner()

    def setup_config(self, tmp_path):
        config_dir = tmp_path / ".config" / "cloudmesh"
        config_dir.mkdir(parents=True)
        config_file = config_dir / "clouds.yaml"
        
        with open(config_file, "w") as f:
            yaml.dump(self.config_data, f)
        
        # Set environment variable for the CLI to find the config
        # Note: The CLI uses os.path.expanduser("~/.config/cloudmesh/clouds.yaml")
        # We need to monkeypatch this or set an environment variable if the app supports it.
        # Since the app uses a hardcoded path, we might need to monkeypatch StateManager.
        return str(config_file)

    def run_vm_cmd(self, args, config_path):
        # We need to make sure StateManager uses the temp_config
        # This is tricky because state is a global object in vm.py
        from cloudmesh.ai.command import vm
        vm.state.CONFIG_PATH = config_path
        # Reload state config
        vm.state.load_config()
        
        return self.runner.invoke(vm_group, args)
