import yaml
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from cloudmesh.ai.vm.CloudBaseManager import CloudBaseManager
from cloudmesh.ai.vm.exceptions import ConfigError, VMResourceError, VMProviderError
import datetime
from datetime import timedelta
import sys
import time
import traceback
import uuid
from contextlib import redirect_stdout
from io import StringIO
import chi
import chi.lease
import chi.exception
from chi import keypair, lease, network, server
from .ChameleonAuthManager import authenticate_chi_from_cloud
from cloudmesh.ai.vm.logger import logger

class Provider(CloudBaseManager):
    """
    Chameleon Cloud implementation of the VM Manager.
    Uses the native chi library for all operations.
    """

    def __init__(self, config: Any, cloud_name: str, console=None, **kwargs):
        super().__init__(config, console=console)
        self.cloud_name = cloud_name
        self._chi_initialized = False

    def _setup_chi_context(self):
        if self._chi_initialized:
            return

        CLOUD_NAME = os.getenv("OS_CLOUD", "chameleon")
        self.print(f"Authentication at site KVM@TACC...")

        try:
            authenticate_chi_from_cloud(CLOUD_NAME)
        except Exception as e:
            raise ConfigError(f"Authentication shim failed: {e}")

        with redirect_stdout(StringIO()):
            chi.context.use_site("KVM@TACC")

        self._chi_initialized = True

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

    def _vm_exists(self, name: str) -> bool:
        """Checks if a VM with the given name already exists."""
        self._setup_chi_context()
        try:
            server = chi.server.get_server(name)
            return server is not None
        except Exception:
            return False

    def start(self, name: Optional[str] = None, flavor: Optional[str] = None, image: Optional[str] = None, assign_ip: bool = True) -> str:
        """Starts a VM in Chameleon using the chi library, automatically creating a reservation."""
        self._setup_chi_context()
        cloud_config = self.get_cloud_config("chameleon")
        image_name = image or cloud_config.get("image")
        flavor_name = flavor or cloud_config.get("flavor")
        security_group = cloud_config.get("security_group", "default")
        key_name = cloud_config.get("key_name")
        username = cloud_config.get("username", "user")

        # Ensure keypair exists or is assigned
        try:
            existing_keys = [k.name for k in chi.server.list_keypair()]
        except Exception as e:
            self.print(f"Warning: Could not list keypairs: {e}")
            existing_keys = []

        if not key_name:
            if existing_keys:
                key_name = existing_keys[0]
                self.print(f"Using existing keypair: {key_name}")
            else:
                key_name = username
                self.print(f"No keypair found. Uploading new keypair as: {key_name}")
                key_path = cloud_config.get("key_path", "~/.ssh/id_rsa.pub")
                key_filename = os.path.expanduser(key_path)
                try:
                    chi.keypair.Keypair(keypair_public_key=key_filename, key_name=key_name)
                    self.print(f"✅ Keypair {key_name} uploaded and ready")
                except Exception as e:
                    raise VMProviderError(f"Failed to upload keypair {key_name}: {e}")
        else:
            if key_name not in existing_keys:
                self.print(f"Keypair {key_name} not found in cloud. Uploading...")
                key_path = cloud_config.get("key_path", "~/.ssh/id_rsa.pub")
                key_filename = os.path.expanduser(key_path)
                try:
                    chi.keypair.Keypair(keypair_public_key=key_filename, key_name=key_name)
                    self.print(f"✅ Keypair {key_name} uploaded and ready")
                except Exception as e:
                    raise VMProviderError(f"Failed to upload keypair {key_name}: {e}")
            else:
                self.print(f"✅ Using existing keypair: {key_name}")

        # Print essential launch information
        lease_duration = cloud_config.get("lease_duration", "1 hour")
        self.print(f"Launching VM with the following configuration:")
        self.print(f"  Server Name:    {name or f'vm-{self.cloud_name}'}")
        self.print(f"  Image:          {image_name}")
        self.print(f"  Flavor:         {flavor_name}")
        self.print(f"  Key Name:       {key_name}")
        self.print(f"  Security Group: {security_group}")
        self.print(f"  Lease Length:   {lease_duration}")

        try:
            # 1. Mandatory Reservation for Chameleon flavored images
            vm_name = name or f"vm-{self.cloud_name}"

            # Ensure VM name is unique to avoid conflicts with existing VMs
            attempt = 1
            original_vm_name = vm_name
            while True:
                if not self._vm_exists(vm_name):
                    break
                vm_name = f"{original_vm_name}-{attempt}"
                attempt += 1

            if not name and self.cloud_name in ["jetstream", "chameleon"]:
                username_fmt = cloud_config.get("username", "user").replace("_", "-")
                site = cloud_config.get("site", self.cloud_name).replace("_", "-").replace("@", "").lower()
                vm_name = f"{vm_name}-{username_fmt}" if site == self.cloud_name else f"{vm_name}-{site}-{username_fmt}"

            res_name = f"res-{vm_name}"

            # Use the high-level chi.lease.Lease pattern from standalone tests
            lease = chi.lease.Lease(
                res_name,
                duration=timedelta(hours=1)
            )

            # We must reserve the specific flavor being requested
            flavor_id = chi.server.get_flavor_id(flavor_name)
            lease.add_flavor_reservation(id=flavor_id, amount=1)
            lease.submit(idempotent=True)

            # Mandated: Ensure the lease exists and is ACTIVE before launching the VM
            self.print(f"Checking/Creating lease for {res_name}...")
            lease.wait(status="active", timeout=300)

            reservation_id = lease.id
            self.print(f"Lease {res_name} is active (ID: {reservation_id}). Proceeding to launch VM...")

            # 2. LAUNCH THE VIRTUAL MACHINE INSTANCE
            self.print("Launching server instance...")

            actual_flavor_name = lease.get_reserved_flavors()[0].name

            s = chi.server.Server(
                name=vm_name,
                image_name=image_name,
                flavor_name=actual_flavor_name,
                key_name=key_name,
            )

            s.submit(idempotent=True, show="text")

            # Wait until instance is active
            s.wait()

            fip_addr = None
            if assign_ip:
                self.print("Associating a floating IP (polling for ready port)...")
                for i in range(10):
                    try:
                        fip_addr = s.associate_floating_ip()
                        self.print(f"✅ Floating IP associated: {fip_addr}")
                        break
                    except chi.exception.ResourceError as e:
                        if "None of the ports can route" in str(e) and i < 9:
                            self.print(f"  Port not ready yet, retrying in 3s... ({i+1}/10)")
                            time.sleep(3)
                        else:
                            self.print(f"Error associating floating IP: {e}")
                            break
                if not fip_addr:
                    self.print("Timed out waiting for network ports to route Floating IP")

            s.refresh()

            # 3. OPEN PORT 22 (SSH) IN SECURITY GROUPS
            self.print("Configuring security groups for SSH...")
            sg_list = network.list_security_groups(name_filter="allow-ssh")
            if sg_list:
                sg = sg_list[0]
            else:
                sg = network.SecurityGroup(
                    {"name": "allow-ssh", "description": "Enable SSH traffic on TCP port 22"}
                )
                sg.add_rule("ingress", "tcp", 22)
                sg.submit()

            # Attach security group to the server instance
            s.add_security_group(sg.id)

            # 4. PRINT SSH CONNECTION DETAILS
            if fip_addr:
                self.print(f"\nVM is ready! You can SSH in using:")
                self.print(f"ssh cc@{fip_addr}")

            return s.id
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger
            tb = traceback.format_exc()
            logger.error(f"CHI start failed for {self.cloud_name}: {e}\n{tb}")
            raise VMProviderError(f"CHI start failed for {self.cloud_name}: {e}\n{tb}") from e

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
        print("GGGGGGG")
        self._setup_chi_context()
        try:
            servers = chi.server.list_servers()
            print(f"Found {len(servers)} servers.")
            from pprint import pprint
            pprint(servers)
            results = []
            
            for s in servers:
                pprint(s)
                
                # Safely extract the IP address from the addresses dictionary
                ip = "No IP"
                addresses = getattr(s, 'addresses', None)
                if addresses and isinstance(addresses, dict):
                    for net_name, addr_list in addresses.items():
                        if addr_list and len(addr_list) > 0:
                            first_addr = addr_list[0]
                            if isinstance(first_addr, dict):
                                ip = first_addr.get('addr', str(first_addr))
                            else:
                                ip = str(first_addr)
                            break  # Grab the first available IP and exit loop
                
                results.append({
                    "name": s.name,
                    "id": s.id,
                    "status": s.status,
                    "ip": ip,
                    "image": getattr(s, 'image_name', 'Unknown'),
                    "flavor": getattr(s, 'flavor_name', 'Unknown'),
                    "networks": addresses if addresses else {}
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
        """Assigns an available floating IP to the VM with retries for network routing."""
        self._setup_chi_context()
        try:
            server = chi.server.get_server(name)
            if not server:
                return None

            import chi.exception
            for i in range(10):
                try:
                    return server.associate_floating_ip()
                except chi.exception.ResourceError as e:
                    if "None of the ports can route" in str(e) and i < 9:
                        self.print(f"  Port not ready yet, retrying in 3s... ({i+1}/10)")
                        time.sleep(3)
                    else:
                        raise e
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
            import hashlib
            import base64
            keys = chi.server.list_keypair()
            results = []
            for k in keys:
                fingerprint = "N/A"
                if hasattr(k, "public_key") and k.public_key:
                    try:
                        # SSH public keys are formatted as: "type base64_blob comment"
                        parts = k.public_key.split()
                        if len(parts) >= 2:
                            blob = base64.b64decode(parts[1])
                            # MD5 fingerprint is the standard for the format requested: xx:xx:xx...
                            md5_hash = hashlib.md5(blob).digest()
                            fingerprint = ":".join(f"{b:02x}" for b in md5_hash)
                    except Exception:
                        fingerprint = "Error"
                results.append({"name": k.name, "fingerprint": fingerprint})
            return results
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
