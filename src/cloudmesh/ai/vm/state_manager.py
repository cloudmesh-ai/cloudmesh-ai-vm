import yaml
import os
from typing import Optional
from cloudmesh.ai.vm.config_models import GlobalConfig
from cloudmesh.ai.vm.logger import logger

class StateManager:
    """
    Handles persistent state for cloudmesh-ai-vm, including VM counters
    and the last used VM.
    """
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config: Optional[GlobalConfig] = self._load_config()

    def _load_config(self) -> GlobalConfig:
        if not os.path.exists(self.config_path):
            logger.warning(f"Config file not found at {self.config_path}. Using defaults.")
            return GlobalConfig(username="user", counter=0, default_cloud="")

        try:
            with open(self.config_path, 'r') as f:
                data = yaml.safe_load(f) or {}
                return GlobalConfig.from_dict(data)
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
            return GlobalConfig(username="user", counter=0, default_cloud="")

    def save(self):
        """Saves the current state back to the YAML file."""
        try:
            # Convert dataclass to dict for yaml dump
            data = {
                "username": self.config.username,
                "counter": self.config.counter,
                "default_cloud": self.config.default_cloud,
                "last_vm": self.config.last_vm,
                "clouds": {name: cfg.__dict__ for name, cfg in self.config.clouds.items()}
            }
            # Remove None values to keep yaml clean
            def clean_nones(d):
                if not isinstance(d, dict): return d
                return {k: clean_nones(v) for k, v in d.items() if v is not None}

            with open(self.config_path, 'w') as f:
                yaml.dump(clean_nones(data), f, default_flow_style=False)
        except Exception as e:
            logger.error(f"Error saving config file: {e}")

    def increment_counter(self) -> int:
        self.config.counter += 1
        self.save()
        return self.config.counter

    def set_last_vm(self, vm_name: str):
        self.config.last_vm = vm_name
        self.save()

    def get_last_vm(self) -> Optional[str]:
        return self.config.last_vm
