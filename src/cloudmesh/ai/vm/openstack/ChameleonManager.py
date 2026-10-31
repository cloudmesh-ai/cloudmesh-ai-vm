import datetime
import json
import logging
import os
import warnings

import yaml

# Suppress the specific neutronclient deprecation warning globally in this module
warnings.filterwarnings(
    "ignore", message=".*python binding code in neutronclient is deprecated.*"
)

# Also suppress via logging in case the library uses logging.warning
logging.getLogger("neutronclient").setLevel(logging.ERROR)

import builtins
import time
import traceback
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any

import chi
import chi.exception
import chi.lease
import humanize
from chi import network, server, lease, keypair

from cloudmesh.ai.vm.CloudBaseManager import CloudBaseManager
from cloudmesh.ai.vm.exceptions import ConfigError, VMProviderError, VMResourceError
from cloudmesh.ai.vm.logger import logger

from .ChameleonAuthManager import authenticate_chi_from_cloud


def DDD(msg):
    if isinstance(msg, dict):
        msg = yaml.safe_dump(msg, sort_keys=False, default_flow_style=False)
    else:
        msg = str(msg)
    print(msg)


class Provider(CloudBaseManager):
    """
    Chameleon Cloud implementation of the VM Manager.
    Uses the native chi library for all operations.
    """

    def __init__(self, config: Any, cloud_name: str, console=None, **kwargs):
        super().__init__(config, console=console)
        self.cloud_name = cloud_name
        # ``assign_ip`` flag for API compatibility; defaults to True.
        self.assign_ip = kwargs.pop("assign_ip", True)
        self._chi_initialized = False

    def _json_serial(self, obj):
        """JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        return str(obj)

    def _get_reservation_details(self, reservation_id):
        """Finds the lease and reservation details for a given reservation ID."""
        try:
            leases = chi.lease.list_leases()
            res_types = [
                "flavor_reservations",
                "node_reservations",
                "fip_reservations",
                "network_reservations",
                "device_reservations",
            ]

            for l in leases:
                for res_type in res_types:
                    reservations = getattr(l, res_type, [])
                    for res in reservations:
                        r_id = (
                            res.get("id")
                            if isinstance(res, dict)
                            else getattr(res, "id", None)
                        )
                        if r_id == reservation_id:

                            def get_val(obj, key, default="N/A"):
                                if isinstance(obj, dict):
                                    return obj.get(key, default)
                                return getattr(obj, key, default)

                            return {
                                "lease": {
                                    "name": get_val(l, "name"),
                                    "id": get_val(l, "id"),
                                    "status": get_val(l, "status"),
                                    "start_date": get_val(l, "start_date"),
                                    "end_date": get_val(l, "end_date"),
                                },
                                "reservation": {
                                    "id": get_val(res, "id"),
                                    "resource_type": get_val(res, "resource_type"),
                                    "status": get_val(res, "status"),
                                    "resource_properties": get_val(
                                        res, "resource_properties"
                                    ),
                                    "amount": get_val(res, "amount"),
                                },
                            }
        except Exception as e:
            return {"error": f"Could not fetch reservation details: {e}"}
        return None

    def _get_security_group_details(self, server):
        """Retrieves security groups and their rules for the server."""
        try:
            sgs = getattr(server, "security_groups", [])
            if not sgs:
                conn = getattr(server, "conn", None)
                if conn:
                    try:
                        server_id = getattr(server, "id", None)
                        server_details = conn.compute.get_server(server_id)
                        sgs = getattr(server_details, "security_groups", [])
                    except Exception:
                        pass
            if not sgs:
                return []

            sg_details = []
            for sg in sgs:
                name = (
                    sg.get("name")
                    if isinstance(sg, dict)
                    else getattr(sg, "name", str(sg))
                )
                try:
                    result = chi.network.neutron().list_security_group_rules(name)
                    rules = (
                        result.get("security_group_rules", [])
                        if isinstance(result, dict)
                        else result
                    )

                    seen_rules = set()
                    unique_rules = []
                    for r in rules:
                        rule_data = {
                            "protocol": r.get("protocol")
                            if isinstance(r, dict)
                            else getattr(r, "protocol", "Unknown"),
                            "port_range_min": r.get("port_range_min")
                            if isinstance(r, dict)
                            else getattr(r, "port_range_min", "Unknown"),
                            "port_range_max": r.get("port_range_max")
                            if isinstance(r, dict)
                            else getattr(r, "port_range_max", "Unknown"),
                            "remote_ip": r.get("remote_ip_prefix")
                            if isinstance(r, dict)
                            else getattr(r, "remote_ip_prefix", "Unknown"),
                            "direction": r.get("direction")
                            if isinstance(r, dict)
                            else getattr(r, "direction", "Unknown"),
                        }
                        for key, val in rule_data.items():
                            if val is None:
                                rule_data[key] = "Any"
                        rule_tuple = tuple(rule_data.items())
                        if rule_tuple not in seen_rules:
                            seen_rules.add(rule_tuple)
                            unique_rules.append(rule_data)
                    sg_details.append({"name": name, "rules": unique_rules})
                except Exception as e:
                    sg_details.append(
                        {"name": name, "error": f"Could not fetch rules: {e}"}
                    )
            return sg_details
        except Exception as e:
            return {"error": f"Could not fetch security groups: {e}"}

    def _setup_chi_context(self):
        """Initializes the CHI context and authenticates if necessary."""
        if self._chi_initialized:
            return

        CLOUD_NAME = os.getenv("OS_CLOUD", "chameleon")
        self.print("Authentication at site KVM@TACC...")

        try:
            authenticate_chi_from_cloud(CLOUD_NAME)
        except Exception as e:
            raise ConfigError(f"Authentication shim failed: {e}")

        with redirect_stdout(StringIO()):
            chi.context.use_site("KVM@TACC")

        self._chi_initialized = True

    def info(self, name: str | None = None, kind: str = "vm") -> dict[str, Any]:
        """
        Returns detailed information about a Chameleon VM.
        :param name: Name of the VM.
        :param kind: Type of info to return: 'all' (full report), 'vm' (vm_info), or 'list' (simplified).
        """
        self._setup_chi_context()

        # 1. Get high-level info from the provider
        try:
            info = self._get_basic_info(name)
        except Exception as e:
            logger.error(f"Error getting provider info for {name}: {e}")
            info = {}

        # 2. Get deep-dive info directly from the chi library
        try:
            server = chi.server.get_server(name)
            if server:
                # Extract and clean attributes from the server object
                raw_attrs = server.__dict__.copy()
                cleaned_attrs = {}
                for k, v in raw_attrs.items():
                    if hasattr(v, "__dict__") or isinstance(v, (set, complex)):
                        cleaned_attrs[k] = str(v)
                    elif isinstance(v, list):
                        cleaned_attrs[k] = [
                            str(i) if hasattr(i, "__dict__") else i for i in v
                        ]
                    else:
                        cleaned_attrs[k] = v

                raw_details = {
                    "raw_attributes": cleaned_attrs,
                    "addresses": getattr(server, "addresses", {}),
                    "status": getattr(server, "status", "Unknown"),
                    "id": getattr(server, "id", "Unknown"),
                    "name": getattr(server, "name", "Unknown"),
                }

                # Resolve Reservation Details
                reservation_info = None
                flavor_name = getattr(server, "flavor_name", "")
                if flavor_name and flavor_name.startswith("reservation:"):
                    res_id = flavor_name.split(":", 1)[1]
                    reservation_info = self._get_reservation_details(res_id)

                # Enhance Provider Info with Flavor details from resource_properties
                if reservation_info and "reservation" in reservation_info:
                    res_props_raw = reservation_info["reservation"].get(
                        "resource_properties", "{}"
                    )
                    try:
                        res_props = (
                            json.loads(res_props_raw)
                            if isinstance(res_props_raw, str)
                            else res_props_raw
                        )
                        info["Flavor"] = {
                            "id": res_props.get("id"),
                            "name": res_props.get("name"),
                            "ram": res_props.get("ram"),
                            "disk": res_props.get("disk"),
                            "vcpus": res_props.get("vcpus"),
                            "extra_specs": res_props.get("extra_specs"),
                            "reservation_id": res_id,
                        }
                    except Exception:
                        pass

                # Resolve Security Group Details
                sg_info = self._get_security_group_details(server)

                # Add simplified security group info to vm_info
                if isinstance(sg_info, list):
                    simplified_sgs = []
                    for sg in sg_info:
                        if not isinstance(sg, dict) or "name" not in sg:
                            continue
                        name_sg = sg["name"]
                        rules_summary = []
                        for r in sg.get("rules", []):
                            if not isinstance(r, dict):
                                continue
                            proto = r.get("protocol", "Any")
                            p_min = r.get("port_range_min", "Any")
                            p_max = r.get("port_range_max", "Any")
                            remote = r.get("remote_ip", "Any")
                            direction = r.get("direction", "Unknown")
                            if proto == "Any" and p_min == "Any" and remote == "Any":
                                summary = f"All {direction}"
                            elif proto == "icmp" and p_min == "Any" and remote == "Any":
                                summary = f"ICMP {direction}"
                            elif proto == "tcp" and p_min == "22" and p_max == "22":
                                remote_label = (
                                    "All" if remote in ["0.0.0.0/0", "Any"] else remote
                                )
                                summary = f"SSH {direction} from {remote_label}"
                            else:
                                port_str = (
                                    f"{p_min}-{p_max}" if p_min != p_max else str(p_min)
                                )
                                remote_label = (
                                    "All" if remote in ["0.0.0.0/0", "Any"] else remote
                                )
                                summary = f"{proto} {port_str} {direction} from {remote_label}"
                            if summary not in rules_summary:
                                rules_summary.append(summary)
                        simplified_sgs.append(
                            {
                                "name": name_sg,
                                "summary": "; ".join(rules_summary)
                                if rules_summary
                                else "No rules",
                            }
                        )
                    info["SecurityGroups"] = simplified_sgs
                elif isinstance(sg_info, dict) and "error" in sg_info:
                    info["SecurityGroups"] = sg_info["error"]

                full_details = {
                    "chi_raw_details": raw_details,
                    "reservation_details": reservation_info,
                    "security_groups": sg_info,
                    "vm_info": info,
                }
            else:
                full_details = {"vm_info": info}
        except Exception as e:
            logger.error(f"Error getting raw chi details for {name}: {e}")
            full_details = {"vm_info": info}

        if kind == "all":
            return full_details
        elif kind == "vm":
            return full_details.get("vm_info", info)
        elif kind == "security_groups":
            return full_details.get("security_groups", sg_info)
        elif kind == "reservation_details":
            return full_details.get("reservation_details", reservation_info)
        elif kind == "chi_raw_details":
            return full_details.get("chi_raw_details", raw_details)
        elif kind == "full":
            return full_details
        elif kind == "list":
            d = {
                "Name": info.get("name", "Unknown"),
                "Status": info.get("status", "Unknown"),
                "Image": info.get("image", "Unknown"),
                "Flavor": info.get("flavor", "Unknown"),
                "IP": info.get("ip", "Unknown"),
                "TTL": info.get("ttl", "Unknown"),
            }
            return d

        return full_details

    def _get_node_type(self, flavor: str) -> str:
        """
        Maps an OpenStack flavor name to a Chameleon node type.
        """
        cloud_config = self.get_cloud_config("chameleon")
        mapping = cloud_config.get(
            "node_type_mapping",
            {
                "m1.small": "compute_haswell",
                "m1.medium": "compute_haswell",
                "m1.large": "compute_haswell",
            },
        )
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

    def start(
        self,
        name: str | None = None,
        flavor: str | None = None,
        image: str | None = None,
        **kwargs,
    ) -> str:
        """Starts a VM in Chameleon using the chi library, automatically creating a reservation."""
        self._setup_chi_context()
        cloud_config = self.get_cloud_config("chameleon")
        image_name = image or cloud_config.get("image")
        flavor_name = flavor or cloud_config.get("flavor")
        security_group = cloud_config.get("security_group", "default")

        username = cloud_config.get("username", "user").replace("_", "-")
        # ``assign_ip`` determines whether a floating IP should be allocated after VM launch.
        assign_ip = kwargs.get("assign_ip", self.assign_ip)
        duration = kwargs.get("duration")
        # Parse optional lease duration string (e.g., '3h', '1d') to timedelta.
        lease_duration_td = timedelta(hours=1)  # Default
        if duration:
            try:
                unit = duration[-1].lower()
                value = int(duration[:-1])
                if unit == "h":
                    lease_duration_td = timedelta(hours=value)
                elif unit == "d":
                    lease_duration_td = timedelta(days=value)
                else:
                    logger.warning(
                        f"Unsupported duration unit '{unit}' for lease. Using default 1h."
                    )
            except Exception as e:
                logger.warning(
                    f"Failed to parse lease duration '{duration}': {e}. Using default 1h."
                )

        # Ensure keypair exists and matches the local key
        key_path = cloud_config.get("key_path", "~/.ssh/id_rsa.pub")
        key_filename = os.path.expanduser(key_path)
        # Determine the key name to use in the cloud. Prefer explicit config, fall back to filename.
        key_name = cloud_config.get("key_name")
        if not key_name:
            # Derive a default name from the key file name (without .pub)
            from pathlib import Path

            key_name = Path(key_path).name.replace(".pub", "")

        try:
            existing_keys = {k.name: k.public_key for k in chi.server.list_keypair()}
        except Exception as e:
            self.print(f"Warning: Could not list keypairs: {e}")
            existing_keys = {}

        # Read the local public key to verify against the cloud
        try:
            with open(key_filename, "r") as f:
                local_pub_key = f.read().strip()
        except Exception as e:
            raise VMProviderError(
                f"Could not read local public key at {key_filename}: {e}"
            )

        if key_name in existing_keys:
            if existing_keys[key_name] == local_pub_key:
                self.print(f"✅ Using existing matching keypair: {key_name}")
            else:
                self.print(
                    f"Keypair {key_name} exists but does not match local key. Updating..."
                )
                try:
                    chi.server.update_keypair(key_name, local_pub_key)
                    self.print(f"✅ Keypair {key_name} updated with local key")
                except Exception as e:
                    raise VMProviderError(f"Failed to update keypair {key_name}: {e}")
        else:
            self.print(f"Keypair {key_name} not found in cloud. Uploading...")
            try:
                # The chi.keypair.Keypair wrapper expects a path to a file, not the key content.
                # To ensure the key is uploaded correctly, we use the filename.
                chi.server.update_keypair(key_name, local_pub_key)
                self.print(f"✅ Keypair {key_name} uploaded and ready")
            except Exception as e:
                raise VMProviderError(f"Failed to upload keypair {key_name}: {e}")

        # Print essential launch information
        self.print("Launching VM with the following configuration:")
        self.print(f"  Server Name:    {name or f'vm-{self.cloud_name}'}")
        self.print(f"  Image:          {image_name}")
        self.print(f"  Flavor:         {flavor_name}")
        self.print(f"  Key Name:       {key_name}")
        self.print(f"  Security Group: {security_group}")
        self.print(f"  Lease Length:   {lease_duration_td}")

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
                username_fmt = cloud_config.get("username", "user")
                site = (
                    cloud_config.get("site", self.cloud_name)
                    .replace("_", "-")
                    .replace("@", "")
                    .lower()
                )
                vm_name = (
                    f"{vm_name}-{username_fmt}"
                    if site == self.cloud_name
                    else f"{vm_name}-{site}-{username_fmt}"
                )

            res_name = f"res-{vm_name}"

            # Use the high-level chi.lease.Lease pattern from standalone tests
            lease = chi.lease.Lease(res_name, duration=lease_duration_td)

            # We must reserve the specific flavor being requested
            flavor_id = chi.server.get_flavor_id(flavor_name)
            lease.add_flavor_reservation(id=flavor_id, amount=1)
            lease.submit(idempotent=True)

            # Mandated: Ensure the lease exists and is ACTIVE before launching the VM
            self.print(f"Checking/Creating lease for {res_name}...")
            lease.wait(status="active", timeout=300)

            reservation_id = lease.id
            self.print(
                f"Lease {res_name} is active (ID: {reservation_id}). Proceeding to launch VM..."
            )

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
                            self.print(
                                f"  Port not ready yet, retrying in 3s... ({i + 1}/10)"
                            )
                            time.sleep(3)
                        else:
                            self.print(f"Error associating floating IP: {e}")
                            break
                if not fip_addr:
                    self.print(
                        "Timed out waiting for network ports to route Floating IP"
                    )

            s.refresh()

            # 3. OPEN PORT 22 (SSH) AND ICMP (PING) IN SECURITY GROUPS
            self.print("Configuring security groups for SSH and ICMP...")
            sg_name = f"{username}-allow-ssh"
            sg_list = network.list_security_groups(name_filter=sg_name)

            # Find exact match to avoid partial name collisions
            sg = next((g for g in sg_list if getattr(g, "name", None) == sg_name), None)

            if sg:
                self.print(f"✅ Found existing security group: {sg_name}")
                sg_id = sg.id
            else:
                self.print(f"Creating new security group: {sg_name}...")
                new_sg = network.SecurityGroup(
                    {
                        "name": sg_name,
                        "description": f"Enable SSH and ICMP traffic for {username}",
                    }
                )
                new_sg.submit()
                sg_id = new_sg.id

            # Ensure the required rules are present using the raw neutron client to avoid wrapper constraints
            # and handle existing rules gracefully (Neutron returns 409 Conflict if rule exists)
            for rule in [
                {"protocol": "tcp", "port": 22},
                {"protocol": "icmp", "port": None},
            ]:
                try:
                    network.neutron().create_security_group_rule(
                        {
                            "security_group_rule": {
                                "direction": "ingress",
                                "protocol": rule["protocol"],
                                "port_range_min": rule["port"],
                                "port_range_max": rule["port"],
                                "security_group_id": sg_id,
                            }
                        }
                    )
                    self.print(f"✅ Added {rule['protocol']} rule to {sg_name}")
                except Exception as e:
                    if "Conflict" in str(e) or "409" in str(e):
                        self.print(
                            f"  Rule for {rule['protocol']} already exists, skipping..."
                        )
                    else:
                        self.print(
                            f"  Warning: Could not add {rule['protocol']} rule: {e}"
                        )

            self.print(
                f"✅ Security group {sg_name} configured with SSH and ICMP rules"
            )

            # Attach security group to the server instance
            s.add_security_group(sg_id)

            # 4. PRINT SSH CONNECTION DETAILS
            if fip_addr:
                # Clear stale host key for the floating IP to avoid "Host key verification failed"
                # This is common in cloud environments where IPs are recycled.
                try:
                    import subprocess

                    subprocess.run(
                        ["ssh-keygen", "-R", fip_addr], capture_output=True, check=False
                    )
                    self.print(
                        f"✅ Cleared stale host key for {fip_addr} to ensure seamless SSH connection"
                    )
                except Exception as e:
                    self.print(
                        f"  Warning: Could not clear host key for {fip_addr}: {e}"
                    )

                # Use 'cc' for images starting with CC-, otherwise use config username
                ssh_user = (
                    "cc" if image_name and image_name.startswith("CC-") else username
                )
                self.print("\nVM is ready! You can SSH in using:")
                self.print(
                    f"ssh -i {os.path.expanduser(cloud_config.get('key_path', '~/.ssh/id_rsa'))} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {ssh_user}@{fip_addr}"
                )

            return vm_name
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger

            tb = traceback.format_exc()
            logger.error(f"CHI start failed for {self.cloud_name}: {e}\n{tb}")
            raise VMProviderError(
                f"CHI start failed for {self.cloud_name}: {e}\n{tb}"
            ) from e

    def stop(self, name: str | None = None) -> bool:
        """Stops a Chameleon VM."""
        if not name:
            return False
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

    def restart(self, name: str | None = None) -> bool:
        """Restarts a Chameleon VM."""
        if not name:
            return False
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

    def suspend(self, name: str | None = None) -> bool:
        """Suspends a Chameleon VM."""
        if not name:
            return False
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

    def delete(self, name: str | None = None) -> bool:
        """Deletes a Chameleon VM by name, ID, or fallback to single active server."""
        if not name:
            return False

        print(f"Deleting Chameleon VM: {name}")
        self._setup_chi_context()
        try:
            server = None
            servers = chi.server.list_servers()

            # 1. Try direct lookup via get_server
            try:
                server = chi.server.get_server(name)
            except Exception:
                pass

            # 2. Try matching name or ID from the list
            if not server:
                for s in servers:
                    s_name = getattr(s, "name", "")
                    s_id = str(getattr(s, "id", ""))
                    print(f"Checking server: {s_name} ({s_id})")
                    if (
                        s_name == name
                        or s_id == name
                        or name in s_id
                        or s_id.startswith(str(name))
                    ):
                        server = s
                        break

            # 3. Ultimate Fallback: If only ONE server exists in this project/site,
            # assume this is the one the user meant to delete (handles internal UUID mismatch)
            if not server and len(servers) == 1:
                server = servers[0]
                print(
                    f"Notice: '{name}' did not match directly, but exactly one server was found. Targeting: {server.name}"
                )

            if not server:
                from cloudmesh.ai.vm.logger import logger

                logger.warning(f"CHI delete: Server '{name}' not found.")
                return False

            server_id = getattr(server, "id", None)
            server_name = getattr(server, "name", name)

            # 4. Safely release floating IP using the actual server name
            try:
                self.release_floating_ip(server_name)
            except Exception as fip_err:
                from cloudmesh.ai.vm.logger import logger

                logger.info(
                    f"Note: Could not release floating IP for {server_name}: {fip_err}"
                )

            # 5. Delete the server using its reliable ID
            if server_id:
                chi.server.delete_server(server_id)
                print(f"Successfully deleted server: {server_name} ({server_id})")
                return True
            elif hasattr(server, "delete"):
                server.delete()
                print(f"Successfully deleted server object: {server_name}")
                return True

            return False
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger

            logger.error(f"CHI delete failed for {name}: {e}")
            raise VMProviderError(f"CHI delete failed for {name}: {e}") from e

    def _resolve_flavor_name(
        self, flavor_val: Any, flavor_map: dict[str, str] | None = None
    ) -> str:
        """
        Resolves a flavor value (which could be a flavor object, a flavor ID,
        or a 'reservation:UUID' string) to a human-readable flavor name.
        """
        if not flavor_val:
            return "Unknown"

        if hasattr(flavor_val, "name"):
            return flavor_val.name

        if isinstance(flavor_val, str):
            lookup_val = flavor_val
            is_reservation = False
            if flavor_val.startswith("reservation:"):
                lookup_val = flavor_val.split(":", 1)[1]
                is_reservation = True

            try:
                # 1. Try to resolve from the provided map first (efficient)
                if flavor_map and lookup_val in flavor_map:
                    return flavor_map[lookup_val]

                # 2. Try to resolve as a standard flavor (ID or Name) from the cloud
                if not flavor_map:
                    flavors = chi.server.list_flavors()
                    for f in flavors:
                        if (
                            getattr(f, "id", None) == lookup_val
                            or getattr(f, "name", None) == lookup_val
                        ):
                            return f.name

                # 3. Handle Reservations: Resolve UUID to human-readable name
                if is_reservation or (
                    isinstance(lookup_val, str)
                    and len(lookup_val) == 36
                    and lookup_val.count("-") == 4
                ):
                    try:
                        # Try high-level CHI Lease object first
                        lease = chi.lease.Lease(lookup_val)
                        reserved_flavors = lease.get_reserved_flavors()
                        if reserved_flavors and len(reserved_flavors) > 0:
                            return reserved_flavors[0].name

                        # Fallback: Manually fetch reservation details from leases list
                        # (Same logic used in _get_reservation_details)
                        leases = chi.lease.list_leases()
                        for l in leases:
                            res_types = [
                                "flavor_reservations",
                                "node_reservations",
                                "fip_reservations",
                                "network_reservations",
                                "device_reservations",
                            ]
                            for res_type in res_types:
                                reservations = getattr(l, res_type, [])
                                for res in reservations:
                                    r_id = (
                                        res.get("id")
                                        if isinstance(res, dict)
                                        else getattr(res, "id", None)
                                    )
                                    if r_id == lookup_val:
                                        res_props = (
                                            res.get("resource_properties", {})
                                            if isinstance(res, dict)
                                            else getattr(res, "resource_properties", {})
                                        )
                                        if isinstance(res_props, str):
                                            try:
                                                res_props = json.loads(res_props)
                                            except:
                                                res_props = {}
                                        if isinstance(
                                            res_props, dict
                                        ) and res_props.get("name"):
                                            return res_props.get("name")
                    except Exception as e:
                        logger.debug(f"Reservation lookup failed for {lookup_val}: {e}")
            except Exception as e:
                logger.debug(f"Could not resolve flavor {flavor_val}: {e}")

            return flavor_val

        return str(flavor_val)

    def _format_networks(self, addresses: Any) -> str:
        """
        Formats the addresses dictionary into a human-readable string.
        """
        if not addresses or not isinstance(addresses, dict):
            return "Unknown"

        net_strings = []
        for net_name, addr_list in addresses.items():
            if not addr_list:
                continue

            addr_strings = []
            for addr in addr_list:
                if isinstance(addr, dict):
                    ip = addr.get("addr", "Unknown")
                    ip_type = addr.get("OS-EXT-IPS:type", "unknown")
                    addr_strings.append(f"{ip_type}:{ip}")
                else:
                    addr_strings.append(str(addr))

            net_strings.append(f"{net_name} ({', '.join(addr_strings)})")

        return ", ".join(net_strings) if net_strings else "No Networks"

    def ttl_humanize(self, end_date):
        ttl_str = "Unknown"

        try:
            if isinstance(end_date, datetime):
                # Ensure we are comparing UTC to UTC
                # If end_date is naive, assume it is UTC (standard for cloud APIs)
                # If end_date is aware, convert it to UTC
                if end_date.tzinfo is None:
                    # Use timezone.utc from the datetime module
                    end_date = end_date.replace(tzinfo=timezone.utc)
                else:
                    end_date = end_date.astimezone(timezone.utc)

                now = datetime.now(timezone.utc)
                ttl = end_date - now

                if ttl.total_seconds() < 0:
                    ttl_str = "Expired"
                else:
                    # Strip out seconds and microseconds completely
                    total_seconds = int(ttl.total_seconds())
                    truncated_ttl = timedelta(seconds=(total_seconds // 60) * 60)

                    if truncated_ttl.total_seconds() == 0:
                        ttl_str = "Less than a minute"
                    else:
                        # precisedelta stops at minutes, showing hours and minutes cleanly
                        ttl_str = humanize.precisedelta(
                            truncated_ttl, minimum_unit="minutes"
                        )

            # print(ttl_str)
            # Note: Ensure tmp_name is passed as an argument or available as self.tmp_name if used here
            # print("TMP: " + tmp_name)

        except Exception as e:
            print(f"Error calculating TTL: {e}")

        return str(ttl_str)

    def list(self) -> builtins.list[dict[str, Any]]:
        """Lists all Chameleon VMs with their reachable IP addresses and TTL."""
        self._setup_chi_context()
        try:
            servers = chi.server.list_servers()

            # 1. Pre-fetch all leases once to build a lookup map for flavors and end_dates
            # This avoids the "N+1" query problem and repeated authentication messages.
            res_lookup = {}
            ttl_data = {}
            try:
                leases = chi.lease.list_leases()
                for l in leases:
                    ttl_name = l.__dict__["name"].replace("res-", "")

                    try:
                        ttl_str = None
                        end_date = getattr(l, "end_date", None)

                        ttl_str = self.ttl_humanize(end_date)
                        ttl_data[ttl_name] = ttl_str
                    except Exception as e:
                        print(f"Error calculating TTL: {e}")

                    end_date = (
                        getattr(l, "end_date", None)
                        if not isinstance(l, dict)
                        else l.get("end_date")
                    )
                    res_types = [
                        "flavor_reservations",
                        "node_reservations",
                        "fip_reservations",
                        "network_reservations",
                        "device_reservations",
                    ]
                    for res_type in res_types:
                        reservations = getattr(l, res_type, [])
                        for res in reservations:
                            r_id = (
                                res.get("id")
                                if isinstance(res, dict)
                                else getattr(res, "id", None)
                            )
                            if r_id:
                                props = (
                                    res.get("resource_properties", {})
                                    if isinstance(res, dict)
                                    else getattr(res, "resource_properties", {})
                                )
                                if isinstance(props, str):
                                    try:
                                        props = json.loads(props)
                                    except:
                                        props = {}

                                tmp_name = (
                                    props.get("name")
                                    if isinstance(props, dict)
                                    else "Unknown"
                                )

                                res_lookup[r_id] = {
                                    "name": tmp_name,
                                    "end_date": end_date,
                                    "ttl": ttl_data.get(ttl_name, "N/A"),
                                    "vm_name": ttl_name,
                                }
                                # pprint(res_lookup[r_id])
                # pprint(ttl_data)

            except Exception as e:
                logger.debug(f"Could not pre-fetch leases: {e}")

            # 2. Fetch standard flavors for non-reservation VMs
            flavor_map = {}
            try:
                all_flavors = chi.server.list_flavors()
                for f in all_flavors:
                    f_id = getattr(f, "id", None)
                    f_name = getattr(f, "name", None)
                    if f_id:
                        flavor_map[f_id] = f_name
                    if f_name:
                        flavor_map[f_name] = f_name
            except Exception as e:
                logger.debug(f"Could not fetch flavor map: {e}")

            print(f"Found {len(servers)} servers.")
            results = []

            for s in servers:
                # Format IP addresses
                all_ips = []
                addresses = getattr(s, "addresses", None)
                if addresses and isinstance(addresses, dict):
                    for net_name, addr_list in addresses.items():
                        for addr in addr_list:
                            if isinstance(addr, dict):
                                all_ips.append(addr.get("addr", str(addr)))
                            else:
                                all_ips.append(str(addr))
                ip = ", ".join(all_ips) if all_ips else "No IP"

                # Resolve Flavor and TTL
                flavor_val = getattr(s, "flavor", None) or getattr(
                    s, "flavor_name", None
                )
                flavor_name = "Unknown"
                ttl = "N/A"

                if flavor_val:
                    # Handle Reservation IDs (e.g., "reservation:UUID" or just UUID)
                    clean_id = (
                        flavor_val.split(":", 1)[1]
                        if isinstance(flavor_val, str) and ":" in flavor_val
                        else flavor_val
                    )

                    if isinstance(clean_id, str) and clean_id in res_lookup:
                        flavor_name = res_lookup[clean_id]["name"]
                        # Calculate TTL from lease end_date
                        end_date_str = res_lookup[clean_id]["end_date"]
                        if end_date_str:
                            try:
                                end_date = datetime.datetime.fromisoformat(end_date_str)
                                now = (
                                    datetime.datetime.now(datetime.timezone.utc)
                                    if end_date.tzinfo
                                    else datetime.datetime.now()
                                )
                                diff = end_date - now
                                if diff.total_seconds() > 0:
                                    days = diff.days
                                    hours, rem = divmod(diff.seconds, 3600)
                                    minutes, _ = divmod(rem, 60)
                                    ttl = (
                                        f"{days}d {hours}h {minutes}m"
                                        if days > 0
                                        else f"{hours}h {minutes}m"
                                    )
                                else:
                                    ttl = "Expired"
                            except:
                                pass
                    elif isinstance(clean_id, str):
                        flavor_name = flavor_map.get(clean_id, clean_id)
                    elif hasattr(clean_id, "name"):
                        flavor_name = clean_id.name

                results.append(
                    {
                        "name": s.name,
                        "id": s.id,
                        "status": s.status,
                        "ip": ip,
                        "image": getattr(s, "image_name", "Unknown"),
                        "flavor": flavor_name,
                        "networks": self._format_networks(addresses),
                        "ttl": ttl_data[s.name],
                    }
                )

            return results
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger

            logger.warning(f"CHI list failed: {e}")
            return []

    def _get_flavor_info(self, server) -> tuple[str, str, str]:
        """
        Helper to resolve flavor name, RAM, and CPUs.
        For reservation-backed VMs, the flavor string itself is the reservation ID.
        """
        flavor_name = "N/A"
        ram = "N/A"
        vcpus = "N/A"

        try:
            # 1. Resolve flavor reference from server attributes or dict
            flavor_ref = getattr(server, "flavor", None)
            if not flavor_ref and hasattr(server, "get"):
                flavor_ref = server.get("flavor_name")
            if not flavor_ref:
                flavor_ref = getattr(server, "flavor_name", None)

            if isinstance(flavor_ref, dict):
                flavor_name = flavor_ref.get("id") or flavor_ref.get("name", "N/A")
                ram_val = flavor_ref.get("ram")
                if ram_val:
                    ram = f"{ram_val} MB"
                vcpus = flavor_ref.get("vcpus", "N/A")
            else:
                flavor_name = self._resolve_flavor_name(flavor_ref)
                if flavor_name == "Unknown":
                    flavor_id = getattr(server, "flavor_id", None)
                    flavor_name = self._resolve_flavor_name(flavor_id)

            # 2. Query connection flavors using the connection attached to the server object
            conn = getattr(server, "conn", None)
            if conn and flavor_name != "N/A":
                try:
                    for f in conn.compute.flavors():
                        if (
                            getattr(f, "id", None) == flavor_name
                            or getattr(f, "name", None) == flavor_name
                        ):
                            ram_val = getattr(f, "ram", None)
                            if ram_val:
                                ram = f"{ram_val} MB"
                            vcpus = getattr(f, "vcpus", "N/A")
                            break
                except Exception as inner_e:
                    if hasattr(self, "DEBUG"):
                        self.DEBUG(f"Could not query connection flavors: {inner_e}")

        except Exception as e:
            if hasattr(self, "DEBUG"):
                self.DEBUG(f"Could not resolve flavor details: {e}")

        return flavor_name, ram, vcpus

    def _get_basic_info(self, name: str) -> dict[str, Any]:
        """Gets detailed information about a Chameleon VM."""
        try:
            server = chi.server.get_server(name)

            if not server:
                raise VMResourceError(f"VM {name} not found")

            floating_ip = self._get_floating_ip(name)
            key_name = getattr(server, "key_name", None) or (
                server.keypair.name
                if hasattr(server, "keypair") and server.keypair
                else "N/A"
            )

            # Call the helper function to get readable flavor metadata
            flavor_name, ram, vcpus = self._get_flavor_info(server)

            return {
                "Name": server.name,
                "ID": server.id,
                "State": server.status,
                "Created": server.created_at,
                "Image": server.image_name,
                "Flavor": flavor_name,
                "Key": key_name,
                "FloatingIP": floating_ip or "Not Assigned",
                "PublicIPs": server.addresses
                if getattr(server, "addresses", None)
                else {},
                "RAM": ram,
                "CPUs": vcpus,
            }
        except VMResourceError:
            raise
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger

            logger.error(f"Error getting info for VM {name} in {self.cloud_name}: {e}")
            raise VMProviderError(
                f"Error getting info for VM {name} in {self.cloud_name}: {e}"
            ) from e

    def info_old(self, name: str) -> dict[str, Any]:
        """Gets detailed information about a Chameleon VM."""
        self._setup_chi_context()
        try:
            server = chi.server.get_server(name)
            # from pprint import pprint
            # pprint(server.__dict__)

            if not server:
                raise VMResourceError(f"VM {name} not found")

            floating_ip = self._get_floating_ip(name)

            return {
                "Name": server.name,
                "ID": server.id,
                "State": server.status,
                "Created": server.created_at,
                "Image": server.image_name,
                "Key": server.keypair,
                "FloatingIP": floating_ip or "Not Assigned",
                "PublicIPs": server.addresses
                if getattr(server, "addresses", None)
                else [],
                "RAM": getattr(server, "ram", "N/A"),
                "CPUs": getattr(server, "vcpus", "N/A"),
            }
        except VMResourceError:
            raise
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger

            logger.error(f"Error getting info for VM {name} in {self.cloud_name}: {e}")
            raise VMProviderError(
                f"Error getting info for VM {name} in {self.cloud_name}: {e}"
            ) from e

    def login(self, name: str | None = None) -> bool:
        """Provides the SSH connection string for the Chameleon VM."""
        if not name:
            self.print("Error: VM name is required to login.")
            return False

        floating_ip = self._get_floating_ip(name)
        if not floating_ip:
            self.print(
                f"No floating IP found for VM {name}. Use 'cmc vm assign-floating-ip' first."
            )
            return False

        cloud_config = self.get_cloud_config("chameleon")
        key_path = cloud_config.get("key_path", "~/.ssh/id_rsa")

        # Use 'cc' for images starting with CC-, otherwise use config username
        # Note: This requires fetching the server to check the image name
        try:
            server = chi.server.get_server(name)
            image_name = getattr(server, "image_name", None)
            username = cloud_config.get("username", "ubuntu")
            user = "cc" if image_name and image_name.startswith("CC-") else username
        except Exception:
            user = cloud_config.get("username", "ubuntu")

        self.print(
            f"Connect to your VM using:\nssh -i {key_path} -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null {user}@{floating_ip}"
        )
        return True

    def _get_floating_ip(self, name: str) -> str | None:
        """Internal helper to retrieve the floating IP address of a VM."""
        self._setup_chi_context()
        try:
            server = chi.server.get_server(name)
            if not server:
                return None
            addresses = getattr(server, "addresses", {})
            if not addresses:
                return None
            for net_name, addr_list in addresses.items():
                for addr in addr_list:
                    if (
                        isinstance(addr, dict)
                        and addr.get("OS-EXT-IPS:type") == "floating"
                    ):
                        return addr.get("addr")
                    elif isinstance(addr, str) and addr.startswith(
                        "129."
                    ):  # Heuristic for Chameleon FIPs
                        return addr
            return None
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger

            logger.debug(f"Error getting floating IP for VM {name}: {e}")
            return None

    def _resolve_sg_id(self, sg_name: str) -> str:
        """
        Resolves a security group name to an ID.
        If multiple groups with the same name exist, returns the first one's ID.
        """
        self._setup_chi_context()
        try:
            # Try the standard resolver first
            sg = chi.network._resolve_resource("security_group", sg_name)
            if isinstance(sg, dict):
                return sg["id"]
            return getattr(sg, "id", sg_name)
        except Exception:
            # Fallback: manually list and find the first match
            groups = chi.network.list_security_groups()
            for g in groups:
                if g["name"] == sg_name:
                    return g["id"]

        # If it's already a UUID, return it as is
        if len(sg_name) == 36 and sg_name.count("-") == 4:
            return sg_name

        raise VMResourceError(f"Could not resolve security group {sg_name} to an ID")

    def assign_floating_ip(self, name: str) -> str | None:
        """Assigns an available floating IP to the VM with retries for network routing."""
        self._setup_chi_context()
        try:
            server = chi.server.get_server(name)
            if not server:
                return None

            for i in range(10):
                try:
                    return server.associate_floating_ip()
                except chi.exception.ResourceError as e:
                    if "None of the ports can route" in str(e) and i < 9:
                        self.print(
                            f"  Port not ready yet, retrying in 3s... ({i + 1}/10)"
                        )
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
        except chi.exception.ResourceError as e:
            if "404" in str(e) or "not found" in str(e).lower():
                return False
            from cloudmesh.ai.vm.logger import logger

            logger.error(f"CHI release_floating_ip failed for {name}: {e}")
            return False
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger

            logger.error(f"CHI release_floating_ip failed for {name}: {e}")
            return False

    def list_regions(self) -> builtins.list[dict[str, Any]]:
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

    def create_reservation(
        self,
        name: str,
        node_type: str,
        count: int,
        start_date: str = None,
        end_date: str = None,
        duration: int = None,
    ) -> str | None:
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
            return (
                lease.get("id")
                if isinstance(lease, dict)
                else getattr(lease, "id", None)
            )
        except Exception as e:
            self.print(f"Error creating reservation in Chameleon: {e}")
            return None

    def get_account_info(self) -> dict[str, Any]:
        """Returns account information for Chameleon using chi."""
        self._setup_chi_context()
        try:
            return {
                "site": chi.get("site"),
                "project_name": chi.get("project_name"),
                "project_id": chi.get("project_id"),
                "user_id": chi.get("user_id"),
                "allocation": chi.get("allocation")
                if hasattr(chi, "get")
                else "Unknown",
            }
        except Exception as e:
            self.print(f"Error fetching Chameleon account info: {e}")
            return {"error": f"Failed to fetch Chameleon account info: {e!s}"}

    def get_images(self, **kwargs) -> builtins.list[dict[str, Any]]:
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

    def get_flavors(self, **kwargs) -> builtins.list[dict[str, Any]]:
        """Lists available flavors in Chameleon Cloud."""
        self._setup_chi_context()
        try:
            flavors = chi.server.list_flavors()
            return [
                {"id": f.id, "name": f.name, "ram": f.ram, "vcpus": f.vcpus}
                for f in flavors
            ]
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger

            logger.error(f"CHI get_flavors failed: {e}")
            return []

    def get_keys(self) -> builtins.list[dict[str, Any]]:
        """Lists available keys in Chameleon Cloud."""
        self._setup_chi_context()
        try:
            import base64
            import hashlib

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

    def upload_key(
        self, key_path: str, key_name: str, vm_name: str | None = None
    ) -> bool:
        """Uploads a public key to Chameleon Cloud."""
        self._setup_chi_context()
        try:
            key_path = os.path.expanduser(key_path)
            with open(key_path, "r") as f:
                public_key = f.read()
            chi.server.update_keypair(key_name, public_key)
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger

            logger.error(f"CHI upload_key failed for {key_name}: {e}")
            return False

    def delete_key(self, key_name: str, vm_name: str | None = None) -> bool:
        """Deletes a public key from Chameleon Cloud."""
        self._setup_chi_context()
        try:
            chi.server.nova().keypairs.delete(key_name)
            return True
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger

            logger.error(f"CHI delete_key failed for {key_name}: {e}")
            return False

    def get_security_groups(self) -> builtins.list[dict[str, Any]]:
        """Lists available security groups in Chameleon Cloud."""
        self._setup_chi_context()
        try:
            groups = chi.network.list_security_groups()
            return [{"name": g.name, "description": g.description} for g in groups]
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger

            logger.error(f"CHI get_security_groups failed: {e}")
            return []

    def get_security_group_info(self, name: str) -> dict[str, Any]:
        """Gets detailed information for a specific security group."""
        self._setup_chi_context()
        try:
            return chi.network._resolve_resource("security_group", name)
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger

            logger.error(f"CHI get_security_group_info failed for {name}: {e}")
            raise VMProviderError(
                f"Could not get security group info for {name} in {self.cloud_name}: {e}"
            ) from e

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
            chi.network.neutron().delete_security_group(sg["id"])
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
            if not server:
                return False

            # Resolve SG name to ID to avoid ambiguity
            sg = chi.network._resolve_resource("security_group", sg_name)
            sg_id = sg["id"] if isinstance(sg, dict) else getattr(sg, "id", sg_name)

            server.add_security_group(sg_id)
            return True
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

    def add_security_group_rule(
        self,
        sg_name: str,
        protocol: str,
        port: str,
        cidr: str,
        direction: str = "ingress",
    ) -> str:
        """Adds a security group rule. Returns the rule ID."""
        self._setup_chi_context()
        try:
            # Resolve SG name to ID
            sg = chi.network._resolve_resource("security_group", sg_name)
            sg_id = sg["id"]

            rule = chi.network.neutron().create_security_group_rule(
                security_group_id=sg_id,
                direction=direction,
                protocol=protocol,
                port_range_min=port,
                port_range_max=port,
                remote_ip_prefix=cidr,
            )
            return rule.id
        except Exception as e:
            from cloudmesh.ai.vm.logger import logger

            logger.error(f"CHI add_security_group_rule failed for {sg_name}: {e}")
            raise VMProviderError(
                f"Could not add security group rule for {sg_name} in {self.cloud_name}: {e}"
            ) from e

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

    def list_security_group_rules(self, sg_name: str) -> builtins.list[dict[str, Any]]:
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

# Export a compatibility alias for matrix tests that import ``ChameleonManager``
# directly. The entry point still references ``Provider``, but the test suite
# expects a class named ``ChameleonManager``.
ChameleonManager = Provider
