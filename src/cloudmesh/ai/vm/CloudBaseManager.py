from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from rich.text import Text
from .base import BaseVMProvider

class CloudBaseManager(BaseVMProvider, ABC):
    """
    Abstract Base Class for Cloud VM Managers.
    All cloud providers (OpenStack, Multipass, etc.) must implement this interface.
    """

    def __init__(self, config: Any, console=None, **kwargs):
        super().__init__(config)
        self.console = console

    def get_cloud_config(self, cloud_name: str) -> Dict[str, Any]:
        """
        Helper to retrieve configuration for a specific cloud, 
        handling both dictionary, StateManager, and GlobalConfig object inputs.
        """
        # 1. Handle StateManager (YamlDB)
        if hasattr(self.config, "get_cloud_config") and callable(getattr(self.config, "get_cloud_config")):
            return self.config.get_cloud_config(cloud_name)

        # 2. Handle plain dictionary
        if isinstance(self.config, dict):
            return self.config.get("clouds", {}).get(cloud_name, {})
        
        # 3. Handle GlobalConfig object (dataclass)
        clouds = getattr(self.config, "clouds", {})
        if isinstance(clouds, dict):
            cloud_cfg = clouds.get(cloud_name, {})
        else:
            # Fallback if clouds is not a dict
            return {}
        
        # If the cloud_cfg is a dataclass (ProviderConfig), convert to dict
        if not isinstance(cloud_cfg, dict) and hasattr(cloud_cfg, "__dict__"):
            return cloud_cfg.__dict__
        
        return cloud_cfg if isinstance(cloud_cfg, dict) else {}

    # We remove @abstractmethod from methods that are not mandatory for all providers.
    # BaseVMProvider already provides default implementations that raise ProviderFeatureNotSupported.
    
    def start(self, name: Optional[str] = None, flavor: Optional[str] = None, image: Optional[str] = None) -> str:
        """Starts a VM."""
        return super().start(name)

    def stop(self, name: Optional[str] = None) -> bool:
        """Stops a VM."""
        return super().stop(name)

    def delete(self, name: Optional[str] = None) -> bool:
        """Deletes a VM."""
        return super().delete(name)

    def list(self) -> List[Dict[str, Any]]:
        """Lists all VMs managed by this provider."""
        return super().list()

    def login(self, name: Optional[str] = None) -> bool:
        """Logs into a VM."""
        return super().login(name)

    def suspend(self, name: Optional[str] = None) -> bool:
        """Suspends a VM."""
        return super().suspend(name)

    def shelve(self, name: Optional[str] = None) -> bool:
        """Shelves a VM."""
        return super().shelve(name)

    def unshelve(self, name: Optional[str] = None) -> bool:
        """Unshelves a VM."""
        return super().unshelve(name)

    def restart(self, name: Optional[str] = None) -> bool:
        """Restarts a VM."""
        return super().restart(name)

    def info(self, name: str) -> Dict[str, Any]:
        """Gets detailed information about a specific VM."""
        return super().info(name)

    def get_security_groups(self) -> List[Dict[str, Any]]:
        """Lists available security groups for the current cloud."""
        return []

    def upload_key(self, key_path: str, key_name: str) -> bool:
        """Uploads a public key to the cloud provider."""
        return False

    def delete_key(self, key_name: str) -> bool:
        """Deletes a public key from the cloud provider."""
        return False

    def get_cost(self, **kwargs) -> Optional[Any]:
        """Returns the cost information for the provider."""
        return None

    def validate_config(self) -> Dict[str, List[str]]:
        """Validates that the cloud configuration has all required fields."""
        return {}

    def add_security_group_rule(self, group_name: str, port: int, protocol: str = "tcp", cidr: str = "0.0.0.0/0") -> bool:
        """Adds a security group rule to allow traffic on a specific port."""
        return False

    def print(self, *args, **kwargs):
        """Helper to print output using the associated rich console if available."""
        if self.console:
            self.console.print(*args, **kwargs)
        else:
            print(*args, **kwargs)

    def print_ansi(self, text: str, **kwargs):
        """Prints text and cleans up ANSI sequences and CLI spinner artifacts."""
        if self.console:
            self.console.print(Text.from_ansi(text), **kwargs)
        else:
            print(text, **kwargs)

    def _run_interactive(self, command: List[str]):
        """Runs a command directly connected to the terminal for smooth animations."""
        import subprocess
        try:
            return subprocess.run(command, capture_output=False, check=True)
        except subprocess.CalledProcessError as e:
            raise e
