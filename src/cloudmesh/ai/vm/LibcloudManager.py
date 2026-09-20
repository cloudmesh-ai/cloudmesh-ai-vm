import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from .CloudBaseManager import CloudBaseManager
from .exceptions import VMProviderError, ProviderFeatureNotSupported

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

    def start(self, name: Optional[str] = None, flavor: Optional[str] = None, image: Optional[str] = None) -> str:
        """
        Starts a VM using libcloud.
        """
        # The actual implementation is in the specific provider subclasses
        raise ProviderFeatureNotSupported(self.cloud_name, "start")

    def stop(self, name: Optional[str] = None) -> bool:
        """
        Stops a VM using libcloud.
        """
        try:
            node = self.driver.get_node(name)
            if node:
                node.stop()
                return True
            return False
        except Exception as e:
            logger.error(f"Error stopping VM {name} in {self.cloud_name}: {e}")
            return False

    def delete(self, name: Optional[str] = None) -> bool:
        """
        Deletes a VM using libcloud.
        """
        try:
            node = self.driver.get_node(name)
            if node:
                node.destroy()
                return True
            return False
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

    def get_images(self) -> List[Dict[str, Any]]:
        try:
            images = self.driver.list_images()
            return [{"id": i.id, "name": i.name} for i in images]
        except Exception as e:
            logger.error(f"Error getting images for {self.cloud_name}: {e}")
            return []

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
            raise ProviderFeatureNotSupported(self.cloud_name, "get_keys")
        except Exception as e:
            if isinstance(e, ProviderFeatureNotSupported): raise e
            logger.error(f"Error getting keys for {self.cloud_name}: {e}")
            return []

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
            
            import subprocess
            import os
            key_path = os.path.expanduser(key_path)
            
            ssh_cmd = [
                "ssh", 
                "-i", key_path, 
                "-o", "StrictHostKeyChecking=no", 
                "-o", "UserKnownHostsFile=/dev/null",
                f"{user}@{floating_ip}", 
                cmd
            ]
            
            result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                return f"SSH Error (code {result.returncode}): {result.stderr}"
            return result.stdout.strip()
            
        except Exception as e:
            return f"Unexpected error executing command on {self.cloud_name}: {e}"

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
