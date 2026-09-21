from abc import ABC
from typing import List, Dict, Any, Optional
from .exceptions import ProviderFeatureNotSupported

class BaseVMProvider(ABC):
    """
    Abstract Base Class for all VM providers.
    Ensures a consistent interface across different cloud providers.
    """
    
    def __init__(self, config: Any):
        self.config = config
        self.cloud_name = "base"

    def validate_config(self) -> Dict[str, List[str]]:
        """Validates the provider configuration. Returns a map of config paths to errors."""
        return {}

    # --- Lifecycle Methods ---
    def start(self, name: str) -> bool:
        raise ProviderFeatureNotSupported(self.cloud_name, "start")

    def stop(self, name: str) -> bool:
        raise ProviderFeatureNotSupported(self.cloud_name, "stop")

    def restart(self, name: str) -> bool:
        raise ProviderFeatureNotSupported(self.cloud_name, "restart")

    def suspend(self, name: str) -> bool:
        raise ProviderFeatureNotSupported(self.cloud_name, "suspend")

    def delete(self, name: str) -> bool:
        raise ProviderFeatureNotSupported(self.cloud_name, "delete")

    def run_command(self, name: str, command: str) -> Optional[str]:
        raise ProviderFeatureNotSupported(self.cloud_name, "run_command")

    def shelve(self, name: str) -> bool:
        raise ProviderFeatureNotSupported(self.cloud_name, "shelve")

    def unshelve(self, name: str) -> bool:
        raise ProviderFeatureNotSupported(self.cloud_name, "unshelve")

    # --- Inventory Methods ---
    def list(self) -> List[Dict[str, Any]]:
        """Lists all VMs in the cloud."""
        raise ProviderFeatureNotSupported(self.cloud_name, "list")

    def info(self, name: str) -> Dict[str, Any]:
        """Gets detailed info for a specific VM."""
        raise ProviderFeatureNotSupported(self.cloud_name, "info")

    def get_images(self) -> List[Dict[str, Any]]:
        """Lists available VM image."""
        raise ProviderFeatureNotSupported(self.cloud_name, "get_images")

    def get_flavors(self) -> List[Dict[str, Any]]:
        """Lists available hardware profiles."""
        raise ProviderFeatureNotSupported(self.cloud_name, "get_flavors")

    def get_provider_info(self) -> Dict[str, Any]:
        """Gets detailed information about the provider configuration and status."""
        raise ProviderFeatureNotSupported(self.cloud_name, "get_provider_info")


    # --- Identity & Security Methods ---
    def get_keys(self) -> List[Dict[str, Any]]:
        """Lists available SSH keys."""
        raise ProviderFeatureNotSupported(self.cloud_name, "get_keys")

    def upload_key(self, key_path: str, key_name: str) -> bool:
        """Uploads a public key."""
        raise ProviderFeatureNotSupported(self.cloud_name, "upload_key")

    def delete_key(self, key_name: str) -> bool:
        """Deletes a public key."""
        raise ProviderFeatureNotSupported(self.cloud_name, "delete_key")

    def get_security_groups(self) -> List[Dict[str, Any]]:
        """Lists available security groups."""
        raise ProviderFeatureNotSupported(self.cloud_name, "get_security_groups")

    def get_security_group_info(self, name: str) -> Dict[str, Any]:
        """Gets detailed information for a specific security group."""
        raise ProviderFeatureNotSupported(self.cloud_name, "get_security_group_info")

    # --- Network Methods ---
    def list_regions(self) -> List[Dict[str, Any]]:
        """Lists available regions."""
        raise ProviderFeatureNotSupported(self.cloud_name, "list_regions")

    def assign_floating_ip(self, name: str) -> Optional[str]:
        """Assigns a floating IP to the VM."""
        raise ProviderFeatureNotSupported(self.cloud_name, "assign_floating_ip")

    def release_floating_ip(self, name: str) -> bool:
        """Releases a floating IP from the VM."""
        raise ProviderFeatureNotSupported(self.cloud_name, "release_floating_ip")

    # --- Cost Methods ---
    def get_cost(self, **kwargs) -> Any:
        """Calculates the cost for a VM configuration."""
        raise ProviderFeatureNotSupported(self.cloud_name, "get_cost")
