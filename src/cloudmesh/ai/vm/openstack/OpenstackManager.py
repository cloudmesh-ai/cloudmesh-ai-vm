from pathlib import Path
import yaml
from typing import List, Dict, Any, Optional
from cloudmesh.ai.vm.CloudBaseManager import CloudBaseManager
from cloudmesh.ai.vm.exceptions import ConfigError, VMResourceError, VMAuthError, VMNetworkError, VMProviderError
from cloudmesh.ai.command.vm._shared.providers_utils import sanitize_output

try:
    from libcloud.compute.types import Provider as LibcloudProvider
    from libcloud.compute.drivers.openstack import OpenStackNodeDriver as OpenStackDriver
except ImportError:
    raise ImportError("libcloud is required for OpenStackManager. Please install it using 'pip install apache-libcloud'.")

class OpenstackManager(CloudBaseManager):
    """
    Base Manager for OpenStack-based clouds.
    Implements common OpenStack VM operations using libcloud.
    """

    def __init__(self, config: Any, cloud_name: Optional[str] = None, **kwargs):
        super().__init__(config, **kwargs)
        self.cloud_name = cloud_name
        if not self.cloud_name:
            self.cloud_name = "openstack"
        self.driver = self._get_driver()

    def _get_driver(self):
        """
        Returns an authenticated Libcloud OpenStack driver using application credentials.
        Checks both the Cloudmesh config and the standard ~/.config/openstack/clouds.yaml.
        """
        from cloudmesh.ai.vm.logger import logger
        from libcloud.compute.providers import get_driver
        from libcloud.compute.types import Provider
        import os
        import yaml
        
        # 1. Get config from Cloudmesh State
        cloud_config = self.get_cloud_config(self.cloud_name) or {}
        
        # 2. Load from standard OpenStack clouds.yaml as a fallback/merge
        os_clouds_path = os.path.expanduser("~/.config/openstack/clouds.yaml")
        if os.path.exists(os_clouds_path):
            try:
                with open(os_clouds_path, "r") as f:
                    os_full_config = yaml.safe_load(f) or {}
                    # Standard clouds.yaml has a top-level 'clouds' key
                    os_clouds = os_full_config.get("clouds", {})
                    os_cloud_cfg = os_clouds.get(self.cloud_name, {})
                    
                    # Merge: OS config takes priority for auth credentials
                    os_auth = os_cloud_cfg.get("auth", {})
                    cm_auth = cloud_config.get("auth", {})
                    
                    # Merged auth: OS values override CM values
                    merged_auth = {**cm_auth, **os_auth}
                    
                    # Update cloud_config with merged auth and other OS settings
                    cloud_config = {**cloud_config, **os_cloud_cfg}
                    cloud_config["auth"] = merged_auth
                    
                    logger.debug(f"Merged configuration for '{self.cloud_name}' from {os_clouds_path}")
            except Exception as e:
                logger.warning(f"Could not parse {os_clouds_path}: {e}")

        auth = cloud_config.get("auth", {})
        
        # Extract credentials, checking both 'auth' sub-dict and top-level
        app_cred_id = auth.get("application_credential_id") or cloud_config.get("application_credential_id")
        app_cred_secret = auth.get("application_credential_secret") or cloud_config.get("application_credential_secret")
        auth_url = auth.get("auth_url") or cloud_config.get("auth_url")
        region_name = cloud_config.get("region_name", auth.get("region_name", "RegionOne"))

        if not all([app_cred_id, app_cred_secret, auth_url]):
            raise ConfigError(
                f"Missing required application credentials for cloud '{self.cloud_name}'. "
                f"Checked both Cloudmesh config and {os_clouds_path}. "
                f"Please ensure 'application_credential_id', 'application_credential_secret', "
                f"and 'auth_url' are configured."
            )

        logger.debug(f"Initializing OpenStack driver for cloud '{self.cloud_name}' using application credentials.")
        OpenStackDriver = get_driver(Provider.OPENSTACK)
        return OpenStackDriver(
            app_cred_id,
            app_cred_secret,
            ex_force_auth_url=auth_url,
            ex_force_auth_version="3.x_appcred",
            ex_force_service_region=region_name
        )

        logger.debug(f"Initializing OpenStack driver for cloud '{self.cloud_name}' using application credentials.")
        OpenStackDriver = get_driver(Provider.OPENSTACK)
        return OpenStackDriver(
            app_cred_id,
            app_cred_secret,
            ex_force_auth_url=auth_url,
            ex_force_auth_version="3.x_appcred",
            ex_force_service_region=region_name
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
            sanitized_stderr = sanitize_output(result.stderr)
            logger.error(f"CLI command failed: {sanitized_stderr}")
            raise VMProviderError(f"CLI command failed: {sanitized_stderr}")

        return result.stdout

    def start(self, name: Optional[str] = None, flavor: Optional[str] = None, image: Optional[str] = None) -> str:
        """Starts a VM in OpenStack using libcloud."""
        cloud_config = self.get_cloud_config(self.cloud_name)
        image_name = image or cloud_config.get("image")
        flavor_name = flavor or cloud_config.get("flavor")
        security_group = cloud_config.get("security_group", "default")
        key_name = cloud_config.get("key_name")
        if not key_name and cloud_config.get("key_path"):
            key_name = Path(cloud_config["key_path"]).name.replace(".pub", "")
        
        if not image_name:
            raise ConfigError(f"Missing 'image' in config for {self.cloud_name}")
        if not flavor_name:
            raise ConfigError(f"Missing 'flavor' in config for {self.cloud_name}")

        try:
            # Find image and flavor objects
            all_images = self.driver.list_images()
            img = next((i for i in all_images if i.name == image_name), None)
            if not img:
                raise VMResourceError(f"Could not find image {image_name} in {self.cloud_name}")

            all_flavors = self.driver.list_sizes()
            flv = next((f for f in all_flavors if f.name == flavor_name), None)
            if not flv:
                raise VMResourceError(f"Could not find flavor {flavor_name} in {self.cloud_name}")

            security_groups = self.driver.ex_list_security_groups()
            sg = next(
                (group for group in security_groups if group.name == security_group),
                None,
            )
            if sg is None:
                raise VMResourceError(
                    f"Could not find security group {security_group} in {self.cloud_name}"
                )

            vm_name = name or f"vm-{self.cloud_name}"
            node = self.driver.create_node(
                name=vm_name,
                image=img,
                size=flv,
                ex_keyname=key_name,
                ex_security_groups=[sg],
            )
            return node.id
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Libcloud start failed for {self.cloud_name}: {e}")
            raise VMProviderError(f"Libcloud start failed for {self.cloud_name}: {e}") from e

    def _find_node(self, identifier: str):
        """Helper to find a node by name or ID since some driver versions lack get_node."""
        try:
            if hasattr(self.driver, 'get_node'):
                node = self.driver.get_node(identifier)
                if node:
                    return node
        except Exception:
            pass

        nodes = self.driver.list_nodes()
        return next((n for n in nodes if n.name == identifier or n.id == identifier), None)

    def exists(self, name: str) -> bool:
        """
        Checks if a VM exists in OpenStack.
        """
        return self._find_node(name) is not None

    def stop(self, name: Optional[str] = None) -> bool:
        """Stops an OpenStack VM."""
        if not name or not self.exists(name):
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"VM {name} not found in {self.cloud_name}")
            return False
        try:
            node = self._find_node(name)
            # Handle ConflictException 409: cannot stop while BUILDING
            import time
            from cloudmesh.ai.vm.logger import logger

            max_retries = 5
            for i in range(max_retries):
                state = getattr(node, 'state', '').lower()
                if state != 'building':
                    break
                logger.warning(f"VM {name} is still building (attempt {i+1}/{max_retries}). Waiting 5s...")
                time.sleep(5)
                node = self._find_node(name)

            self.driver.stop_node(node)
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Libcloud stop failed for {name}: {e}")
            raise VMProviderError(f"Libcloud stop failed for {name}: {e}") from e

    def shelve(self, name: Optional[str] = None) -> bool:
        """Shelves an OpenStack VM (preserves disk, releases compute resources)."""
        if not name: return False
        try:
            node = self._find_node(name)
            if node:
                self.driver.shelve_node(node)
                return True
            return False
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Libcloud shelve failed for {name}: {e}")
            return False

    def unshelve(self, name: Optional[str] = None) -> bool:
        """Unshelves an OpenStack VM."""
        if not name: return False
        try:
            node = self._find_node(name)
            if node:
                self.driver.unshelve_node(node)
                return True
            return False
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Libcloud unshelve failed for {name}: {e}")
            return False

    def delete(self, name: Optional[str] = None) -> bool:
        """Deletes an OpenStack VM."""
        if not name or not self.exists(name):
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"VM {name} not found in {self.cloud_name}")
            return False
        try:
            node = self._find_node(name)
            if node:
                self.driver.destroy_node(node)
                return True
            return False
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Libcloud delete failed for {name}: {e}")
            raise VMProviderError(f"Libcloud delete failed for {name}: {e}") from e

    def list(self) -> List[Dict[str, Any]]:
        """Lists all OpenStack VMs with their reachable IP addresses."""
        try:
            nodes = self.driver.list_nodes()
            if nodes:
                results = []
                for n in nodes:
                    # Prioritize public IP if available in libcloud node object
                    ip = n.public_ips[0] if getattr(n, 'public_ips', None) else self._get_floating_ip(n.name)
                    results.append({
                        "name": n.name, 
                        "id": n.id, 
                        "status": n.state, 
                        "ip": ip or "No IP",
                        "image": getattr(n, 'image', 'Unknown'),
                        "flavor": getattr(n, 'size', 'Unknown'),
                        "networks": getattr(n, 'public_ips', [])
                    })
                return results
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.warning(f"Libcloud list failed: {e}. Trying CLI fallback...")

        # CLI Fallback
        try:
            # openstack server list --format value -c Name -c ID -c Status -c Image -c Flavor -c Networks
            output = self._run_cli_command([
                "openstack",
                "server",
                "list",
                "--format",
                "value",
                "-c", "Name",
                "-c", "ID",
                "-c", "Status",
                "-c", "Image",
                "-c", "Flavor",
                "-c", "Networks",
            ])

            results = []
            lines = output.strip().split("\n")
            for line in lines[1:]: # Skip header
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 6:
                    results.append({
                        "name": parts[0],
                        "id": parts[1],
                        "status": parts[2],
                        "image": parts[3],
                        "flavor": parts[4],
                        "networks": parts[5],
                    })
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
                raise VMResourceError(f"VM {name} not found")

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
        except VMResourceError:
            raise
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error getting info for VM {name} in {self.cloud_name}: {e}")
            raise VMProviderError(f"Error getting info for VM {name} in {self.cloud_name}: {e}") from e

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
                logger.error(f"CLI fallback failed: {sanitize_output(result.stderr)}")
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
            result = self._run_cli_command([
                "openstack",
                "security",
                "group",
                "show",
                name,
                "-f",
                "value",
                "-c", "id",
                "-c", "name",
                "-c", "description",
            ])
            parts = result.strip().split("\t")
            if len(parts) >= 3:
                return {
                    "id": parts[0],
                    "name": parts[1],
                    "description": parts[2],
                }
            return {"error": "Unexpected output format from CLI"}
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error getting security group info for {name}: {e}")
            raise VMProviderError(f"Could not get security group info for {name} in {self.cloud_name}: {e}") from e

    def create_security_group(self, name: str, description: str = "") -> bool:
        """Creates a security group in OpenStack."""
        try:
            cmd = ["openstack", "security", "group", "create"]
            if description:
                cmd.extend(["--description", description])
            cmd.append(name)
            self._run_cli_command(cmd)
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error creating security group {name}: {e}")
            return False

    def delete_security_group(self, name: str) -> bool:
        """Deletes a security group in OpenStack."""
        try:
            self._run_cli_command(["openstack", "security", "group", "delete", name])
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error deleting security group {name}: {e}")
            return False

    def add_security_group_to_vm(self, vm_name: str, sg_name: str) -> bool:
        """Associates a security group with a VM."""
        try:
            self._run_cli_command(["openstack", "server", "add", "security", "group", vm_name, sg_name])
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error adding security group {sg_name} to VM {vm_name}: {e}")
            return False

    def remove_security_group_from_vm(self, vm_name: str, sg_name: str) -> bool:
        """Removes a security group association from a VM."""
        try:
            self._run_cli_command(["openstack", "server", "remove", "security", "group", vm_name, sg_name])
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error removing security group {sg_name} from VM {vm_name}: {e}")
            return False

    def add_security_group_rule(self, sg_name: str, protocol: str, port: str, cidr: str, direction: str = "ingress") -> str:
        """
        Adds a security group rule. Returns the rule ID.
        """
        try:
            cmd = ["openstack", "security", "group", "rule", "create"]
            if direction == "egress":
                cmd.append("--egress")
            else:
                cmd.append("--ingress")
            
            cmd.extend(["--protocol", protocol])
            port_flag = "--dst-port" if direction == "ingress" else "--src-port"
            cmd.extend([port_flag, port])
            cmd.extend(["--remote-ip", cidr])
            cmd.append(sg_name)
            
            result = self._run_cli_command(cmd)
            import re
            match = re.search(r"rule\s+([a-f0-9-]+)", result)
            if match:
                return match.group(1)
            return result.strip()
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error adding security group rule to {sg_name}: {e}")
            raise VMProviderError(f"Could not add security group rule for {sg_name} in {self.cloud_name}: {e}") from e

    def remove_security_group_rule(self, sg_name: str, rule_id: str) -> bool:
        """Removes a rule by ID."""
        try:
            self._run_cli_command(["openstack", "security", "group", "rule", "delete", rule_id])
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error removing security group rule {rule_id}: {e}")
            return False

    def list_security_group_rules(self, sg_name: str) -> List[Dict[str, Any]]:
        """Lists rules for a group."""
        try:
            result = self._run_cli_command([
                "openstack",
                "security",
                "group",
                "rule",
                "list",
                sg_name,
                "-f",
                "value",
                "-c", "id",
                "-c", "protocol",
                "-c", "port_range_min",
                "-c", "port_range_max",
                "-c", "remote_ip",
            ])

            rules = []
            for line in result.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("\t")
                if len(parts) >= 5:
                    rules.append({
                        "id": parts[0],
                        "protocol": parts[1],
                        "port_range_min": parts[2],
                        "port_range_max": parts[3],
                        "remote_ip": parts[4],
                    })
            return rules
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error listing rules for {sg_name}: {e}")
            return []

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

    def upload_key(self, key_path: str, key_name: str, vm_name: Optional[str] = None) -> bool:
        """
        Uploads a public key to OpenStack.
        """
        try:
            import subprocess
            import os
            key_path = os.path.expanduser(key_path)
            if not os.path.exists(key_path):
                return False
            
            # If key_name is not provided, use a default name based on the file path
            if not key_name:
                key_name = os.path.basename(key_path).replace(".pub", "")
            
            self._run_cli_command(["openstack", "key", "create", "--public-key", key_path, key_name])
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error uploading key {key_name}: {e}")
            return False

    def delete_key(self, key_name: str, vm_name: Optional[str] = None) -> bool:
        """
        Deletes a public key from OpenStack.
        """
        try:
            import subprocess
            self._run_cli_command(["openstack", "key", "delete", key_name])
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error deleting key {key_name}: {e}")
            return False

    def _get_floating_ip(self, name: str) -> Optional[str]:
        """
        Internal helper to retrieve the floating IP address of a VM.
        """
        try:
            # libcloud lists floating IPs in public_ips (same source as list())
            node = self._find_node(name)
            public_ips = getattr(node, "public_ips", None) if node is not None else None
            if isinstance(public_ips, list) and public_ips:
                return public_ips[0]

            result = self._run_cli_command(["openstack", "server", "show", name, "--format", "value", "-c", "addresses"])
            # Output is like: 'network: a=10.0.0.1,net-id=...; floating: a=1.2.3.4,net-id=...'
            parts = result.split(';')
            for part in parts:
                if 'floating' in part:
                    if ':' in part:
                        val = part.split(':', 1)[1].strip()
                        addr_parts = val.split(',')
                        for attr in addr_parts:
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


    def get_provider_info(self) -> Dict[str, Any]:
        """Gets detailed information about the OpenStack provider."""
        info = {
            "provider": "OpenStack",
            "cloud_name": self.cloud_name,
            "version": self.version,
        }

        try:
            result = self._run_cli_command([
                "openstack",
                "configuration",
                "show",
                "-f",
                "json",
                "-c",
                "region_name",
                "-c",
                "auth.auth_url",
            ])

            import json
            cloud_info = json.loads(result)

            info.update({
                "region": cloud_info.get("region_name"),
                "auth_url": cloud_info.get("auth.auth_url"),
        })

        except Exception:
            pass

        return info

    def _get_current_status(self, name: str) -> str:
        """Returns the current status of the OpenStack VM."""
        node = self._find_node(name)
        return getattr(node, 'state', '') if node else ''

    def _normalize_status(self, status: str) -> str:
        """Normalizes status, treating 'active' as 'running'."""
        normalized = super()._normalize_status(status)
        return 'running' if normalized == 'active' else normalized


    def _get_current_status(self, name: str) -> str:
        """Returns the current status of the OpenStack VM."""
        node = self._find_node(name)
        return getattr(node, 'state', '') if node else ''

    def _normalize_status(self, status: str) -> str:
        """Normalizes status, treating 'active' as 'running'."""
        normalized = super()._normalize_status(status)
        return 'running' if normalized == 'active' else normalized
