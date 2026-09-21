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

    def __init__(self, config: Dict[str, Any], cloud_name: str, **kwargs):
        super().__init__(config, **kwargs)
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
        
        # Overwrite region if region_name is specified in cloudmesh config
        cloud_config = self.get_cloud_config(self.cloud_name)
        region_override = cloud_config.get("region_name")
        if region_override:
            logger.debug(f"Overriding region {region} with region_name from cloudmesh config: {region_override}")
            region = region_override

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
        """Runs an OpenStack CLI command with OS_CLOUD and OS_REGION_NAME environment variables set."""
        import subprocess
        import os
        from cloudmesh.ai.vm.logger import logger
        
        env = os.environ.copy()
        env["OS_CLOUD"] = self.cloud_name
        
        # Overwrite region if region_name is specified in cloudmesh config
        cloud_config = self.get_cloud_config(self.cloud_name)
        region_override = cloud_config.get("region_name")
        if region_override:
            env["OS_REGION_NAME"] = region_override
            logger.debug(f"Setting OS_REGION_NAME to {region_override} from cloudmesh config")
        
        logger.debug(f"Running CLI command: {' '.join(map(str, cmd))}")
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        
        if result.returncode != 0:
            logger.error(f"CLI command failed: {result.stderr}")
            raise RuntimeError(f"CLI command failed: {result.stderr}")
        
        return result.stdout

    def start(self, name: Optional[str] = None, flavor: Optional[str] = None, image: Optional[str] = None) -> str:
        """Starts a VM in OpenStack."""
        cloud_config = self.get_cloud_config(self.cloud_name)
        image_name = image or cloud_config.get("image")
        flavor_name = flavor or cloud_config.get("flavor")
        security_group = cloud_config.get("security_group", "default")
        
        if not image_name or not flavor_name:
            raise ValueError(f"Image or flavor missing in config for {self.cloud_name}")

        # Try libcloud first
        try:
            images = self.driver.list_images()
            image = next((img for img in images if img.name == image_name), None)
            
            sizes = self.driver.list_sizes()
            size = next((s for s in sizes if s.id == flavor_name or s.name == flavor_name), None)
            
            if image and size:
                node = self.driver.create_node(
                    name=name, 
                    image=image, 
                    size=size, 
                    ex_properties={'security_groups': [security_group]}
                )
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
        cmd = ["openstack", "server", "create", "--flavor", str(flavor_id), "--image", str(image_id), "--format", "value", "-c", "name"]
        
        if security_group:
            cmd.extend(["--security-group", str(security_group)])
        
        # The server name is a positional argument at the end of the command
        cmd.append(str(name))
        
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

    def shelve(self, name: Optional[str] = None) -> bool:
        """Shelves an OpenStack VM (preserves disk, releases compute resources)."""
        if not name: return False
        try:
            self._run_cli_command(["openstack", "server", "shelve", name])
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error shelving VM {name}: {e}")
            return False

    def unshelve(self, name: Optional[str] = None) -> bool:
        """Unshelves an OpenStack VM."""
        if not name: return False
        try:
            self._run_cli_command(["openstack", "server", "unshelve", name])
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error unshelving VM {name}: {e}")
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
        """Lists all OpenStack VMs with their reachable IP addresses."""
        try:
            nodes = self.driver.list_nodes()
            if nodes:
                results = []
                for n in nodes:
                    # Prioritize public IP if available in libcloud node object
                    ip = n.public_ips[0] if getattr(n, 'public_ips', None) else self._get_floating_ip(n.name)
                    results.append({"Name": n.name, "ID": n.id, "State": n.state, "IP": ip or "No IP"})
                return results
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.warning(f"Libcloud list failed: {e}. Trying CLI fallback...")

        # CLI Fallback
        try:
            # openstack server list --format json
            output = self._run_cli_command(["openstack", "server", "list", "--format", "json"])
            import json
            servers = json.loads(output)
            
            results = []
            for s in servers:
                # Extract Floating IP from addresses dictionary
                # Addresses format: {"network_name": [{"addr": "1.2.3.4", "version": "ipv4"}]}
                ip = "No IP"
                addresses = s.get('addresses', {})
                for net_name, addrs in addresses.items():
                    # Floating IPs are usually in networks not containing 'private' or 'internal'
                    if 'private' not in net_name.lower() and 'internal' not in net_name.lower():
                        if addrs:
                            ip = addrs[0].get('addr')
                            break
                
                # Final fallback if no obvious public net was found
                if ip == "No IP" and addresses:
                    # Just take the first available IP if we can't distinguish
                    first_net = list(addresses.values())[0]
                    if first_net:
                        ip = first_net[0].get('addr')

                results.append({"Name": s['name'], "ID": s['id'], "State": s['status'], "IP": ip})
            return results
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
            
            floating_ip = self._get_floating_ip(name)
            
            return {
                "Name": getattr(node, 'name', name),
                "ID": getattr(node, 'id', 'N/A'),
                "State": getattr(node, 'state', 'Unknown'),
                "FloatingIP": floating_ip or "Not Assigned",
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
        Provides the SSH connection string for the OpenStack VM.
        """
        if not name:
            self.print("Error: VM name is required to login.")
            return False
        
        floating_ip = self._get_floating_ip(name)
        if not floating_ip:
            self.print(f"No floating IP found for VM {name}. Use 'cmc vm assign-floating-ip' first.")
            return False
        
        cloud_config = self.get_cloud_config(self.cloud_name)
        key_path = cloud_config.get("key_path", "~/.ssh/id_rsa")
        user = cloud_config.get("user", "ubuntu")
        
        self.print(f"Connect to your VM using:\nssh -i {key_path} {user}@{floating_ip}")
        return True


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
            self.print(f"Error suspending node {name}: {e}")
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
            self.print(f"Error restarting node {name}: {e}")
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
            # Use the helper method to benefit from region override and consistent env setup
            result_stdout = self._run_cli_command(["openstack", "flavor", "list"])
            
            # Parse the table output
            lines = result_stdout.strip().split('\n')
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
        Lists available keys in OpenStack using the CLI.
        """
        try:
            result = self._run_cli_command(["openstack", "key", "list", "--format", "value", "-c", "name", "-c", "fingerprint"])
            lines = result.strip().split("\n")
            keys = []
            for line in lines:
                if not line:
                    continue
                parts = line.split(maxsplit=1)
                name = parts[0]
                fingerprint = parts[1] if len(parts) > 1 else "N/A"
                keys.append({"name": name, "fingerprint": fingerprint})
            return keys
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error listing OpenStack keys: {e}")
            return []

    def get_security_groups(self) -> List[Dict[str, Any]]:
        """
        Lists available security groups in OpenStack using the CLI.
        """
        try:
            result = self._run_cli_command(["openstack", "security", "group", "list", "--format", "value", "-c", "name", "-c", "description"])
            groups = []
            for line in result.strip().split("\n"):
                if not line: continue
                parts = line.split(maxsplit=1)
                name = parts[0]
                description = parts[1] if len(parts) > 1 else ""
                groups.append({"name": name, "description": description})
            return groups
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error listing security groups: {e}")
            return []

    def get_security_group_info(self, name: str) -> Dict[str, Any]:
        """
        Gets detailed information for a specific security group using the CLI.
        """
        try:
            # Use --format value to get key=value pairs
            result = self._run_cli_command(["openstack", "security", "group", "show", name, "--format", "value"])
            # OpenStack 'show' with --format value returns lines of values. 
            # To get keys as well, we can use --format json or just parse the output.
            # Since _run_cli_command is simple, let's try to use json if possible, 
            # but usually we can just use 'openstack security group show <name>' and parse.
            
            # Actually, 'openstack security group show <name> -f json' is the most reliable.
            import json
            result_json = self._run_cli_command(["openstack", "security", "group", "show", name, "-f", "json"])
            return json.loads(result_json)
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error getting security group info for {name}: {e}")
            raise RuntimeError(f"Could not get security group info: {e}")

    def add_security_group_rule(self, group_name: str, port: int, protocol: str = "tcp", cidr: str = "0.0.0.0/0") -> bool:
        """
        Adds a security group rule to allow traffic on a specific port using OpenStack CLI.
        """
        try:
            cmd = [
                "openstack", "security", "group", "rule", "create",
                "--protocol", protocol,
                "--dst-port", str(port),
                "--remote-ip", cidr,
                group_name
            ]
            self._run_cli_command(cmd)
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error adding security group rule to {group_name}: {e}")
            return False

    @property
    def version(self) -> List[str]:
        """
        Returns a list of version strings for the openstack CLI tool, libcloud, and CHI (for Chameleon).
        """
        versions = []
        try:
            import subprocess
            result = subprocess.run(["openstack", "--version"], capture_output=True, text=True, check=True)
            versions.append(f"CLI: {result.stdout.strip()}")
        except Exception:
            versions.append("CLI: Unknown")

        try:
            import libcloud
            versions.append(f"libcloud: {libcloud.__version__}")
        except Exception:
            versions.append("libcloud: Unknown")

        # Specifically for Chameleon, add the CHI library version
        if self.cloud_name == "chameleon":
            try:
                import chi
                versions.append(f"CHI: {chi.__version__}")
            except Exception:
                versions.append("CHI: Unknown")

        return versions


    def check_requirements(self) -> bool:
        """
        Checks if the requirements for this provider are met on the current system.
        """
        import shutil
        return shutil.which("openstack") is not None

    def upload_key(self, key_path: str, key_name: str) -> bool:
        """
        Uploads a public key to OpenStack.
        """
        try:
            import subprocess
            import os
            key_path = os.path.expanduser(key_path)
            if not os.path.exists(key_path):
                return False
            
            env = self._get_env()
            cmd = ["openstack", "key", "create", "--public-key", key_path, key_name]
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            return result.returncode == 0
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error uploading key {key_name}: {e}")
            return False

    def delete_key(self, key_name: str) -> bool:
        """
        Deletes a public key from OpenStack.
        """
        try:
            import subprocess
            env = self._get_env()
            cmd = ["openstack", "key", "delete", key_name]
            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            return result.returncode == 0
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error deleting key {key_name}: {e}")
            return False

    def _get_floating_ip(self, name: str) -> Optional[str]:
        """
        Internal helper to retrieve the floating IP address of a VM.
        """
        try:
            result = self._run_cli_command(["openstack", "server", "show", name, "--format", "value", "-c", "addresses"])
            # Output is like: 'network: a=10.0.0.1,net-id=...; floating: a=1.2.3.4,net-id=...'
            parts = result.split(';')
            for part in parts:
                if 'floating' in part:
                    # Extract a=1.2.3.4
                    addr_part = part.split(',')
                    for attr in addr_part:
                        if attr.startswith('a='):
                            return attr.split('=')[1]
            return None
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.debug(f"Could not find floating IP for {name}: {e}")
            return None

    def assign_floating_ip(self, name: str) -> Optional[str]:
        """
        Assigns an available floating IP to the VM.
        """
        try:
            # 1. Find a free floating IP
            result = self._run_cli_command(["openstack", "floating", "ip", "list", "--status", "FREE", "--format", "value", "-c", "ID"])
            free_ips = result.strip().split("\n")
            if not free_ips or not free_ips[0]:
                from cloudmesh.ai.vm.logger import logger
                logger.warning("No free floating IPs available in the pool.")
                return None
            
            floating_ip_id = free_ips[0]
            
            # 2. Associate it with the server
            self._run_cli_command(["openstack", "server", "add", "floating", "ip", name, floating_ip_id])
            
            return self._get_floating_ip(name)
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error assigning floating IP to {name}: {e}")
            return None

    def release_floating_ip(self, name: str) -> bool:
        """
        Releases the floating IP associated with the VM.
        """
        try:
            # 1. Find the floating IP
            result = self._run_cli_command(["openstack", "server", "show", name, "--format", "value", "-c", "addresses"])
            floating_ip_id = None
            parts = result.split(';')
            for part in parts:
                if 'floating' in part:
                    addr_part = part.split(',')
                    for attr in addr_part:
                        if 'net-id=' in attr:
                            floating_ip_id = attr.split('=')[1]
            
            if not floating_ip_id:
                return False
            
            # 2. Remove from server
            self._run_cli_command(["openstack", "server", "remove", "floating", "ip", name, floating_ip_id])
            
            # 3. Delete the IP
            self._run_cli_command(["openstack", "floating", "ip", "delete", floating_ip_id])
            
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error releasing floating IP for {name}: {e}")
            return False

            result = subprocess.run(cmd, capture_output=True, text=True, env=env)
            return result.returncode == 0
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error deleting key {key_name}: {e}")
            return False


    def run_command(self, name: str, cmd: str) -> str:
        """
        Executes a command on the VM via SSH.
        """
        try:
            floating_ip = self._get_floating_ip(name)
            if not floating_ip:
                return f"Error: No floating IP found for VM {name}. Please assign one first."
            
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
            return f"Unexpected error executing command: {e}"
        
    def validate_config(self) -> Dict[str, List[str]]:
        """
        Validates OpenStack specific configuration.
        """
        errors_map = {}
        config = self.get_cloud_config(self.cloud_name)
        
        config_name = "Cloudmesh config (~/.config/cloudmesh/clouds.yaml)"
        errors = []
        
        if not config.get("image"):
            errors.append("Missing required field: 'image'")
        if not (config.get("flavor") or config.get("size")):
            errors.append("Missing required field: 'flavor' or 'size'")
        if not config.get("key_path"):
            errors.append("Missing required field: 'key_path' for SSH access")
        
        if errors:
            errors_map[config_name] = errors
            
        return errors_map

