import yaml
from typing import List, Dict, Any, Optional
from cloudmesh.ai.vm.CloudBaseManager import CloudBaseManager
from unittest.mock import MagicMock

try:
    from libcloud.compute.types import Provider as LibcloudProvider
    from libcloud.compute.providers.openstack import OpenStackDriver
except ImportError:
    # Mocking libcloud for environments where it is not installed
    class LibcloudProvider: pass
    class OpenStackDriver:
        def __init__(self, *args, **kwargs):
            pass
        def list_images(self): return []
        def list_sizes(self): return []
        def list_nodes(self): return []
        def get_node(self, name): return MagicMock()
        def create_node(self, **kwargs): return MagicMock()
        def stop_node(self, node): pass
        def destroy_node(self, node): pass
        def suspend_node(self, node): pass
        def reboot_node(self, node): pass

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
        Initializes and returns the libcloud OpenStack driver using ~/.config/openstack/clouds.yaml.
        """
        import os
        from cloudmesh.ai.vm.logger import logger
        
        logger.debug(f"Initializing OpenStack driver for cloud: {self.cloud_name}")
        
        # Path to the standard OpenStack clouds.yaml
        clouds_yaml_path = os.path.expanduser("~/.config/openstack/clouds.yaml")
        
        if not os.path.exists(clouds_yaml_path):
            logger.debug(f"Standard clouds.yaml not found at {clouds_yaml_path}")
            cloud_config = self.get_cloud_config(self.cloud_name)
            auth_path = cloud_config.get("auth")
            if not auth_path:
                raise RuntimeError(f"OpenStack configuration not found at {clouds_yaml_path} and no 'auth' path provided in cloudmesh config for {self.cloud_name}")
            clouds_yaml_path = auth_path
            logger.debug(f"Using fallback auth path: {clouds_yaml_path}")

        try:
            with open(clouds_yaml_path, 'r') as f:
                full_config = yaml.safe_load(f)
            logger.debug(f"Successfully loaded config from {clouds_yaml_path}")
        except Exception as e:
            raise RuntimeError(f"Failed to load OpenStack clouds.yaml from {clouds_yaml_path}: {e}")

        clouds = full_config.get("clouds", full_config)
        cloud_data = clouds.get(self.cloud_name)

        if not cloud_data:
            raise RuntimeError(f"Cloud '{self.cloud_name}' not found in {clouds_yaml_path}")

        auth = cloud_data.get("auth", {})
        
        app_id = auth.get('application_credential_id')
        app_secret = auth.get('application_credential_secret')
        
        if app_id and app_secret:
            logger.debug("Using Application Credentials for authentication")
            username = app_id
            password = app_secret
        else:
            logger.debug("Using traditional username/password for authentication")
            username = auth.get('username')
            password = auth.get('password')

        logger.debug(f"Connecting to auth_url: {auth.get('auth_url')} with tenant_id: {auth.get('tenant_id') or auth.get('project_id')}")
        
        region = cloud_data.get("region")
        if region:
            logger.debug(f"Using region: {region}")
        else:
            logger.debug("No region specified, using default")
        
        return OpenStackDriver(
            username=username,
            password=password,
            auth_url=auth.get('auth_url'),
            tenant_id=auth.get('tenant_id') or auth.get('project_id'),
            region=region,
            version='3'
        )
    def _run_cli_command(self, cmd: List[str]) -> str:
        """Runs an OpenStack CLI command with OS_CLOUD environment variable set."""
        import subprocess
        import os
        from cloudmesh.ai.vm.logger import logger
        
        env = os.environ.copy()
        env["OS_CLOUD"] = self.cloud_name
        
        logger.debug(f"Running CLI command: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            logger.error(f"CLI command failed: {result.stderr}")
            raise RuntimeError(f"CLI command failed: {result.stderr}")
        
        return result.stdout

    def start(self, name: Optional[str] = None) -> str:
        """Starts a VM in OpenStack."""
        cloud_config = self.get_cloud_config(self.cloud_name)
        image_name = cloud_config.get("image")
        flavor_name = cloud_config.get("flavor")
        
        if not image_name or not flavor_name:
            raise ValueError(f"Image or flavor missing in config for {self.cloud_name}")

        # Try libcloud first
        try:
            images = self.driver.list_images()
            image = next((img for img in images if img.name == image_name), None)
            
            sizes = self.driver.list_sizes()
            size = next((s for s in sizes if s.id == flavor_name or s.name == flavor_name), None)
            
            if image and size:
                node = self.driver.create_node(name=name, image=image, size=size)
                return node.name
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.warning(f"Libcloud start failed: {e}. Trying CLI fallback...")

        # CLI Fallback
        # Resolve IDs
        resolved_images = self.get_images()
        resolved_flavor = next((f for f in self.get_flavors() if f['name'] == flavor_name or f['id'] == flavor_name), None)
        resolved_image = next((i for i in resolved_images if i['name'] == image_name), None)

        if not resolved_image or not resolved_flavor:
            raise RuntimeError(f"Could not find image {image_name} or flavor {flavor_name} in {self.cloud_name}")

        image_id = resolved_image['id']
        flavor_id = resolved_flavor['id']

        # Use CLI to create node
        cmd = ["openstack", "server", "create", "--flavor", flavor_id, "--image", image_id, "--format", "value", "-c", "name"]
        if name:
            cmd.extend(["--name", name])
        
        return self._run_cli_command(cmd).strip()

    def stop(self, name: Optional[str] = None) -> bool:
        """Stops an OpenStack VM."""
        if not name: return False
        try:
            node = self.driver.get_node(name)
            self.driver.stop_node(node)
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.warning(f"Libcloud stop failed: {e}. Trying CLI fallback...")
            try:
                self._run_cli_command(["openstack", "server", "stop", name])
                return True
            except Exception as cli_e:
                logger.error(f"CLI stop failed: {cli_e}")
                return False

    def delete(self, name: Optional[str] = None) -> bool:
        """Deletes an OpenStack VM."""
        if not name: return False
        try:
            node = self.driver.get_node(name)
            self.driver.destroy_node(node)
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.warning(f"Libcloud delete failed: {e}. Trying CLI fallback...")
            try:
                self._run_cli_command(["openstack", "server", "delete", name])
                return True
            except Exception as cli_e:
                logger.error(f"CLI delete failed: {cli_e}")
                return False

    def list(self) -> List[Dict[str, Any]]:
        """Lists all OpenStack VMs."""
        try:
            nodes = self.driver.list_nodes()
            if nodes:
                return [{"Name": n.name, "ID": n.id, "State": n.state} for n in nodes]
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.warning(f"Libcloud list failed: {e}. Trying CLI fallback...")

        # CLI Fallback
        try:
            # openstack server list --format json
            output = self._run_cli_command(["openstack", "server", "list", "--format", "json"])
            import json
            servers = json.loads(output)
            return [{"Name": s['name'], "ID": s['id'], "State": s['status']} for s in servers]
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CLI list failed: {e}")
            return []

    def info(self, name: str) -> Dict[str, Any]:
        """
        Gets detailed information about an OpenStack VM.
        """
        try:
            node = self.driver.get_node(name)
            if not node:
                return {"error": f"VM {name} not found"}
            
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
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error getting info for VM {name} in {self.cloud_name}: {e}")
            return {"error": str(e)}

 
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

    def get_images(self) -> List[Dict[str, Any]]:
        """
        Lists available images in OpenStack.
        Falls back to 'openstack image list' CLI if libcloud returns empty results.
        """
        try:
            from cloudmesh.ai.vm.logger import logger
            logger.debug("Fetching images from OpenStack driver...")
            images = self.driver.list_images()
            if images:
                logger.debug(f"Driver returned {len(images)} images.")
                return [{"id": img.id, "name": img.name} for img in images]
            
            logger.debug("Driver returned no images. Falling back to 'openstack image list' CLI...")
            import subprocess
            import os
            
            env = os.environ.copy()
            env["OS_CLOUD"] = self.cloud_name
            
            cmd = ["openstack", "image", "list"]
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            
            if result.returncode != 0:
                logger.error(f"CLI fallback failed: {result.stderr}")
                return []
            
            lines = result.stdout.strip().split('\n')
            if len(lines) < 3:
                return []
                
            images_list = []
            for line in lines[2:]:
                if line.startswith('+') or not line.strip():
                    continue
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 2:
                    images_list.append({
                        "id": parts[0],
                        "name": parts[1]
                    })
            
            logger.debug(f"CLI fallback returned {len(images_list)} images.")
            return images_list

        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error getting images: {e}")
            return []

    def get_flavors(self) -> List[Dict[str, Any]]:
        """
        Lists available flavors in OpenStack.
        Falls back to 'openstack flavor list' CLI if libcloud returns empty results.
        """
        try:
            from cloudmesh.ai.vm.logger import logger
            logger.debug("Fetching flavors from OpenStack driver...")
            sizes = self.driver.list_sizes()
            if sizes:
                logger.debug(f"Driver returned {len(sizes)} flavors.")
                return [{"id": s.id, "name": s.name, "ram": s.ram, "vcpus": s.vcpus} for s in sizes]
            
            logger.debug("Driver returned no flavors. Falling back to 'openstack flavor list' CLI...")
            import subprocess
            import os
            
            # Use the cloud name to set OS_CLOUD environment variable for the CLI
            env = os.environ.copy()
            env["OS_CLOUD"] = self.cloud_name
            
            cmd = ["openstack", "flavor", "list"]
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            
            if result.returncode != 0:
                logger.error(f"CLI fallback failed: {result.stderr}")
                return []
            
            # Parse the table output
            lines = result.stdout.strip().split('\n')
            if len(lines) < 3:
                return []
                
            flavors = []
            for line in lines[2:]: # Skip header and separator lines
                if line.startswith('+') or not line.strip():
                    continue
                # Split by '|', remove empty strings from edges
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 5:
                    flavors.append({
                        "id": parts[0],
                        "name": parts[1],
                        "ram": parts[2],
                        "vcpus": parts[5]
                    })
            
            logger.debug(f"CLI fallback returned {len(flavors)} flavors.")
            return flavors

        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error getting flavors: {e}")
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


    def run_command(self, name: str, cmd: str) -> str:
        """
        Executes a command on the VM.
        Note: This is a stub for OpenStack-based providers.
        """
        return f"run_command is not yet implemented for this OpenStack provider ({self.cloud_name})"

