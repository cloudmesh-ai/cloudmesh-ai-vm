import subprocess
from typing import Any

from cloudmesh.ai.vm.LibcloudManager import LibcloudManager
from cloudmesh.ai.vm.exceptions import ProviderFeatureNotSupported

try:
    from libcloud.compute.providers.amazon import AmazonEC2Driver
except ImportError:

    class AmazonEC2Driver:
        def __init__(self, *args, **kwargs):
            pass


class Provider(LibcloudManager):
    """
    AWS EC2 implementation of the LibcloudManager.
    """

    def __init__(self, config, **kwargs):
        super().__init__(config, cloud_name="aws", **kwargs)

    def _get_driver(self):
        cloud_config = self.get_cloud_config("aws")
        return AmazonEC2Driver(
            access_key=cloud_config.get("access_key"),
            secret_key=cloud_config.get("secret_key"),
            region=cloud_config.get("region", "us-east-1"),
        )

    def _find_node(self, identifier: str):
        """Helper to find a node by name or ID since some driver versions lack get_node."""
        try:
            if hasattr(self.driver, "get_node"):
                node = self.driver.get_node(identifier)
                if node:
                    return node
        except Exception:
            pass

        nodes = self.driver.list_nodes()
        return next(
            (n for n in nodes if n.name == identifier or n.id == identifier), None
        )

    def assign_floating_ip(self, name: str) -> str | None:
        """
        Assigns a floating (Elastic) IP to the AWS VM.
        """
        try:
            node = self.driver.get_node(name)
            if not node:
                raise VMResourceError(f"VM {name} not found in AWS")

            cloud_config = self.get_cloud_config(self.cloud_name)
            domain = cloud_config.get("region", "us-east-1")

            # Allocate a new Elastic IP
            address = self.driver.ex_allocate_address(domain=domain)
            # Associate the Elastic IP with the node
            self.driver.ex_associate_address_with_node(
                node=node, elastic_ip=address, domain=domain
            )

            return address
        except Exception as e:
            logger.error(f"Error assigning floating IP to {name} in AWS: {e}")
            raise VMProviderError(f"Failed to assign floating IP to {name}: {e}")

    def release_floating_ip(self, name: str) -> bool:
        """
        Releases the floating (Elastic) IP from the AWS VM.
        """
        try:
            node = self.driver.get_node(name)
            if not node:
                raise VMResourceError(f"VM {name} not found in AWS")

            public_ips = getattr(node, "public_ips", [])
            if not public_ips:
                logger.warning(f"No public IP found to release for VM {name}")
                return False

            address = public_ips[0]
            cloud_config = self.get_cloud_config(self.cloud_name)
            domain = cloud_config.get("region", "us-east-1")

            # Disassociate the address
            self.driver.ex_disassociate_address(elastic_ip=address, domain=domain)
            # Release the address
            self.driver.ex_release_address(elastic_ip=address, domain=domain)
            return True
        except Exception as e:
            logger.error(f"Error releasing floating IP from {name} in AWS: {e}")
            raise VMProviderError(f"Failed to release floating IP from {name}: {e}")

    def restart(self, name: str | None = None) -> bool:
        """Restarts an AWS VM using the native reboot command."""
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
            logger.error(f"Error restarting AWS VM {name}: {e}")
            return False

    def suspend(self, name: str | None = None) -> bool:
        """
        Suspends an AWS VM. In EC2, this is mapped to 'stop' to release
        compute resources and stop billing.
        """
        if not name:
            return False
        try:
            return self.stop(name)
        except Exception as e:
            logger.error(f"Error suspending AWS VM {name}: {e}")
            return False

    def reset(self, name: str | None = None) -> bool:
        """
        Resets an AWS VM. Performs a hard power cycle (stop -> start)
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
            logger.error(f"Error resetting AWS VM {name}: {e}")
            return False

    def get_provider_info(self) -> dict[str, Any]:
        """Gets detailed information about the AWS provider."""

        version = "Unknown"
        try:
            result = subprocess.run(
                ["aws", "--version"], capture_output=True, text=True
            )
            if result.returncode == 0:
                version = result.stdout.strip()
        except Exception:
            pass

        cloud_config = self.get_cloud_config(self.cloud_name)
        region = cloud_config.get("region", "us-east-1")

        account_id = "Unknown"
        try:
            result = subprocess.run(
                [
                    "aws",
                    "sts",
                    "get-caller-identity",
                    "--query",
                    "Account",
                    "--output",
                    "text",
                ],
                capture_output=True,
                text=True,
            )
            if result.returncode == 0:
                account_id = result.stdout.strip()
        except Exception:
            pass

        return {
            "provider": "AWS",
            "cloud_name": self.cloud_name,
            "version": version,
            "config": {
                "region": region,
                "account_id": account_id,
            },
        }

# Compatibility alias for matrix tests and historic imports.
AwsManager = Provider
