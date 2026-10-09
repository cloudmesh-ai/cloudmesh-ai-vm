import yaml
import os
import openstack
from pathlib import Path
from typing import List, Dict, Any, Optional
from cloudmesh.ai.vm.CloudBaseManager import CloudBaseManager
from cloudmesh.ai.vm.exceptions import ConfigError, VMResourceError, VMProviderError

try:
    import chi
except ImportError:
    # Mocking chi for environments where it is not installed
    class ChiMock:
        def use_site(self, site): pass
        def set(self, key, value): pass
        def get(self, key): return None
        def use_project(self, project): pass
        class Lease:
            def add_node_reservation(self, res, node_type, count): res.append({"node_type": node_type, "count": count})
            def lease_duration(self, days): return "start", "end"
            def create_lease(self, name, res, start_date, end_date): pass
        lease = Lease()
    chi = ChiMock()

class Provider(OpenstackManager):
    """
    Chameleon Cloud implementation of the VM Manager.
    Uses the native chi library for all operations.
    """

    def _setup_chi_context(self):
        """
        Ensures the CHI library is configured for the current cloud site and project,
        and injects required OS_ environment variables from the cloud configuration.
        """
        cloud_config = self.get_cloud_config("chameleon")
        site = cloud_config.get("site", "CHI@TACC")
        project = cloud_config.get("project_name")

        if not project:
            raise ConfigError("Error: 'project_name' must be configured in clouds.yaml for Chameleon operations.")

        try:
            # 1. Inject credentials from clouds.yaml into environment variables for chi
            conn = openstack.connect(cloud="chameleon")
            auth = conn.openstack_session.auth

            # Check for Application Credentials specifically
            app_cred_id = getattr(auth, 'application_credential_id', None)
            app_cred_secret = getattr(auth, 'application_credential_secret', None)

            if app_cred_id and app_cred_secret:
                # Force keystoneauth1 to use Application Credentials
                os.environ['OS_AUTH_TYPE'] = 'application_credential'
                os.environ['OS_APPLICATION_CREDENTIAL_ID'] = app_cred_id
                os.environ['OS_APPLICATION_CREDENTIAL_SECRET'] = app_cred_secret
            else:
                # Fallback to standard auth map
                env_map = {
                    'OS_USERNAME': getattr(auth, 'username', None),
                    'OS_PASSWORD': getattr(auth, 'password', None),
                    'OS_AUTH_URL': getattr(auth, 'auth_url', None),
                    'OS_PROJECT_NAME': getattr(auth, 'project_name', None),
                    'OS_PROJECT_DOMAIN_NAME': getattr(auth, 'project_domain_name', None),
                    'OS_USER_DOMAIN_NAME': getattr(auth, 'user_domain_name', None),
                    'OS_AUTH_TYPE': getattr(auth, 'auth_type', 'password'),
                }

                for var, val in env_map.items():
                    if val:
                        os.environ[var] = val
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Failed to inject credentials for chi from cloud 'chameleon': {e}")
            raise ConfigError(f"Could not load credentials from clouds.yaml for cloud 'chameleon': {e}")

        # 2. Configure CHI library context
        chi.use_site(site)
        chi.set("project_name", project)

        if "auth_url" in cloud_config:
            chi.set("auth_url", cloud_config["auth_url"])
        if "region_name" in cloud_config:
            chi.set("region_name", cloud_config["region_name"])

    def _get_node_type(self, flavor: str) -> str:
        """
        Maps an OpenStack flavor name to a Chameleon node type.
        """
        cloud_config = self.get_cloud_config("chameleon")
        mapping = cloud_config.get("node_type_mapping", {
            "m1.small": "compute_haswell",
            "m1.medium": "compute_haswell",
            "m1.large": "compute_haswell",
        })
        return mapping.get(flavor, "compute_haswell")

    def _get_current_status(self, name: str) -> str:
        """
        Returns the current status of the Chameleon VM.
        """
        self._setup_chi_context()
        try:
            server = chi.server.get_server(name)
            return server.status if server else ""
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.debug(f"Error getting status for VM {name}: {e}")
            return ""

    def start(self, name: Optional[str] = None, flavor: Optional[str] = None, image: Optional[str] = None, assign_ip: bool = True) -> str:
        """Starts a VM in Chameleon using the chi library, automatically creating a reservation."""
        self._setup_chi_context()
        cloud_config = self.get_cloud_config("chameleon")
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
            # 1. Automatic Reservation for Chameleon
            node_type = self._get_node_type(flavor_name)
            vm_name = name or f"vm-{self.cloud_name}"
            if not name and self.cloud_name in ["jetstream", "chameleon"]:
                username = cloud_config.get("username", "user").replace("_", "-")
                site = cloud_config.get("site", self.cloud_name).replace("_", "-").replace("@", "").lower()
                vm_name = f"{vm_name}-{username}" if site == self.cloud_name else f"{vm_name}-{site}-{username}"

            res_name = f"res-{vm_name}"
            reservation_id = self.create_reservation(
                name=res_name,
                node_type=node_type,
                count=1,
                duration=1 # Default to 1 day
            )

            if not reservation_id:
                from cloudmesh.ai.vm.logger import logger
                logger.warning(f"Could not create automatic reservation for {vm_name}. Attempting to start without it...")

            # 2. Launch the server using chi
            scheduler_hints = {'reservation_id': reservation_id} if reservation_id else {}

            s = chi.server.Server(
                name=vm_name,
                image_name=image_name,
                flavor_name=flavor_name,
                key_name=key_name,
                security_groups=[security_group],
                scheduler_hints=scheduler_hints,
            )
            s.submit(idempotent=True)

            # Wait until instance is active
            s.wait(status="ACTIVE")

            if assign_ip:
                self.assign_floating_ip(vm_name)

            return s.id
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI start failed for {self.cloud_name}: {e}")
            raise VMProviderError(f"CHI start failed for {self.cloud_name}: {e}") from e

    def stop(self, name: Optional[str] = None) -> bool:
        """Stops a Chameleon VM."""
        if not name: return False
        self._setup_chi_context()
        try:
            server = chi.server.get_server(name)
            if not server:
                return False
            # Use the raw nova client for stop operation
            chi.server.nova().servers.stop(server.id)
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI stop failed for {name}: {e}")
            return False

    def restart(self, name: Optional[str] = None) -> bool:
        """Restarts a Chameleon VM."""
        if not name: return False
        self._setup_chi_context()
        try:
            server = chi.server.get_server(name)
            if not server:
                return False
            chi.server.nova().servers.reboot(server.id)
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI restart failed for {name}: {e}")
            return False

    def suspend(self, name: Optional[str] = None) -> bool:
        """Suspends a Chameleon VM."""
        if not name: return False
        self._setup_chi_context()
        try:
            server = chi.server.get_server(name)
            if not server:
                return False
            chi.server.nova().servers.suspend(server.id)
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI suspend failed for {name}: {e}")
            return False

    def delete(self, name: Optional[str] = None) -> bool:
        """Deletes a Chameleon VM and releases its floating IP."""
        if not name: return False
        self._setup_chi_context()
        try:
            self.release_floating_ip(name)
            server = chi.server.get_server(name)
            if server:
                server.delete()
                return True
            return False
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI delete failed for {name}: {e}")
            raise VMProviderError(f"CHI delete failed for {name}: {e}") from e

    def list(self) -> List[Dict[str, Any]]:
        """Lists all Chameleon VMs with their reachable IP addresses."""
        self._setup_chi_context()
        try:
            servers = chi.server.list_servers()
            results = []
            for s in servers:
                ip = s.addresses[0] if getattr(s, 'addresses', None) else "No IP"
                results.append({
                    "name": s.name,
                    "id": s.id,
                    "status": s.status,
                    "ip": ip,
                    "image": getattr(s, 'image_name', 'Unknown'),
                    "flavor": getattr(s, 'flavor_name', 'Unknown'),
                    "networks": s.addresses if getattr(s, 'addresses', None) else []
                })
            return results
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.warning(f"CHI list failed: {e}")
            return []

    def info(self, name: str) -> Dict[str, Any]:
        """Gets detailed information about a Chameleon VM."""
        self._setup_chi_context()
        try:
            server = chi.server.get_server(name)
            if not server:
                raise VMResourceError(f"VM {name} not found")

            floating_ip = self._get_floating_ip(name)

            return {
                "Name": server.name,
                "ID": server.id,
                "State": server.status,
                "FloatingIP": floating_ip or "Not Assigned",
                "PublicIPs": server.addresses if getattr(server, 'addresses', None) else [],
                "RAM": getattr(server, 'ram', 'N/A'),
                "CPUs": getattr(server, 'vcpus', 'N/A'),
            }
        except VMResourceError:
            raise
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"Error getting info for VM {name} in {self.cloud_name}: {e}")
            raise VMProviderError(f"Error getting info for VM {name} in {self.cloud_name}: {e}") from e

    def login(self, name: Optional[str] = None) -> bool:
        """Provides the SSH connection string for the Chameleon VM."""
        if not name:
            self.print("Error: VM name is required to login.")
            return False

        floating_ip = self._get_floating_ip(name)
        if not floating_ip:
            self.print(f"No floating IP found for VM {name}. Use 'cmc vm assign-floating-ip' first.")
            return False

        cloud_config = self.get_cloud_config("chameleon")
        key_path = cloud_config.get("key_path", "~/.ssh/id_rsa")
        user = cloud_config.get("user", "ubuntu")

        self.print(f"Connect to your VM using:\nssh -i {key_path} {user}@{floating_ip}")
        return True

    def _get_floating_ip(self, name: str) -> Optional[str]:
        """Internal helper to retrieve the floating IP address of a VM."""
        self._setup_chi_context()
        try:
            server = chi.server.get_server(name)
            if server and getattr(server, 'addresses', None):
                return server.addresses[0]
            return None
        except Exception:
            return None

    def assign_floating_ip(self, name: str) -> Optional[str]:
        """Assigns an available floating IP to the VM."""
        self._setup_chi_context()
        try:
            server = chi.server.get_server(name)
            if not server:
                return None
            return server.associate_floating_ip()
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI assign_floating_ip failed for {name}: {e}")
            return None

    def release_floating_ip(self, name: str) -> bool:
        """Releases the floating IP associated with the VM."""
        self._setup_chi_context()
        try:
            server = chi.server.get_server(name)
            if not server:
                return False
            fip = self._get_floating_ip(name)
            if fip:
                server.detach_floating_ip(fip, delete=True)
                return True
            return False
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI release_floating_ip failed for {name}: {e}")
            return False

    def list_regions(self) -> List[Dict[str, Any]]:
        """Lists available sites/regions in Chameleon Cloud."""
        self._setup_chi_context()
        try:
            sites_dict = chi.context.list_sites(show=None)
            regions = []
            for site_name, properties in sites_dict.items():
                regions.append({"name": site_name, **properties})
            return regions
        except Exception as e:
            self.print(f"Error listing Chameleon regions: {e}")
            return []

    def create_reservation(self, name: str, node_type: str, count: int, start_date: str = None, end_date: str = None, duration: int = None) -> Optional[str]:
        """
        Creates a node reservation (lease) in Chameleon Cloud using python-chi.
        Returns the reservation ID if successful, None otherwise.
        """
        self._setup_chi_context()
        try:
            reservations = []
            chi.lease.add_node_reservation(
                reservations,
                node_type=node_type,
                count=count,
            )

            if duration:
                s, e = chi.lease.lease_duration(days=duration)
            elif start_date and end_date:
                s, e = start_date, end_date
            else:
                s, e = chi.lease.lease_duration(days=1)

            lease = chi.lease.create_lease(
                name,
                reservations,
                start_date=s,
                end_date=e,
            )
            return lease.get('id') if isinstance(lease, dict) else getattr(lease, 'id', None)
        except Exception as e:
            self.print(f"Error creating reservation in Chameleon: {e}")
            return None

    def get_account_info(self) -> Dict[str, Any]:
        """Returns account information for Chameleon using chi."""
        self._setup_chi_context()
        try:
            return {
                "site": chi.get("site"),
                "project_name": chi.get("project_name"),
                "project_id": chi.get("project_id"),
                "user_id": chi.get("user_id"),
                "allocation": chi.get("allocation") if hasattr(chi, "get") else "Unknown"
            }
        except Exception as e:
            self.print(f"Error fetching Chameleon account info: {e}")
            return {"error": f"Failed to fetch Chameleon account info: {str(e)}"}

    def get_images(self, **kwargs) -> List[Dict[str, Any]]:
        """Lists all available images in Chameleon Cloud using python-chi."""
        self._setup_chi_context()
        try:
            # is_chameleon_supported=False returns all images without filtering
            images = chi.image.list_images(is_chameleon_supported=False)
            return [{"id": img.uuid, "name": img.name} for img in images]
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI get_images failed for {self.cloud_name}: {e}")
            return []

    def get_flavors(self, **kwargs) -> List[Dict[str, Any]]:
        """Lists available flavors in Chameleon Cloud."""
        self._setup_chi_context()
        try:
            flavors = chi.server.list_flavors()
            return [{"id": f.id, "name": f.name, "ram": f.ram, "vcpus": f.vcpus} for f in flavors]
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI get_flavors failed: {e}")
            return []

    def get_keys(self) -> List[Dict[str, Any]]:
        """Lists available keys in Chameleon Cloud."""
        self._setup_chi_context()
        try:
            keys = chi.server.list_keypair()
            return [{"name": k.name, "fingerprint": k.fingerprint} for k in keys]
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI get_keys failed: {e}")
            return []

    def upload_key(self, key_path: str, key_name: str, vm_name: Optional[str] = None) -> bool:
        """Uploads a public key to Chameleon Cloud."""
        self._setup_chi_context()
        try:
            key_path = os.path.expanduser(key_path)
            with open(key_path, 'r') as f:
                public_key = f.read()
            chi.server.update_keypair(key_name, public_key)
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI upload_key failed for {key_name}: {e}")
            return False

    def delete_key(self, key_name: str, vm_name: Optional[str] = None) -> bool:
        """Deletes a public key from Chameleon Cloud."""
        self._setup_chi_context()
        try:
            chi.server.nova().keypairs.delete(key_name)
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI delete_key failed for {key_name}: {e}")
            return False

    def get_security_groups(self) -> List[Dict[str, Any]]:
        """Lists available security groups in Chameleon Cloud."""
        self._setup_chi_context()
        try:
            groups = chi.network.list_security_groups()
            return [{"name": g.name, "description": g.description} for g in groups]
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI get_security_groups failed: {e}")
            return []

    def get_security_group_info(self, name: str) -> Dict[str, Any]:
        """Gets detailed information for a specific security group."""
        self._setup_chi_context()
        try:
            return chi.network._resolve_resource("security_group", name)
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI get_security_group_info failed for {name}: {e}")
            raise VMProviderError(f"Could not get security group info for {name} in {self.cloud_name}: {e}") from e

    def create_security_group(self, name: str, description: str = "") -> bool:
        """Creates a security group in Chameleon Cloud."""
        self._setup_chi_context()
        try:
            sg = chi.network.SecurityGroup({"name": name, "description": description})
            sg.submit()
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI create_security_group failed for {name}: {e}")
            return False

    def delete_security_group(self, name: str) -> bool:
        """Deletes a security group in Chameleon Cloud."""
        self._setup_chi_context()
        try:
            # Resolve name to ID
            sg = chi.network._resolve_resource("security_group", name)
            chi.network.neutron().delete_security_group(sg['id'])
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI delete_security_group failed for {name}: {e}")
            return False

    def add_security_group_to_vm(self, vm_name: str, sg_name: str) -> bool:
        """Associates a security group with a VM."""
        self._setup_chi_context()
        try:
            server = chi.server.get_server(vm_name)
            if server:
                server.add_security_group(sg_name)
                return True
            return False
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI add_security_group_to_vm failed for {vm_name}: {e}")
            return False

    def remove_security_group_from_vm(self, vm_name: str, sg_name: str) -> bool:
        """Removes a security group association from a VM."""
        self._setup_chi_context()
        try:
            server = chi.server.get_server(vm_name)
            if server:
                server.remove_security_group(sg_name)
                return True
            return False
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI remove_security_group_from_vm failed for {vm_name}: {e}")
            return False

    def add_security_group_rule(self, sg_name: str, protocol: str, port: str, cidr: str, direction: str = "ingress") -> str:
        """Adds a security group rule. Returns the rule ID."""
        self._setup_chi_context()
        try:
            # Resolve SG name to ID
            sg = chi.network._resolve_resource("security_group", sg_name)
            sg_id = sg['id']

            rule = chi.network.neutron().create_security_group_rule(
                security_group_id=sg_id,
                direction=direction,
                protocol=protocol,
                port_range_min=port,
                port_range_max=port,
                remote_ip_prefix=cidr
            )
            return rule.id
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI add_security_group_rule failed for {sg_name}: {e}")
            raise VMProviderError(f"Could not add security group rule for {sg_name} in {self.cloud_name}: {e}") from e

    def remove_security_group_rule(self, sg_name: str, rule_id: str) -> bool:
        """Removes a rule by ID."""
        self._setup_chi_context()
        try:
            chi.network.neutron().delete_security_group_rule(rule_id)
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI remove_security_group_rule failed for {rule_id}: {e}")
            return False

    def list_security_group_rules(self, sg_name: str) -> List[Dict[str, Any]]:
        """Lists rules for a group."""
        self._setup_chi_context()
        try:
            rules = chi.network.neutron().list_security_group_rules(sg_name)
            return [
                {
                    "id": r.id,
                    "protocol": r.protocol,
                    "port_range_min": r.port_range_min,
                    "port_range_max": r.port_range_max,
                    "remote_ip": r.remote_ip_prefix,
                }
                for r in rules
            ]
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            logger.error(f"CHI list_security_group_rules failed for {sg_name}: {e}")
            return []
