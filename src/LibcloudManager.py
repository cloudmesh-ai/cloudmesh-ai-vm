from typing import List, Dict, Any, Optional
from src.CloudBaseManager import CloudBaseManager

try:
    from libcloud.compute.types import Provider as LibcloudProvider
except ImportError:
    class LibcloudProvider: pass

class LibcloudManager(CloudBaseManager):
    """
    General Manager for cloud providers supported by libcloud.
    Implements common VM operations using the libcloud unified API.
    """

    def __init__(self, config: Dict[str, Any], cloud_name: str):
        super().__init__(config)
        self.cloud_name = cloud_name
        self.driver = self._get_driver()

    def _get_driver(self):
        """
        Initialize the libcloud driver. 
        Must be implemented by specific provider managers.
        """
        raise NotImplementedError("Subclasses must implement _get_driver()")

    def start(self, name: Optional[str] = None) -> str:
        """
        Creates and starts a VM in the cloud.
        """
        cloud_config = self.config.get("clouds", {}).get(self.cloud_name, {})
        image_name = cloud_config.get("image")
        size_name = cloud_config.get("size") or cloud_config.get("flavour")
        
        if not image_name or not size_name:
            raise ValueError(f"Image or Size/Flavour missing in config for {self.cloud_name}")

        # Resolve image
        images = self.driver.list_images()
        image = next((img for img in images if img.name == image_name), None)
        
        # Resolve size
        sizes = self.driver.list_sizes()
        size = next((s for s in sizes if s.id == size_name or s.name == size_name), None)

        if not image or not size:
            raise RuntimeError(f"Could not find image {image_name} or size {size_name} in {self.cloud_name}")

        try:
            node = self.driver.create_node(name=name, image=image, size=size)
        except TypeError:
            node = self.driver.create_node(name=name)

        return node.name

    def stop(self, name: Optional[str] = None) -> bool:
        """
        Stops a VM.
        """
        if not name: return False
        try:
            node = self.driver.get_node(name)
            self.driver.stop_node(node)
            return True
        except Exception as e:
            print(f"Error stopping node {name}: {e}")
            return False

    def delete(self, name: Optional[str] = None) -> bool:
        """
        Deletes a VM.
        """
        if not name: return False
        try:
            node = self.driver.get_node(name)
            self.driver.destroy_node(node)
            return True
        except Exception as e:
            print(f"Error deleting node {name}: {e}")
            return False

    def list(self) -> List[Dict[str, Any]]:
        """
        Lists all VMs.
        """
        try:
            nodes = self.driver.list_nodes()
            return [{"Name": n.name, "ID": n.id, "State": n.state} for n in nodes]
        except Exception as e:
            print(f"Error listing nodes: {e}")
            return []

    def login(self, name: Optional[str] = None) -> bool:
        """
        Default login implementation (usually SSH).
        """
        if not name: return False
        print(f"Please use SSH to log into the VM: {name}")
        return False

    def suspend(self, name: Optional[str] = None) -> bool:
        """
        Suspends a VM if supported.
        """
        if not name: return False
        try:
            node = self.driver.get_node(name)
            if hasattr(self.driver, 'suspend_node'):
                self.driver.suspend_node(node)
                return True
            print(f"Suspend not supported by {self.cloud_name} driver.")
            return False
        except Exception as e:
            print(f"Error suspending node {name}: {e}")
            return False

    def restart(self, name: Optional[str] = None) -> bool:
        """
        Restarts a VM.
        """
        if not name: return False
        try:
            node = self.driver.get_node(name)
            if hasattr(self.driver, 'reboot_node'):
                self.driver.reboot_node(node)
                return True
            print(f"Restart not supported by {self.cloud_name} driver.")
            return False
        except Exception as e:
            print(f"Error restarting node {name}: {e}")
            return False

    def get_flavors(self) -> List[Dict[str, Any]]:
        """
        Lists available sizes/flavors in the cloud.
        """
        try:
            sizes = self.driver.list_sizes()
            return [{"id": s.id, "name": s.name, "ram": getattr(s, 'ram', 'N/A'), "vcpus": getattr(s, 'vcpus', 'N/A')} for s in sizes]
        except Exception as e:
            print(f"Error getting flavors for {self.cloud_name}: {e}")
            return []

    def get_keys(self) -> List[Dict[str, Any]]:
        """
        Lists available SSH keys in the cloud.
        """
        try:
            if hasattr(self.driver, 'list_keys'):
                keys = self.driver.list_keys()
                return [{"name": k.name, "fingerprint": getattr(k, 'fingerprint', 'N/A')} for k in keys]
            print(f"Key listing not supported by {self.cloud_name} driver.")
            return []
        except Exception as e:
            print(f"Error getting keys for {self.cloud_name}: {e}")
            return []

    def get_security_groups(self) -> List[Dict[str, Any]]:
        """
        Lists available security groups in the cloud.
        """
        try:
            if hasattr(self.driver, 'list_securitygroups'):
                groups = self.driver.list_securitygroups()
                return [{"name": g.name, "id": g.id, "description": getattr(g, 'description', 'N/A')} for g in groups]
            print(f"Security group listing not supported by {self.cloud_name} driver.")
            return []
        except Exception as e:
            print(f"Error getting security groups for {self.cloud_name}: {e}")
            return []
