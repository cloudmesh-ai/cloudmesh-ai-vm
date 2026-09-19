from typing import List, Dict, Any, Optional
from cloudmesh.ai.vm.CloudBaseManager import CloudBaseManager
from cloudmesh.ai.vm.exceptions import ProviderError, ResourceNotFoundError, AuthenticationError
from cloudmesh.ai.vm.logger import logger

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
        try:
            self.driver = self._get_driver()
        except Exception as e:
            # If we are just checking requirements, don't fail hard on driver init
            # if it's an authentication/configuration error.
            logger.debug(f"Driver initialization skipped or failed for {cloud_name}: {e}")
            self.driver = None

    def check_requirements(self) -> bool:
        """
        Checks if the requirements for this provider are met.
        For Libcloud providers, this means the driver must be successfully initialized
        and not be a dummy class.
        """
        if self.driver is None:
            return False
        
        # Check if the driver is a dummy by checking for a known libcloud method.
        # All libcloud compute drivers should have list_nodes.
        if not hasattr(self.driver, 'list_nodes'):
            return False
            
        return True

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
        cloud_config = self.get_cloud_config(self.cloud_name)
        image_name = cloud_config.get("image")
        size_name = cloud_config.get("size") or cloud_config.get("flavor")
        
        if not image_name or not size_name:
            raise ProviderError(f"Image or Size/Flavour missing in config for {self.cloud_name}")

        try:
            images = self.driver.list_images()
            image = next((img for img in images if img.name == image_name), None)
            
            sizes = self.driver.list_sizes()
            size = next((s for s in sizes if s.id == size_name or s.name == size_name), None)

            if not image or not size:
                raise ResourceNotFoundError(f"Could not find image {image_name} or size {size_name} in {self.cloud_name}")

            try:
                node = self.driver.create_node(name=name, image=image, size=size)
            except TypeError:
                node = self.driver.create_node(name=name)

            logger.info(f"Successfully started VM {node.name} in {self.cloud_name}")
            return node.name
        except (ProviderError, ResourceNotFoundError):
            raise
        except Exception as e:
            logger.error(f"Unexpected error starting VM in {self.cloud_name}: {e}")
            raise ProviderError(f"Failed to start VM in {self.cloud_name}: {e}")

    def stop(self, name: Optional[str] = None) -> bool:
        if not name: return False
        try:
            node = self.driver.get_node(name)
            self.driver.stop_node(node)
            logger.info(f"Stopped VM {name} in {self.cloud_name}")
            return True
        except Exception as e:
            logger.error(f"Error stopping node {name} in {self.cloud_name}: {e}")
            return False

    def delete(self, name: Optional[str] = None) -> bool:
        if not name: return False
        try:
            node = self.driver.get_node(name)
            self.driver.destroy_node(node)
            logger.info(f"Deleted VM {name} in {self.cloud_name}")
            return True
        except Exception as e:
            logger.error(f"Error deleting node {name} in {self.cloud_name}: {e}")
            return False

    def list(self) -> List[Dict[str, Any]]:
        try:
            nodes = self.driver.list_nodes()
            return [{"Name": n.name, "ID": n.id, "State": n.state} for n in nodes]
        except Exception as e:
            logger.error(f"Error listing nodes in {self.cloud_name}: {e}")
            return []

    def login(self, name: Optional[str] = None) -> bool:
        if not name: return False
        logger.info(f"Login for {self.cloud_name} requires SSH: ssh {name}")
        return False

    def suspend(self, name: Optional[str] = None) -> bool:
        if not name: return False
        try:
            node = self.driver.get_node(name)
            if hasattr(self.driver, 'suspend_node'):
                self.driver.suspend_node(node)
                logger.info(f"Suspended VM {name} in {self.cloud_name}")
                return True
            logger.warning(f"Suspend not supported by {self.cloud_name} driver.")
            return False
        except Exception as e:
            logger.error(f"Error suspending node {name} in {self.cloud_name}: {e}")
            return False

    def restart(self, name: Optional[str] = None) -> bool:
        if not name: return False
        try:
            node = self.driver.get_node(name)
            if hasattr(self.driver, 'reboot_node'):
                self.driver.reboot_node(node)
                logger.info(f"Restarted VM {name} in {self.cloud_name}")
                return True
            logger.warning(f"Restart not supported by {self.cloud_name} driver.")
            return False
        except Exception as e:
            logger.error(f"Error restarting node {name} in {self.cloud_name}: {e}")
            return False


    def info(self, name: str) -> Dict[str, Any]:
        """
        Gets detailed information about a VM.
        """
        try:
            node = self.driver.get_node(name)
            if not node:
                return {"error": f"VM {name} not found"}
            
            # Extract common attributes from libcloud node object
            return {
                "Name": getattr(node, 'name', name),
                "ID": getattr(node, 'id', 'N/A'),
                "State": getattr(node, 'state', 'Unknown'),
                "PublicIPs": getattr(node, 'public_ips', []),
                "PrivateIPs": getattr(node, 'private_ips', []),
                "RAM": getattr(node, 'ram', 'N/A'),
                "CPUs": getattr(node, 'cpus', 'N/A'),
            }
        except Exception as e:
            logger.error(f"Error getting info for VM {name} in {self.cloud_name}: {e}")
            return {"error": str(e)}

    def get_flavors(self) -> List[Dict[str, Any]]:
        try:
            sizes = self.driver.list_sizes()
            return [{"id": s.id, "name": s.name, "ram": getattr(s, 'ram', 'N/A'), "vcpus": getattr(s, 'vcpus', 'N/A')} for s in sizes]
        except Exception as e:
            logger.error(f"Error getting flavors for {self.cloud_name}: {e}")
            return []

    def get_keys(self) -> List[Dict[str, Any]]:
        try:
            if hasattr(self.driver, 'list_keys'):
                keys = self.driver.list_keys()
                return [{"name": k.name, "fingerprint": getattr(k, 'fingerprint', 'N/A')} for k in keys]
            logger.warning(f"Key listing not supported by {self.cloud_name} driver.")
            return []
        except Exception as e:
            logger.error(f"Error getting keys for {self.cloud_name}: {e}")
            return []

    def get_security_groups(self) -> List[Dict[str, Any]]:
        try:
            if hasattr(self.driver, 'list_securitygroups'):
                groups = self.driver.list_securitygroups()
                return [{"name": g.name, "id": g.id, "description": getattr(g, 'description', 'N/A')} for g in groups]
            logger.warning(f"Security group listing not supported by {self.cloud_name} driver.")
            return []
        except Exception as e:
            logger.error(f"Error getting security groups for {self.cloud_name}: {e}")
            return []

    def run_command(self, name: str, cmd: str) -> str:
        """
        Executes a command on the VM.
        Note: This is a stub for libcloud-based providers as libcloud does not provide a unified run_command API.
        """
        return f"run_command is not yet implemented for this cloud provider ({self.cloud_name})"

