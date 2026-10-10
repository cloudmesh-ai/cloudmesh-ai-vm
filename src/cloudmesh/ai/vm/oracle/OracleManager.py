from typing import List, Dict, Any, Optional
import os
import subprocess
from cloudmesh.ai.vm.CloudBaseManager import CloudBaseManager
from cloudmesh.ai.vm.exceptions import ConfigError, VMResourceError, VMAuthError, VMNetworkError, VMProviderError, ProviderFeatureNotSupported
from cloudmesh.ai.vm.logger import logger

try:
    import oci
except ImportError:
    oci = None

class Provider(CloudBaseManager):
    """
    Oracle Cloud Infrastructure (OCI) implementation of the VM Manager.
    Uses the OCI Python SDK.
    """

    def __init__(self, config, **kwargs):
        super().__init__(config, **kwargs)
        self.cloud_name = "oracle"
        self._init_oci_client()

    def _init_oci_client(self):
        """Initializes OCI clients using configuration from clouds.yaml."""
        if oci is None:
            logger.error("OCI SDK not installed. Please install it using 'pip install oci'.")
            return

        cloud_config = self.get_cloud_config(self.cloud_name)

        # OCI expects a config dictionary or a path to a config file
        # We build a config dictionary compatible with oci.config.from_dict
        oci_config = {
            "user": cloud_config.get("user"),
            "key_file": os.path.expanduser(cloud_config.get("key_file", "~/.oci/oci_api_key.pem")),
            "fingerprint": cloud_config.get("fingerprint"),
            "tenancy": cloud_config.get("tenancy"),
            "region": cloud_config.get("region"),
        }

        if not all([oci_config["user"], oci_config["tenancy"], oci_config["fingerprint"], oci_config["region"]]):
            logger.warning(f"OCI configuration for {self.cloud_name} is incomplete.")

        try:
            self.config = oci.config.from_dict(oci_config)
            self.compute_client = oci.core.ComputeClient(self.config)
            self.network_client = oci.core.VirtualNetworkClient(self.config)
            logger.debug(f"OCI client initialized for {self.cloud_name}")
        except Exception as e:
            logger.error(f"Failed to initialize OCI client: {e}")
            self.compute_client = None

    def start(self, name: Optional[str] = None, flavor: Optional[str] = None, image: Optional[str] = None, **kwargs) -> str:
        """
        Launches a VM in Oracle Cloud.
        """
        if not self.compute_client:
            raise VMProviderError("OCI client not initialized")

        cloud_config = self.get_cloud_config(self.cloud_name)
        image_id = image or cloud_config.get("image")
        shape = flavor or cloud_config.get("flavor") or cloud_config.get("size")
        subnet_id = cloud_config.get("subnet_id")
        compartment_id = cloud_config.get("compartment_id")

        if not all([image_id, shape, subnet_id, compartment_id]):
            raise ConfigError(f"Missing required OCI config: image, flavor/size, subnet_id, or compartment_id")

        vm_name = name or f"vm-{self.cloud_name}"

        try:
            launch_details = oci.core.models.LaunchInstanceDetails(
                compartment_id=compartment_id,
                availability_domain=cloud_config.get("availability_domain"),
                shape=shape,
                display_name=vm_name,
                image_id=image_id,
                create_vnic_details=oci.core.models.CreateVnicDetails(
                    subnet_id=subnet_id,
                    assign_public_ip=True
                )
            )

            instance = self.compute_client.launch_instance(launch_details)
            logger.info(f"Successfully started Oracle VM {vm_name} (ID: {instance.data.id})")
            return instance.data.id
        except Exception as e:
            logger.error(f"OCI launch failed for {self.cloud_name}: {e}")
            raise VMProviderError(f"OCI launch failed for {self.cloud_name}: {e}") from e

    def exists(self, name: str) -> bool:
        """
        Checks if an Oracle VM exists.
        """
        try:
            self._resolve_instance_id(name)
            return True
        except Exception:
            return False

    def stop(self, name: Optional[str] = None) -> bool:
        """Stops an Oracle VM."""
        if not name:
            return False
        if not self.compute_client:
            return False
        try:
            instance_id = self._resolve_instance_id(name)
            self.compute_client.instance_action(instance_id, "STOP")
            return True
        except Exception as e:
            logger.error(f"OCI stop failed for {name}: {e}")
            raise VMProviderError(f"OCI stop failed for {name}: {e}") from e

    def delete(self, name: Optional[str] = None) -> bool:
        """Deletes an Oracle VM."""
        if not name:
            return False
        if not self.compute_client:
            return False
        try:
            instance_id = self._resolve_instance_id(name)
            self.compute_client.terminate_instance(instance_id)
            return True
        except Exception as e:
            logger.error(f"OCI delete failed for {name}: {e}")
            raise VMProviderError(f"OCI delete failed for {name}: {e}") from e

    def restart(self, name: Optional[str] = None) -> bool:
        """Restarts an Oracle VM."""
        if not name:
            return False
        if not self.compute_client:
            return False
        try:
            instance_id = self._resolve_instance_id(name)
            self.compute_client.instance_action(instance_id, "SOFTRESET")
            return True
        except Exception as e:
            logger.error(f"OCI restart failed for {name}: {e}")
            return False

    def reset(self, name: Optional[str] = None) -> bool:
        """Resets an Oracle VM (Hard Reset)."""
        if not name:
            return False
        if not self.compute_client:
            return False
        try:
            instance_id = self._resolve_instance_id(name)
            self.compute_client.instance_action(instance_id, "RESET")
            return True
        except Exception as e:
            logger.error(f"OCI reset failed for {name}: {e}")
            return False

    def suspend(self, name: Optional[str] = None) -> bool:
        """Suspends an Oracle VM."""
        if not name:
            return False
        if not self.compute_client:
            return False
        try:
            instance_id = self._resolve_instance_id(name)
            # OCI doesn't have a direct 'suspend' equivalent in the same way as local,
            # but we use STOP as a closest approximation or raise unsupported.
            self.compute_client.instance_action(instance_id, "STOP")
            return True
        except Exception as e:
            logger.error(f"OCI suspend failed for {name}: {e}")
            return False

    def list(self) -> List[Dict[str, Any]]:
        """Lists all Oracle VMs."""
        if not self.compute_client:
            return []
        try:
            compartment_id = self.get_cloud_config(self.cloud_name).get("compartment_id")
            instances = self.compute_client.list_instances(compartment_id).data

            results = []
            for inst in instances:
                # Get public IP
                vnic_attachments = self.compute_client.list_vnic_attachments(
                    compartment_id=compartment_id,
                    instance_id=inst.id
                ).data
                public_ip = "N/A"
                if vnic_attachments:
                    vnic = self.network_client.get_vnic(vnic_attachments[0].vnic_id).data
                    public_ip = vnic.public_ip

                results.append({
                    "name": inst.display_name,
                    "ip": public_ip,
                    "status": inst.lifecycle_state
                })
            return results
        except Exception as e:
            logger.error(f"OCI list failed: {e}")
            return []

    def info(self, name: str) -> Dict[str, Any]:
        """Gets detailed info for an Oracle VM."""
        if not self.exists(name):
            raise VMResourceError(f"Oracle VM {name} not found")
        if not self.compute_client:
            raise VMProviderError("OCI client not initialized")
        try:
            instance_id = self._resolve_instance_id(name)
            inst = self.compute_client.get_instance(instance_id).data
            return {
                "Name": inst.display_name,
                "ID": inst.id,
                "Status": inst.lifecycle_state,
                "Shape": inst.shape,
                "TimeCreated": inst.time_created
            }
        except Exception as e:
            logger.error(f"OCI info failed for {name}: {e}")
            raise VMProviderError(f"OCI info failed for {name}: {e}") from e

    def run_command(self, name: str, cmd: str) -> str:
        """Executes command via SSH."""
        try:
            instance_id = self._resolve_instance_id(name)
            vnic_attachments = self.compute_client.list_vnic_attachments(
                compartment_id=self.get_cloud_config(self.cloud_name).get("compartment_id"),
                instance_id=instance_id
            ).data
            if not vnic_attachments:
                return "Error: No VNIC found for instance."
            vnic = self.network_client.get_vnic(vnic_attachments[0].vnic_id).data
            public_ip = vnic.public_ip
            if not public_ip:
                return "Error: No public IP found for instance."

            cloud_config = self.get_cloud_config(self.cloud_name)
            key_path = os.path.expanduser(cloud_config.get("key_file", "~/.ssh/id_rsa"))
            user = cloud_config.get("user", "opc")

            return self._execute_ssh_command(public_ip, user, key_path, cmd)
        except Exception as e:
            return f"OCI SSH Error: {e}"

    def _resolve_instance_id(self, name: str) -> str:
        """Helper to resolve a display name to an OCID."""
        if name.startswith("ocid1.instance"):
            return name

        compartment_id = self.get_cloud_config(self.cloud_name).get("compartment_id")
        instances = self.compute_client.list_instances(compartment_id).data
        for inst in instances:
            if inst.display_name == name:
                return inst.id
        raise VMResourceError(f"Could not find Oracle instance with name {name}")

    def validate_config(self) -> Dict[str, List[str]]:
        errors_map = {}
        config = self.get_cloud_config(self.cloud_name)
        errors = []

        required = ["user", "tenancy", "fingerprint", "region", "key_file", "compartment_id", "subnet_id"]
        for field in required:
            if not config.get(field):
                errors.append(f"Missing required field: '{field}'")

        if errors:
            errors_map["Oracle Cloud Config"] = errors
        return errors_map

    def upload_key(self, key_path: str, key_name: str) -> bool:
        """
        Uploads a public key to the Oracle Cloud Infrastructure.
        """
        try:
            import oci
            if not self.compute_client:
                return False

            with open(os.path.expanduser(key_path), 'r') as f:
                public_key = f.read()

            identity_client = oci.identity.IdentityClient(self.config)
            identity_client.upload_public_key(
                user_id=self.config["user"],
                key_body=public_key,
                key_name=key_name
            )
            return True
        except Exception as e:
            logger.error(f"OCI upload_key failed for {key_name}: {e}")
            return False

    def delete_key(self, key_name: str) -> bool:
        """
        Deletes a public key from Oracle Cloud Infrastructure.
        """
        try:
            import oci
            if not self.compute_client:
                return False

            identity_client = oci.identity.IdentityClient(self.config)
            # Finding the key OCID first
            keys = identity_client.list_public_keys(self.config["user"]).data
            key_id = next((k.id for k in keys if k.name == key_name), None)

            if not key_id:
                return False

            identity_client.delete_public_key(key_id)
            return True
        except Exception as e:
            logger.error(f"OCI delete_key failed for {key_name}: {e}")
            return False

    def list_regions(self) -> List[Dict[str, Any]]:
        """
        Lists available regions for Oracle Cloud.
        """
        if not self.compute_client:
            return []
        try:
            # Use the OCI identity client to list regions
            import oci
            identity_client = oci.identity.IdentityClient(self.config)
            regions = identity_client.list_regions().data
            return [{"name": r.region_name, "id": r.region_name} for r in regions]
        except Exception as e:
            logger.error(f"OCI list_regions failed: {e}")
            return []

    def get_provider_info(self) -> Dict[str, Any]:
        """Gets detailed information about the Oracle provider."""
        import subprocess

        version = "OCI SDK"
        try:
            result = subprocess.run(["oci", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                version = result.stdout.strip()
        except Exception:
            pass

        cloud_config = self.get_cloud_config(self.cloud_name)
        return {
            "provider": "Oracle",
            "cloud_name": self.cloud_name,
            "version": version,
            "config": {
                "tenancy": cloud_config.get("tenancy"),
                "region": cloud_config.get("region"),
            },
        }

