import yaml
from typing import List, Dict, Any, Optional
from cloudmesh.ai.vm.CloudBaseManager import CloudBaseManager

try:
    from libcloud.compute.types import Provider as LibcloudProvider
    from libcloud.compute.providers.openstack import OpenStackDriver
except ImportError:
    # Mocking libcloud for environments where it is not installed
    class LibcloudProvider: pass
    class OpenStackDriver: pass

class OpenstackManager(CloudBaseManager):
    """
    Base Manager for OpenStack-based clouds.
    Implements common OpenStack VM operations using libcloud.
    """

    def __init__(self, config: Dict[str, Any], cloud_name: str):
        super().__init__(config)
        self.cloud_name = cloud_name
        self.driver = self._get_driver()

    def _get_driver(self):
        """
        Initializes and returns the libcloud OpenStack driver.
        """
        cloud_config = self.config.clouds.get(self.cloud_name, {})
        auth_path = getattr(cloud_config, "auth", None)
        
        if not auth_path:
            raise ValueError(f"Auth path not found in config for cloud: {self.cloud_name}")
        
        try:
            with open(auth_path, 'r') as f:
                auth_data = yaml.safe_load(f)
        except Exception as e:
            raise RuntimeError(f"Failed to load auth file {auth_path}: {e}")

        return OpenStackDriver(
            username=auth_data.get('username'),
            password=auth_data.get('password'),
            auth_url=auth_data.get('auth_url'),
            tenant_id=auth_data.get('tenant_id'),
            version='2'
        )

    def start(self, name: Optional[str] = None) -> str:
        """
        Starts a VM in OpenStack.
        """
        cloud_config = self.config.clouds.get(self.cloud_name, {})
        image_name = getattr(cloud_config, "image", None)
        flavor_name = getattr(cloud_config, "flavour", None)
        
        if not image_name or not flavor_name:
            raise ValueError(f"Image or Flavour missing in config for {self.cloud_name}")

        images = self.driver.list_images()
        image = next((img for img in images if img.name == image_name), None)
        
        sizes = self.driver.list_sizes()
        size = next((s for s in sizes if s.id == flavor_name or s.name == flavor_name), None)

        if not image or not size:
            raise RuntimeError(f"Could not find image {image_name} or flavor {flavor_name} in {self.cloud_name}")

        node = self.driver.create_node(name=name, image=image, size=size)
        return node.name

    def stop(self, name: Optional[str] = None) -> bool:
        """
        Stops an OpenStack VM.
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
        Deletes an OpenStack VM.
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
        Lists all OpenStack VMs.
        """
        try:
            nodes = self.driver.list_nodes()
            return [{"Name": n.name, "ID": n.id, "State": n.state} for n in nodes]
        except Exception as e:
            print(f"Error listing nodes: {e}")
            return []

    def login(self, name: Optional[str] = None) -> bool:
        """
        Logging into OpenStack VMs usually happens via SSH.
        """
        if not name: return False
        print(f"Please use SSH to log into the OpenStack VM: {name}")
        return False


    def suspend(self, name: Optional[str] = None) -> bool:
        """
        Suspends an OpenStack VM.
        """
        if not name: return False
        try:
            node = self.driver.get_node(name)
            self.driver.suspend_node(node)
            return True
        except Exception as e:
            print(f"Error suspending node {name}: {e}")
            return False

    def restart(self, name: Optional[str] = None) -> bool:
        """
        Restarts an OpenStack VM.
        """
        if not name: return False
        try:
            node = self.driver.get_node(name)
            self.driver.reboot_node(node)
            return True
        except Exception as e:
            print(f"Error restarting node {name}: {e}")
            return False

    def get_flavors(self) -> List[Dict[str, Any]]:
        """
        Lists available flavors in OpenStack.
        """
        try:
            sizes = self.driver.list_sizes()
            return [{"id": s.id, "name": s.name, "ram": s.ram, "vcpus": s.vcpus} for s in sizes]
        except Exception as e:
            print(f"Error getting flavors: {e}")
            return []

    def get_keys(self) -> List[Dict[str, Any]]:
        """
        Lists available keys in OpenStack.
        """
        return [{"name": "generic-openstack-key", "status": "active"}]

    def get_security_groups(self) -> List[Dict[str, Any]]:
        """
        Lists available security groups in OpenStack.
        """
        try:
            return [{"name": "default", "description": "Default security group"}]
        except Exception as e:
            print(f"Error getting security groups: {e}")
            return []

