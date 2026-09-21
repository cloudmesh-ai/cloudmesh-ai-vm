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
        self._raw_config = {}
        self.config: Optional[GlobalConfig] = self._load_config()

    def _load_config(self) -> GlobalConfig:
        if not os.path.exists(self.config_path):
            logger.warning(f"Config file not found at {self.config_path}. Using defaults.")
            self._raw_config = {}
            return GlobalConfig(username="user", counter=0, default_cloud="")

        try:
            with open(self.config_path, 'r') as f:
                self._raw_config = yaml.safe_load(f) or {}
                return GlobalConfig.from_dict(self._raw_config)
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
            self._raw_config = {}
            return GlobalConfig(username="user", counter=0, default_cloud="")

    def save(self):
        """Saves the current state back to the YAML file, preserving unknown fields."""
        try:
            # Start with a copy of the raw config to preserve unknown fields
            data = self._raw_config.copy() if self._raw_config else {}
            
            # Update global fields
            data["username"] = self.config.username
            data["counter"] = self.config.counter
            data["default_cloud"] = self.config.default_cloud
            data["last_vm"] = self.config.last_vm
            
            # Update clouds section
            clouds_data = data.get("clouds", {})
            if not isinstance(clouds_data, dict):
                clouds_data = {}
                
            for name, cfg in self.config.clouds.items():
                # Get existing cloud data to preserve its unknown fields
                existing_cloud_data = clouds_data.get(name, {})
                if not isinstance(existing_cloud_data, dict):
                    existing_cloud_data = {}
                
                # Merge dataclass values into the existing cloud data
                updated_cloud_data = {**existing_cloud_data, **cfg.__dict__}
                # Remove None values to keep yaml clean
                updated_cloud_data = {k: v for k, v in updated_cloud_data.items() if v is not None}
                clouds_data[name] = updated_cloud_data
            
            data["clouds"] = clouds_data
            
            # Final cleanup of None values in global section
            data = {k: v for k, v in data.items() if v is not None}

            with open(self.config_path, 'w') as f:
                yaml.dump(data, f, default_flow_style=False)
        except Exception as e:
            logger.error(f"Error saving config file: {e}")

    def increment_counter(self) -> int:
        self.config.counter += 1
        self.save()
        return self.config.counter

    def set_last_vm(self, cloud_name: str, vm_name: str):
        self.config.last_vm[cloud_name] = vm_name
        self.save()

    def get_last_vm(self, cloud_name: str) -> Optional[str]:
        return self.config.last_vm.get(cloud_name)
