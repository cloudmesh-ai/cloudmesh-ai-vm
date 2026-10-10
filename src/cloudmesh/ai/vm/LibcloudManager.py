import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from .CloudBaseManager import CloudBaseManager
from .exceptions import VMProviderError, ProviderFeatureNotSupported, ConfigError, VMResourceError

logger = logging.getLogger("cloudmesh.ai.vm")

class LibcloudManager(CloudBaseManager, ABC):
    """
    Base class for providers using the libcloud library.
    """

    def __init__(self, config: Any, cloud_name: str, **kwargs):
        super().__init__(config, **kwargs)
        self.cloud_name = cloud_name
        self.driver = self._get_driver()

    @abstractmethod
    def _get_driver(self) -> Any:
        """Returns the libcloud driver instance."""
        pass

    def _get_current_status(self, name: str) -> str:
        """Returns the current status of the VM using the libcloud driver."""
        try:
            node = self.driver.get_node(name)
            return getattr(node, 'state', '') if node else ''
        except Exception:
            return ''

    def exists(self, name: str) -> bool:
        """
        Checks if a VM exists using the libcloud driver.
        """
        try:
            node = self.driver.get_node(name)
            return node is not None
        except Exception:
            return False

    def start(self, name: Optional[str] = None, flavor: Optional[str] = None, image: Optional[str] = None, **kwargs) -> str:
        """
        Starts a VM using libcloud.
        """
        cloud_config = self.get_cloud_config(self.cloud_name)
        image_name = image or cloud_config.get("image")
        flavor_name = flavor or cloud_config.get("flavor") or cloud_config.get("size")

        if not image_name:
            raise ConfigError(f"Missing 'image' in config or arguments for {self.cloud_name}")
        if not flavor_name:
            raise ConfigError(f"Missing 'flavor' or 'size' in config or arguments for {self.cloud_name}")

        try:
            # Find image object
            all_images = self.driver.list_images()
            img = next((i for i in all_images if i.name == image_name), None)
            if not img:
                raise VMResourceError(f"Could not find image {image_name} in {self.cloud_name}")

            # Find flavor/size object
            all_flavors = self.driver.list_sizes()
            flv = next((f for f in all_flavors if f.name == flavor_name), None)
            if not flv:
                raise VMResourceError(f"Could not find flavor {flavor_name} in {self.cloud_name}")

            vm_name = name or f"vm-{self.cloud_name}"
            logger.info(f"Starting {self.cloud_name} VM {vm_name} with image {image_name} and flavor {flavor_name}...")

            node = self.driver.create_node(name=vm_name, image=img, size=flv)
            logger.info(f"Successfully started {self.cloud_name} VM {vm_name} (ID: {node.id})")

            return node.id
        except Exception as e:
            logger.error(f"Libcloud start failed for {self.cloud_name}: {e}")
            raise e

    @property
    def version(self) -> List[str]:
        """Returns the provider version."""
        try:
            import libcloud
            return [f"libcloud: {libcloud.__version__}"]
        except Exception:
            return ["libcloud: Unknown"]

    def restart(self, name: Optional[str] = None) -> bool:
        """
        Restarts a VM using libcloud.
        """
        if not name:
            return False
        try:
            node = self.driver.get_node(name)
            if not node:
                logger.error(f"VM {name} not found in {self.cloud_name}")
                return False
            if not hasattr(node, 'reboot'):
                raise ProviderFeatureNotSupported(self.cloud_name, "restart")
            node.reboot()
            return True
        except Exception as e:
            if isinstance(e, ProviderFeatureNotSupported):
                raise e
            logger.error(f"Error restarting VM {name} in {self.cloud_name}: {e}")
            return False

    def suspend(self, name: Optional[str] = None) -> bool:
        """
        Suspends a VM using libcloud.
        """
        if not name:
            return False
        try:
            node = self.driver.get_node(name)
            if not node:
                logger.error(f"VM {name} not found in {self.cloud_name}")
                return False
            if not hasattr(node, 'suspend'):
                raise ProviderFeatureNotSupported(self.cloud_name, "suspend")
            node.suspend()
            return True
        except Exception as e:
            if isinstance(e, ProviderFeatureNotSupported):
                raise e
            logger.error(f"Error suspending VM {name} in {self.cloud_name}: {e}")
            return False

    def reset(self, name: Optional[str] = None) -> bool:
        """
        Resets a VM using libcloud.
        """
        if not name:
            return False
        try:
            node = self.driver.get_node(name)
            if not node:
                logger.error(f"VM {name} not found in {self.cloud_name}")
                return False
            # Libcloud doesn't have a generic 'reset' for all providers.
            # Usually a hard reboot or a specific driver method.
            if hasattr(node, 'reset'):
                node.reset()
                return True

            # Fallback to reboot if reset is not explicitly supported
            node.reboot()
            return True
        except Exception as e:
            logger.error(f"Error resetting VM {name} in {self.cloud_name}: {e}")
            return False

    def stop(self, name: Optional[str] = None) -> bool:
        """
        Stops a VM using libcloud.
        """
        if not name:
            return False
        try:
            node = self.driver.get_node(name)
            if not node:
                logger.error(f"VM {name} not found in {self.cloud_name}")
                return False
            node.stop()
            return True
        except Exception as e:
            logger.error(f"Error stopping VM {name} in {self.cloud_name}: {e}")
            return False

    def delete(self, name: Optional[str] = None) -> bool:
        """
        Deletes a VM using libcloud.
        """
        if not name:
            return False
        try:
            node = self.driver.get_node(name)
            if not node:
                logger.error(f"VM {name} not found in {self.cloud_name}")
                return False
            node.destroy()
            return True
        except Exception as e:
            logger.error(f"Error deleting VM {name} in {self.cloud_name}: {e}")
            return False

    def list(self) -> List[Dict[str, Any]]:
        """
        Lists all VMs using libcloud.
        """
        try:
            nodes = self.driver.list_nodes()
            return [
                {"Name": n.name, "IP": n.public_ips[0] if n.public_ips else "N/A", "Status": n.state}
                for n in nodes
            ]
        except Exception as e:
            logger.error(f"Error listing VMs in {self.cloud_name}: {e}")
            return []

    def info(self, name: str) -> Dict[str, Any]:
        """
        Gets detailed information about a specific VM using libcloud.
        """
        if not self.exists(name):
            return {"error": f"VM {name} not found in {self.cloud_name}"}
        try:
            node = self.driver.get_node(name)
            if not node:
                return {"error": "VM not found"}
            return {
                "Name": node.name,
                "IP": node.public_ips[0] if node.public_ips else "N/A",
                "Status": node.state,
                "RAM": getattr(node, 'ram', 'N/A'),
                "CPUs": getattr(node, 'cpus', 'N/A'),
            }
        except Exception as e:
            logger.error(f"Error getting info for VM {name} in {self.cloud_name}: {e}")
            return {"error": str(e)}

    def get_images(self, **kwargs) -> List[Dict[str, Any]]:
        try:
            images = self.driver.list_images()
            return [{"id": i.id, "name": i.name} for i in images]
        except Exception as e:
            logger.error(f"Error getting images for {self.cloud_name}: {e}")
            return []

    def get_flavors(self, **kwargs) -> List[Dict[str, Any]]:
        try:
            sizes = self.driver.list_sizes()
            return [{"id": s.id, "name": s.name, "ram": getattr(s, 'ram', 'N/A'), "vcpus": getattr(s, 'vcpus', 'N/A')} for s in sizes]
        except Exception as e:
            logger.error(f"Error getting flavors for {self.cloud_name}: {e}")
            return []

    def list_regions(self) -> List[Dict[str, Any]]:
        """
        Lists available regions for the libcloud provider.
        """
        try:
            if hasattr(self.driver, 'list_regions'):
                regions = self.driver.list_regions()
                return [{"name": r.name, "id": getattr(r, 'id', r.name)} for r in regions]
            raise ProviderFeatureNotSupported(self.cloud_name, "list_regions")
        except Exception as e:
            if isinstance(e, ProviderFeatureNotSupported): raise e
            logger.error(f"Error listing regions for {self.cloud_name}: {e}")
            return []

    def get_keys(self) -> List[Dict[str, Any]]:
        try:
            if hasattr(self.driver, 'list_keys'):
                keys = self.driver.list_keys()
                return [{"name": k.name, "fingerprint": getattr(k, 'fingerprint', 'N/A')} for k in keys]
            raise ProviderFeatureNotSupported(self.cloud_name, "get_keys")
        except Exception as e:
            if isinstance(e, ProviderFeatureNotSupported): raise e
            logger.error(f"Error getting keys for {self.cloud_name}: {e}")
            return []

    def upload_key(self, key_path: str, key_name: str, vm_name: Optional[str] = None) -> bool:
        """
        Uploads a public key to the cloud provider using libcloud.
        """
        try:
            if hasattr(self.driver, 'upload_key'):
                self.driver.upload_key(key_path, key_name)
                return True
            raise ProviderFeatureNotSupported(self.cloud_name, "upload_key")
        except Exception as e:
            if isinstance(e, ProviderFeatureNotSupported): raise e
            logger.error(f"Error uploading key {key_name} in {self.cloud_name}: {e}")
            return False

    def delete_key(self, key_name: str, vm_name: Optional[str] = None) -> bool:
        """
        Deletes a public key from the cloud provider using libcloud.
        """
        try:
            if hasattr(self.driver, 'delete_key'):
                self.driver.delete_key(key_name)
                return True
            raise ProviderFeatureNotSupported(self.cloud_name, "delete_key")
        except Exception as e:
            if isinstance(e, ProviderFeatureNotSupported): raise e
            logger.error(f"Error deleting key {key_name} in {self.cloud_name}: {e}")
            return False

    def create_security_group(self, name: str, description: str = "") -> bool:
        """
        Creates a security group using the libcloud driver.
        """
        try:
            if hasattr(self.driver, 'create_security_group'):
                self.driver.create_security_group(name, description)
                return True
            raise ProviderFeatureNotSupported(self.cloud_name, "create_security_group")
        except Exception as e:
            if isinstance(e, ProviderFeatureNotSupported): raise e
            logger.error(f"Error creating security group {name} in {self.cloud_name}: {e}")
            return False

    def add_security_group_rule(self, sg_name: str, protocol: str, port: str, cidr: str, direction: str = "ingress") -> str:
        """
        Adds a firewall rule to a security group.
        """
        try:
            if hasattr(self.driver, 'add_security_group_rule'):
                # Libcloud's add_security_group_rule typically expects the SG object or name
                # Depending on the driver, we might need to find the SG first
                sg = self.driver.get_security_group(sg_name)
                rule = self.driver.add_security_group_rule(sg, protocol, port, cidr, direction)
                return rule.id if hasattr(rule, 'id') else "success"
            raise ProviderFeatureNotSupported(self.cloud_name, "add_security_group_rule")
        except Exception as e:
            if isinstance(e, ProviderFeatureNotSupported): raise e
            logger.error(f"Error adding rule to {sg_name} in {self.cloud_name}: {e}")
            return f"Error: {e}"

    def get_security_groups(self) -> List[Dict[str, Any]]:
        try:
            if hasattr(self.driver, 'list_securitygroups'):
                groups = self.driver.list_securitygroups()
                return [{"name": g.name, "id": g.id, "description": getattr(g, 'description', 'N/A')} for g in groups]
            raise ProviderFeatureNotSupported(self.cloud_name, "get_security_groups")
        except Exception as e:
            if isinstance(e, ProviderFeatureNotSupported): raise e
            logger.error(f"Error getting security groups for {self.cloud_name}: {e}")
            return []

    def run_command(self, name: str, cmd: str) -> str:
        try:
            node = self.driver.get_node(name)
            if not node:
                return f"Error: VM {name} not found in {self.cloud_name}."
            
            public_ips = getattr(node, 'public_ips', [])
            if not public_ips:
                return f"Error: No public IP found for VM {name}."
            
            floating_ip = public_ips[0]
            cloud_config = self.get_cloud_config(self.cloud_name)
            key_path = cloud_config.get("key_path", "~/.ssh/id_rsa")
            user = cloud_config.get("user", "ubuntu")

            return self._execute_ssh_command(floating_ip, user, key_path, cmd)

        except Exception as e:
            return f"Unexpected error executing command on {self.cloud_name}: {e}"

    def assign_floating_ip(self, name: str) -> Optional[str]:
        """
        Assigns a floating IP to the VM using libcloud.
        """
        try:
            node = self.driver.get_node(name)
            if not node:
                logger.error(f"VM {name} not found in {self.cloud_name}")
                return None

            if hasattr(node, 'assign_floating_ip'):
                return node.assign_floating_ip()

            if hasattr(self.driver, 'assign_floating_ip'):
                return self.driver.assign_floating_ip(node)

            raise ProviderFeatureNotSupported(self.cloud_name, "assign_floating_ip")
        except Exception as e:
            if isinstance(e, ProviderFeatureNotSupported): raise e
            logger.error(f"Error assigning floating IP to {name} in {self.cloud_name}: {e}")
            return None

    def release_floating_ip(self, name: str) -> bool:
        """
        Releases a floating IP from the VM using libcloud.
        """
        try:
            node = self.driver.get_node(name)
            if not node:
                logger.error(f"VM {name} not found in {self.cloud_name}")
                return False

            if hasattr(node, 'release_floating_ip'):
                node.release_floating_ip()
                return True

            if hasattr(self.driver, 'release_floating_ip'):
                self.driver.release_floating_ip(node)
                return True

            raise ProviderFeatureNotSupported(self.cloud_name, "release_floating_ip")
        except Exception as e:
            if isinstance(e, ProviderFeatureNotSupported): raise e
            logger.error(f"Error releasing floating IP from {name} in {self.cloud_name}: {e}")
            return False

    def validate_config(self) -> Dict[str, List[str]]:
        errors_map = {}
        cloud_config = self.get_cloud_config(self.cloud_name)
        
        config_name = "Cloudmesh config (~/.config/cloudmesh/clouds.yaml)"
        errors = []
        
        if not cloud_config.get("image"):
            errors.append("Missing required field: 'image'")
        if not (cloud_config.get("size") or cloud_config.get("flavor")):
            errors.append("Missing required field: 'size' or 'flavor'")
        
        if errors:
            errors_map[config_name] = errors
            
        return errors_map
