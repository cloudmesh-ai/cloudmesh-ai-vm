import os
from typing import Optional, Dict, Any
from yamldb import YamlDB
from cloudmesh.ai.vm.logger import logger

class StateManager:
    """
    Handles persistent state for cloudmesh-ai-vm using yamldb.
    Provides dynamic access to the YAML configuration.
    """
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.db = YamlDB(filename=config_path)

    def get_cloud_config(self, cloud_name: str) -> Dict[str, Any]:
        """
        Retrieves configuration for a specific cloud.
        Returns a dictionary to maintain backward compatibility with providers.
        """
        config = self.db.get(f"clouds.{cloud_name}")
        return config if isinstance(config, dict) else {}

    def increment_counter(self) -> int:
        """Increments the global VM counter and saves it."""
        counter = self.db.get("counter", 0) or 0
        new_counter = counter + 1
        self.db.set("counter", new_counter)
        return new_counter

    def set_last_vm(self, cloud_name: str, vm_name: str):
        """Sets the last used VM for a specific cloud."""
        self.db.set(f"last_vm.{cloud_name}", vm_name)

    def get_last_vm(self, cloud_name: str) -> Optional[str]:
        """Gets the last used VM for a specific cloud."""
        return self.db.get(f"last_vm.{cloud_name}")

    @property
    def config(self):
        """
        Returns self to act as the config object.
        This allows state.config.get_cloud_config(...) to continue working.
        """
        return self
