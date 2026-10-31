from typing import Any

from cloudmesh.ai.vm.LibcloudManager import LibcloudManager

try:
    from libcloud.compute.providers.gce import GCEDriver
except ImportError:

    class GCEDriver:
        def __init__(self, *args, **kwargs):
            pass


class Provider(LibcloudManager):
    """
    Google Compute Engine implementation of the LibcloudManager.
    """

    def __init__(self, config, **kwargs):
        super().__init__(config, cloud_name="google", **kwargs)

    def _get_driver(self):
        cloud_config = self.get_cloud_config("google")
        return GCEDriver(
            project_id=cloud_config.get("project_id"),
            private_key=cloud_config.get("private_key"),
        )

    def assign_floating_ip(self, name: str) -> str | None:
        """
        Assigns a floating (static external) IP to the Google VM.
        """
        try:
            node = self.driver.get_node(name)
            if not node:
                raise VMResourceError(f"VM {name} not found in Google")

            cloud_config = self.get_cloud_config(self.cloud_name)
            region = cloud_config.get("region", "us-central1")

            # Reserve a static external IP
            address = self.driver.ex_create_address(name=f"ip-{name}", region=region)
            # Assign the static IP to the node
            # nic is typically 'nic0' for the primary interface
            self.driver.ex_add_access_config(
                node=node, name="external-nat", nic="nic0", nat_ip=address
            )

            return address
        except Exception as e:
            logger.error(f"Error assigning floating IP to {name} in Google: {e}")
            raise VMProviderError(f"Failed to assign floating IP to {name}: {e}")

    def release_floating_ip(self, name: str) -> bool:
        """
        Releases the floating (static external) IP from the Google VM.
        """
        try:
            node = self.driver.get_node(name)
            if not node:
                raise VMResourceError(f"VM {name} not found in Google")

            public_ips = getattr(node, "public_ips", [])
            if not public_ips:
                logger.warning(f"No public IP found to release for VM {name}")
                return False

            address = public_ips[0]
            # Disassociate first
            self.driver.ex_delete_access_config(
                node=node, name="external-nat", nic="nic0"
            )
            # Release the address
            self.driver.ex_destroy_address(address=address)
            return True
        except Exception as e:
            logger.error(f"Error releasing floating IP from {name} in Google: {e}")
            raise VMProviderError(f"Failed to release floating IP from {name}: {e}")

    def get_provider_info(self) -> dict[str, Any]:
        """Gets detailed information about the Google provider."""
        import subprocess

        version = "Unknown"
        try:
            result = subprocess.run(
                ["gcloud", "--version"], capture_output=True, text=True
            )
            if result.returncode == 0:
                # gcloud --version returns multiple lines, take the first one
                version = result.stdout.splitlines()[0].strip()
        except Exception:
            pass

        cloud_config = self.get_cloud_config(self.cloud_name)
        return {
            "provider": "Google",
            "cloud_name": self.cloud_name,
            "version": version,
            "config": {
                "project_id": cloud_config.get("project_id"),
            },
        }

    def restart(self, name: str | None = None) -> bool:
        """Restarts a Google VM using the native reboot command."""
        if not name:
            return False
        try:
            node = self.driver.get_node(name)
            if not node:
                return False
            if hasattr(node, "reboot"):
                node.reboot()
                return True
            if hasattr(self.driver, "reboot_node"):
                self.driver.reboot_node(node)
                return True
            raise ProviderFeatureNotSupported(self.cloud_name, "restart")
        except Exception as e:
            if isinstance(e, ProviderFeatureNotSupported):
                raise e
            logger.error(f"Error restarting Google VM {name}: {e}")
            return False

    def suspend(self, name: str | None = None) -> bool:
        """
        Suspends a Google VM. Tries native suspend first;
        falls back to stop to ensure compute resources are released.
        """
        if not name:
            return False
        try:
            node = self.driver.get_node(name)
            if not node:
                return False
            if hasattr(node, "suspend"):
                node.suspend()
                return True

            logger.info(
                f"Native suspend not supported for {name}. Falling back to stop..."
            )
            return self.stop(name)
        except Exception as e:
            logger.error(f"Error suspending Google VM {name}: {e}")
            return False

    def reset(self, name: str | None = None) -> bool:
        """
        Resets a Google VM. Performs a hard power cycle (stop -> start)
        if the native restart fails.
        """
        if not name:
            return False
        try:
            # 1. Try the soft restart first
            if self.restart(name):
                return True

            # 2. Fallback: Hard Power Cycle
            logger.info(
                f"Native restart failed for {name}. Performing hard reset (stop -> start)..."
            )
            if self.stop(name):
                return self.start(name=name)
            return False
        except Exception as e:
            logger.error(f"Error resetting Google VM {name}: {e}")
            return False

# Compatibility alias for matrix tests and historic imports.
GoogleManager = Provider
