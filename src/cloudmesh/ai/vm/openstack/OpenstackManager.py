from pathlib import Path
import yaml
from typing import List, Dict, Any, Optional
import re
from cloudmesh.ai.vm.CloudBaseManager import CloudBaseManager
from cloudmesh.ai.vm.exceptions import ConfigError, VMResourceError, VMAuthError, VMNetworkError, VMProviderError

class OpenstackManager(CloudBaseManager):
    """
    Base Manager for OpenStack-based clouds.
    Implements common OpenStack VM operations using OpenStack SDK.
    """

    def __init__(self, config: Any, cloud_name: Optional[str] = None, **kwargs):
        super().__init__(config, **kwargs)

        # If cloud_name is not provided, try to infer it from the config
        if not cloud_name:
            # Check if 'jetstream' or 'chameleon' are in the config first
            # as this class is the base for them.
            clouds = getattr(config, "clouds", {}) if hasattr(config, "clouds") else {}
            if not clouds and isinstance(config, dict):
                clouds = config.get("clouds", {})

            if "jetstream" in clouds:
                cloud_name = "jetstream"
            elif "chameleon" in clouds:
                cloud_name = "chameleon"
            else:
                cloud_name = "openstack"

        self.cloud_name = cloud_name

    def _get_sdk_conn(self):
        """
        Returns an authenticated OpenStack SDK connection.
        Merges Cloudmesh config with standard clouds.yaml.
        """
        from cloudmesh.ai.vm.logger import logger
        import openstack
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
                    os_clouds = os_full_config.get("clouds", {})
                    os_cloud_cfg = os_clouds.get(self.cloud_name, {})

                    # Merge: OS config takes priority for auth credentials
                    os_auth = os_cloud_cfg.get("auth", {})
                    cm_auth = cloud_config.get("auth", {})
                    merged_auth = {**cm_auth, **os_auth}

                    cloud_config = {**cloud_config, **os_cloud_cfg}
                    cloud_config["auth"] = merged_auth
                    logger.debug(f"Merged configuration for '{self.cloud_name}' from {os_clouds_path}")
            except Exception as e:
                logger.warning(f"Could not parse {os_clouds_path}: {e}")

        try:
            # OpenStack SDK connect can take a config dict via the 'cloud' param
            # if it's a valid clouds.yaml entry, but for custom merged configs,
            # we use the auth and region parameters directly.
            auth = cloud_config.get("auth", {})

            # We use openstack.connect and pass the merged config
            # If cloud_name is in clouds.yaml, this works.
            # To ensure the merged config is used, we can pass the config dict.
            return openstack.connect(
                cloud=self.cloud_name,
                # Pass merged auth if available to ensure CM state is used
                auth_url=auth.get("auth_url") or cloud_config.get("auth_url"),
                username=auth.get("username") or cloud_config.get("username"),
                password=auth.get("password") or cloud_config.get("password"),
                project_name=auth.get("project_name") or cloud_config.get("project_name"),
                user_domain_name=auth.get("user_domain_name") or cloud_config.get("user_domain_name", "Default"),
                project_domain_name=auth.get("project_domain_name") or cloud_config.get("project_domain_name", "Default"),
                region_name=cloud_config.get("region_name") or auth.get("region_name")
            )
        except Exception as e:
            logger.error(f"Failed to connect to OpenStack SDK for cloud {self.cloud_name}: {e}")
            raise VMAuthError(f"OpenStack SDK connection failed: {e}") from e

    def start(self, name: Optional[str] = None, flavor: Optional[str] = None, image: Optional[str] = None, **kwargs) -> str:
        """Starts a VM in OpenStack using the SDK."""
        cloud_config = self.get_cloud_config(self.cloud_name)
        image_name = image or cloud_config.get("image")
        flavor_name = flavor or cloud_config.get("flavor")
        security_group = cloud_config.get("security_group", "default")
        key_name = cloud_config.get("key_name")
        if not key_name and cloud_config.get("key_path"):
            key_name = Path(cloud_config["key_path"]).name.replace(".pub", "")

        from cloudmesh.ai.vm.logger import logger
        logger.debug(f"Using key_name: {key_name} (derived from config/clouds.yaml)")

        if not image_name:
            raise ConfigError(f"Missing 'image' in config for {self.cloud_name}")
        if not flavor_name:
            raise ConfigError(f"Missing 'flavor' in config for {self.cloud_name}")

        try:
            conn = self._get_sdk_conn()
            # Find image and flavor objects
            img = conn.compute.find_image(image_name)
            if not img:
                raise VMResourceError(f"Could not find image {image_name} in {self.cloud_name}")

            flv = conn.compute.find_flavor(flavor_name)
            if not flv:
                raise VMResourceError(f"Could not find flavor {flavor_name} in {self.cloud_name}")

            sg = conn.network.find_security_group(security_group)
            if sg is None:
                raise VMResourceError(
                    f"Could not find security group {security_group} in {self.cloud_name}"
                )

            vm_name = name or f"vm-{self.cloud_name}"

            # Append username and site for shared clouds to prevent collisions
            # ONLY if a name was not explicitly provided by the user.
            if not name and self.cloud_name in ["jetstream", "chameleon"]:
                username = cloud_config.get("username", "user").replace("_", "-")
                site = cloud_config.get("site", self.cloud_name).replace("_", "-").replace("@", "").lower()

                if site == self.cloud_name:
                    vm_name = f"{vm_name}-{username}"
                else:
                    vm_name = f"{vm_name}-{site}-{username}"

            # Create server using SDK
            network_name = self._get_default_network()
            server = conn.compute.create_server(
                name=vm_name,
                image_id=img.id,
                flavor_id=flv.id,
                key_name=key_name,
                security_groups=[{"name": sg.name}],
                networks=[{"uuid": network_name}] if network_name else [],
            )

            # Wait for the VM to actually be ACTIVE before proceeding to IP assignment
            if not self.wait_for_active(vm_name):
                raise VMProviderError(f"VM {vm_name} failed to become ACTIVE. Aborting start.")

            # Automatically assign a floating IP to make the VM reachable if requested
            if kwargs.get('assign_ip', True):
                fip = self.assign_floating_ip(vm_name)
                if fip:
                    from cloudmesh.ai.vm.logger import logger
                    logger.info(f"Floating IP {fip} assigned. Verifying SSH connectivity...")
                    if self.wait_for_login(vm_name):
                        logger.info(f"VM {vm_name} is reachable via SSH.")
                    else:
                        logger.warning(f"VM {vm_name} started but SSH login timed out.")
                else:
                    from cloudmesh.ai.vm.logger import logger
                    logger.warning(f"Requested floating IP for {vm_name} but none could be assigned.")



            return server.id
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"SDK start failed for {self.cloud_name} with key_name '{key_name}': {e}")
            raise VMProviderError(f"SDK start failed for {self.cloud_name} (key_name: {key_name}): {e}") from e

    def wait_for_active(self, name: str, timeout: int = 300) -> bool:
        """
        Waits for the VM to reach the 'active' or 'running' state.
        """
        import time
        from cloudmesh.ai.vm.logger import logger

        logger.info(f"Waiting for VM {name} to become active/running...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            node = self._find_node(name)
            if node:
                # Use OpenStack SDK server status
                status = getattr(node, 'status', '').lower()

                if status == 'active':
                    logger.info(f"VM {name} is now active (status: {status}).")
                    return True
                logger.debug(f"VM {name} is currently in state: {status}. Waiting...")
            else:
                logger.debug(f"VM {name} not found yet. Waiting...")

            time.sleep(10)

        logger.error(f"Timeout reached waiting for VM {name} to become active.")
        return False

    def wait_for_login(self, name: str, timeout: int = 300, check_command: str = "uptime") -> bool:
        """
        Waits until the VM is reachable via SSH.
        """
        import time
        from cloudmesh.ai.vm.logger import logger

        logger.info(f"Waiting for SSH login to be available on VM {name} using command '{check_command}'...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Try the check command to verify connectivity
            result = self.run_command(name, check_command)
            if result and not result.startswith("Error:") and not result.startswith("SSH Error"):
                logger.info(f"SSH login successful for VM {name} (verified with '{check_command}').")
                return True

            logger.debug(f"SSH login not yet available for {name} ({result}). Waiting...")
            time.sleep(10)

        logger.error(f"Timeout reached waiting for SSH login to VM {name} using command '{check_command}'.")
        return False

    def _find_node(self, identifier: str):
        """Helper to find a server by name or ID using the SDK."""
        try:
            conn = self._get_sdk_conn()
            return conn.compute.find_server(identifier)
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.debug(f"Error finding server {identifier} via SDK: {e}")
            return None

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
            conn = self._get_sdk_conn()
            server = self._find_node(name)
            if not server:
                raise VMProviderError(f"VM {name} not found during stop attempt.")

            # Check for terminal Error state
            if getattr(server, 'status', '').lower() == 'error':
                from cloudmesh.ai.vm.logger import logger
                logger.error(f"VM {name} is in ERROR state. Stop operation will not succeed.")
                raise VMProviderError(f"VM {name} is in ERROR state and cannot be stopped.")

            conn.compute.stop_server(server)
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"SDK stop failed for {name}: {e}")
            raise VMProviderError(f"SDK stop failed for {name}: {e}") from e

    def shelve(self, name: Optional[str] = None) -> bool:
        """Shelves an OpenStack VM (preserves disk, releases compute resources)."""
        if not name: return False
        try:
            conn = self._get_sdk_conn()
            server = self._find_node(name)
            if server:
                conn.compute.shelve_server(server)
                return True
            return False
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"SDK shelve failed for {name}: {e}")
            return False

    def unshelve(self, name: Optional[str] = None) -> bool:
        """Unshelves an OpenStack VM."""
        if not name: return False
        try:
            conn = self._get_sdk_conn()
            server = self._find_node(name)
            if server:
                conn.compute.unshelve_server(server)
                return True
            return False
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"SDK unshelve failed for {name}: {e}")
            return False

    def delete(self, name: Optional[str] = None) -> bool:
        """Deletes an OpenStack VM and releases its floating IP."""
        if not name or not self.exists(name):
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"VM {name} not found in {self.cloud_name}")
            return False
        try:
            # Release floating IP before deleting the VM
            self.release_floating_ip(name)

            conn = self._get_sdk_conn()
            server = self._find_node(name)
            if server:
                conn.compute.delete_server(server)
                return True
            return False
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"SDK delete failed for {name}: {e}")
            raise VMProviderError(f"SDK delete failed for {name}: {e}") from e

    def list(self) -> List[Dict[str, Any]]:
        """Lists all OpenStack VMs with their reachable IP addresses using the SDK."""
        try:
            conn = self._get_sdk_conn()
            servers = conn.compute.servers()
            results = []
            for s in servers:
                # Try to find a floating IP for the server
                fip = None
                # In openstacksdk, addresses are in a dict. We look for 'floating'
                addresses = getattr(s, 'addresses', {})
                if addresses and 'floating' in addresses:
                    fip = addresses['floating'][0].get('addr') if addresses['floating'] else None

                results.append({
                    "name": s.name,
                    "id": s.id,
                    "status": s.status,
                    "ip": fip or "No IP",
                    "image": s.image.name if s.image else "Unknown",
                    "flavor": s.flavor.name if s.flavor else "Unknown",
                    "networks": [a.get('addr') for net in addresses.values() for a in net] if addresses else [],
                })
            return results
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"SDK list failed: {e}")
            return []

    def info(self, name: str, kind: str = "vm") -> Dict[str, Any]:
        """
        Gets detailed information about an OpenStack VM.
        """
        try:
            server = self._find_node(name)
            if not server:
                raise VMResourceError(f"VM {name} not found")

            floating_ip = self._get_floating_ip(name)
            flavor = getattr(server, 'flavor', None)

            return {
                "Name": getattr(server, 'name', name),
                "ID": getattr(server, 'id', 'N/A'),
                "State": getattr(server, 'status', 'Unknown'),
                "FloatingIP": floating_ip or "Not Assigned",
                "PublicIPs": getattr(server, 'public_ips', []),
                "PrivateIPs": getattr(server, 'private_ips', []),
                "RAM": getattr(flavor, 'ram', 'N/A'),
                "CPUs": getattr(flavor, 'vcpus', 'N/A'),
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

        self.print(f"Connect to your VM using:\nssh -i {key_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {user}@{floating_ip}")
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

    def suspend(self, name: Optional[str] = None) -> bool:
        """Suspends an OpenStack VM."""
        if not name: return False
        try:
            conn = self._get_sdk_conn()
            server = self._find_node(name)
            if server:
                conn.compute.suspend_server(server)
                return True
            return False
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"SDK suspend failed for {name}: {e}")
            return False

    def restart(self, name: Optional[str] = None) -> bool:
        """Restarts an OpenStack VM."""
        if not name: return False
        try:
            conn = self._get_sdk_conn()
            server = self._find_node(name)
            if server:
                conn.compute.reboot_server(server)
                return True
            return False
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"SDK restart failed for {name}: {e}")
            return False

    def get_images(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Lists available images in OpenStack.
        """
        try:
            from cloudmesh.ai.vm.logger import logger
            logger.debug("Fetching images from OpenStack SDK...")
            conn = self._get_sdk_conn()
            sdk_images = conn.compute.images()
            images_list = [{"id": img.id, "name": img.name} for img in sdk_images]
            logger.debug(f"SDK returned {len(images_list)} images.")
            return images_list
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error getting images: {e}")
            return []

    def get_flavors(self, **kwargs) -> List[Dict[str, Any]]:
        """
        Lists available flavors in OpenStack.
        """
        try:
            from cloudmesh.ai.vm.logger import logger
            logger.debug("Fetching flavors from OpenStack SDK...")
            conn = self._get_sdk_conn()
            sdk_flavors = conn.compute.flavors()
            flavors = [{"id": f.id, "name": f.name, "ram": f.ram, "vcpus": f.vcpus} for f in sdk_flavors]
            logger.debug(f"SDK returned {len(flavors)} flavors.")
            return flavors
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error getting flavors: {e}")
            return []
            return []

    def get_keys(self) -> List[Dict[str, Any]]:
        """
        Lists available keys in OpenStack using the SDK.
        """
        try:
            conn = self._get_sdk_conn()
            keys = conn.compute.keypairs()
            return [{"name": k.name, "fingerprint": k.fingerprint} for k in keys]
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error listing OpenStack keys: {e}")
            return []

    def get_security_groups(self) -> List[Dict[str, Any]]:
        """
        Lists available security groups in OpenStack using the SDK.
        """
        try:
            conn = self._get_sdk_conn()
            groups = conn.network.security_groups()
            return [{"name": g.name, "description": g.description} for g in groups]
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error listing security groups: {e}")
            return []

    def get_security_group_info(self, name: str) -> Dict[str, Any]:
        """
        Gets detailed information for a specific security group using the SDK.
        """
        try:
            conn = self._get_sdk_conn()
            sg = conn.network.find_security_group(name)
            if sg:
                return {
                    "id": sg.id,
                    "name": sg.name,
                    "description": sg.description,
                }
            raise VMResourceError(f"Security group {name} not found")
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error getting security group info for {name}: {e}")
            raise VMProviderError(f"Could not get security group info for {name} in {self.cloud_name}: {e}") from e

    def create_security_group(self, name: str, description: str = "") -> bool:
        """Creates a security group in OpenStack using the SDK."""
        try:
            conn = self._get_sdk_conn()
            conn.network.create_security_group(name=name, description=description)
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error creating security group {name}: {e}")
            return False

    def delete_security_group(self, name: str) -> bool:
        """Deletes a security group in OpenStack using the SDK."""
        try:
            conn = self._get_sdk_conn()
            sg = conn.network.find_security_group(name)
            if sg:
                conn.network.delete_security_group(sg.id)
                return True
            return False
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error deleting security group {name}: {e}")
            return False

    def add_security_group_to_vm(self, vm_name: str, sg_name: str) -> bool:
        """Associates a security group with a VM using the SDK."""
        try:
            conn = self._get_sdk_conn()
            server = conn.compute.find_server(vm_name)
            sg = conn.network.find_security_group(sg_name)
            if server and sg:
                conn.compute.add_security_group_to_server(server, sg.name)
                return True
            return False
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error adding security group {sg_name} to VM {vm_name}: {e}")
            return False

    def remove_security_group_from_vm(self, vm_name: str, sg_name: str) -> bool:
        """Removes a security group association from a VM using the SDK."""
        try:
            conn = self._get_sdk_conn()
            server = conn.compute.find_server(vm_name)
            if server:
                conn.compute.remove_security_group_from_server(server, sg_name)
                return True
            return False
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error removing security group {sg_name} from VM {vm_name}: {e}")
            return False

    def add_security_group_rule(self, sg_name: str, protocol: str, port: str, cidr: str, direction: str = "ingress") -> str:
        """
        Adds a security group rule. Returns the rule ID.
        """
        try:
            conn = self._get_sdk_conn()
            sg = conn.network.find_security_group(sg_name)
            if not sg:
                raise VMResourceError(f"Security group {sg_name} not found")

            rule = conn.network.create_security_group_rule(
                security_group_id=sg.id,
                direction=direction,
                protocol=protocol,
                port_range_min=int(port) if port.isdigit() else None,
                port_range_max=int(port) if port.isdigit() else None,
                remote_ip_prefix=cidr
            )
            return rule.id
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error adding security group rule to {sg_name}: {e}")
            raise VMProviderError(f"Could not add security group rule for {sg_name} in {self.cloud_name}: {e}") from e

    def remove_security_group_rule(self, sg_name: str, rule_id: str) -> bool:
        """Removes a rule by ID."""
        try:
            conn = self._get_sdk_conn()
            conn.network.delete_security_group_rule(rule_id)
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error removing security group rule {rule_id}: {e}")
            return False

    def list_security_group_rules(self, sg_name: str) -> List[Dict[str, Any]]:
        """Lists rules for a group."""
        try:
            conn = self._get_sdk_conn()
            sg = conn.network.find_security_group(sg_name)
            if not sg:
                return []

            rules = conn.network.security_group_rules(security_group_id=sg.id)
            return [{
                "id": r.id,
                "protocol": r.protocol,
                "port_range_min": r.port_range_min,
                "port_range_max": r.port_range_max,
                "remote_ip": r.remote_ip_prefix,
            } for r in rules]
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
            import openstack
            versions.append(f"SDK: {openstack.__version__}")
        except Exception:
            versions.append("SDK: Unknown")

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
        try:
            import openstack
            return True
        except ImportError:
            return False

    def upload_key(self, key_path: str, key_name: str, vm_name: Optional[str] = None) -> bool:
        """
        Uploads a public key to OpenStack using the SDK.
        """
        try:
            import os
            key_path = os.path.expanduser(key_path)
            if not os.path.exists(key_path):
                return False

            # If key_name is not provided, use a default name based on the file path
            if not key_name:
                key_name = os.path.basename(key_path).replace(".pub", "")

            with open(key_path, "r") as f:
                pub_key = f.read().strip()

            conn = self._get_sdk_conn()
            conn.compute.create_keypair(name=key_name, public_key=pub_key)
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error uploading key {key_name}: {e}")
            return False

    def delete_key(self, key_name: str, vm_name: Optional[str] = None) -> bool:
        """
        Deletes a public key from OpenStack using the SDK.
        """
        try:
            conn = self._get_sdk_conn()
            conn.compute.delete_keypair(key_name)
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error deleting key {key_name}: {e}")
            return False

    def _get_default_network(self) -> Optional[str]:
        """
        Finds a default network to use for VM creation.
        Checks config first, then tries to find a usable network via SDK.
        """
        cloud_config = self.get_cloud_config(self.cloud_name)
        network_name = cloud_config.get("network")
        if network_name:
            return network_name

        try:
            conn = self._get_sdk_conn()
            networks = conn.network.networks()
            if networks:
                # Return the first available network
                return networks[0].name
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.debug(f"Could not find a default network for {self.cloud_name}: {e}")

        return None

    def _get_floating_ip(self, name: str) -> Optional[str]:
        """
        Internal helper to retrieve the floating IP address of a VM.
        """
        try:
            server = self._find_node(name)
            if not server:
                return None

            addresses = getattr(server, "addresses", {}) or {}

            for network_addresses in addresses.values():
                for address in network_addresses or []:
                    if address.get("OS-EXT-IPS:type") == "floating":
                        return address.get("addr")

        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.debug(f"Error retrieving floating IP for {name}: {e}")

        return None

    def _wait_for_network(self, node, timeout: int = 300) -> bool:
        """
        Probes the VM until its private network interfaces are ready.
        Returns True if private IPs are assigned, False otherwise.
        """
        import time
        from cloudmesh.ai.vm.logger import logger

        logger.info(f"Probing network readiness for VM {node.name}...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            # Refresh node state from driver
            node = self._find_node(node.name)
            if node and getattr(node, 'private_ips', None):
                logger.info(f"Network is ready for {node.name} (Private IPs: {node.private_ips}).")
                return True

            state = getattr(node, 'state', 'unknown') if node else 'not found'
            logger.info(f"Network not ready for {node.name} yet (State: {state}). Waiting 5s...")
            time.sleep(5)

        logger.error(f"Timeout reached waiting for network readiness for VM {node.name}.")
        return False

    def assign_floating_ip(self, name: str) -> Optional[str]:
        """
        Assigns an available floating IP to the VM.
        Tries to create a new one, falling back to available pools or existing free IPs.
        Handles the case where the instance network is not ready yet by probing.
        """
        try:
            from cloudmesh.ai.vm.logger import logger
            import time

            node = self._find_node(name)
            if not node:
                logger.error(f"VM {name} not found.")
                return None

            # Ensure the VM is active and network is ready before assigning FIP
            if not self.wait_for_active(name):
                logger.error(f"VM {name} failed to become active. Skipping floating IP assignment.")
                return None

            network_ready = self._wait_for_network(node)

            fip = None
            conn = self._get_sdk_conn()
            cloud_config = self.get_cloud_config(self.cloud_name)
            # Use configured pool, or default to 'public'
            pool_name = cloud_config.get("floating_ip_pool", "public")

            try:
                # 1. Try to create a floating IP using the specified or default pool
                logger.debug(f"Attempting to create floating IP from pool '{pool_name}'...")
                pool = conn.network.find_network(pool_name)
                if pool:
                    fip = conn.network.create_floating_ip(floating_network_id=pool.id)
                else:
                    raise Exception(f"Pool '{pool_name}' not found")
            except Exception as e:
                err_msg = str(e)
                if "pool not found" in err_msg.lower() or "404" in err_msg:
                    logger.debug(f"Pool '{pool_name}' not found, trying to find any available pools...")
                    pools = conn.network.floating_ip_pools()
                    if pools:
                        try:
                            # Try the first available pool found by the SDK
                            fallback_pool = pools[0]
                            logger.debug(f"Trying fallback pool '{fallback_pool.name}'...")
                            fip = conn.network.create_floating_ip(floating_network_id=fallback_pool.id)
                        except Exception as pool_e:
                            logger.warning(f"Failed to create FIP from fallback pool {fallback_pool.name}: {pool_e}")
                    else:
                        logger.warning("No floating IP pools found on this cloud.")
                else:
                    logger.debug(f"Creation failed with error: {err_msg}. Trying fallback to existing IPs...")

            if not fip:
                # 2. Fallback: Try to find an existing FREE floating IP
                logger.debug("Attempting to find an existing FREE floating IP...")
                all_fips = conn.network.floating_ips()
                # In SDK, a floating IP is free if it's not associated with a port (fixed_ip is None/missing)
                free_fips = [f for f in all_fips if not getattr(f, 'fixed_ip', None)]
                if free_fips:
                    fip = free_fips[0]
                else:
                    logger.warning("No free floating IPs available and could not create a new one.")

            if fip:
                # Attempt to attach the floating IP.
                max_retries = 3
                for i in range(max_retries):
                    try:
                        conn.compute.add_floating_ip_to_server(node, fip)
                        return fip.floating_ip_address
                    except Exception as e:
                        err_msg = str(e)
                        if "Instance network is not ready yet" in err_msg:
                            if not network_ready and i == max_retries - 1:
                                logger.error(f"Network never became ready for {name}, and final attach attempt failed: {e}")
                            elif i < max_retries - 1:
                                logger.warning(f"Network still not ready for {name}, retrying in 5s... ({i+1}/{max_retries})")
                                time.sleep(5)
                                continue
                        raise e

            return None

        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            err_msg = str(e)
            if "quota" in err_msg.lower():
                logger.error(f"Floating IP quota reached for cloud '{self.cloud_name}'.")
            else:
                logger.error(f"Error assigning floating IP to {name}: {e}")
            return None

    def release_floating_ip(self, name: str) -> bool:
        """
        Releases the floating IP associated with the VM.
        """
        try:
            node = self._find_node(name)
            if not node:
                from cloudmesh.ai.vm.logger import logger
                logger.error(f"VM {name} not found in {self.cloud_name}")
                return False

            # Find floating IPs
            fips = getattr(node, 'public_ips', [])
            if not fips:
                return False

            # We assume the first public IP is the floating IP to release
            fip_address = fips[0]
            conn = self._get_sdk_conn()
            fip = conn.network.find_floating_ip(fip_address)

            if fip:
                # Remove from server
                conn.compute.remove_floating_ip_from_server(node, fip)
                # Delete the IP
                conn.network.delete_floating_ip(fip)
                return True

            return False
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
            conn = self._get_sdk_conn()
            # The SDK connection object provides access to the underlying connection details
            # which include the auth URL and region.
            info.update({
                "region": conn.region,
                "auth_url": conn.auth.auth_url,
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
