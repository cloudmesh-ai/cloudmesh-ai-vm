import logging
logger = logging.getLogger("cloudmesh.ai.vm")

import subprocess
from types import SimpleNamespace
from typing import Any

from cloudmesh.ai.vm.LibcloudManager import LibcloudManager
from cloudmesh.ai.vm.exceptions import ProviderFeatureNotSupported

from libcloud.compute.providers import get_driver
from libcloud.compute.types import Provider as LibcloudProvider

class Provider(LibcloudManager):
    """
    AWS EC2 implementation of the LibcloudManager.
    """

    def __init__(self, config, **kwargs):
        super().__init__(config, cloud_name="aws", **kwargs)

    def _get_driver(self):
        cloud_config = self.get_cloud_config("aws")
        driver_class = get_driver(LibcloudProvider.EC2)
        return driver_class(
            key=cloud_config.get("access_key"),
            secret=cloud_config.get("secret_key"),
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

    def start(
        self,
        name: str | None = None,
        flavor: str | None = None,
        image: str | None = None,
        size: str | None = None,
        **kwargs,
    ) -> str:
        """Create and start an AWS EC2 instance."""
        cloud_config = self.get_cloud_config("aws")
        vm_name = name or "vm-aws"
        instance_type = (
            flavor or size or cloud_config.get("flavor")
            or cloud_config.get("size")
        )
        image_id = image or cloud_config.get("image")

        if not image_id:
            raise ValueError("Missing 'image' in AWS configuration")
        if not instance_type:
            raise ValueError("Missing 'flavor' or 'size' in AWS configuration")

        if not image_id.startswith("ami-"):
            raise ValueError("AWS image must be an AMI ID")
        if self._find_node(vm_name) is not None:
            raise ValueError(f"AWS instance {vm_name} already exists")
        images = self.driver.list_images(
            ex_image_ids=[image_id]
        )
        selected_image = next(
            (item for item in images if item.id == image_id),
            None,
        )
        if selected_image is None:
            raise ValueError(f"AMI {image_id} not found")
        sizes = self.driver.list_sizes()
        selected_size = next(
            (
                item for item in sizes
                if item.id == instance_type
                or item.name == instance_type
            ),
            None,
        )
        if selected_size is None:
            raise ValueError(
                f"EC2 instance type {instance_type} not found"
            )

        create_kwargs = {}
        key_name = kwargs.get("key_name", cloud_config.get("key_name"))
        if key_name:
            create_kwargs["ex_keyname"] = key_name
        security_group_ids = kwargs.get(
            "security_group_ids",
            cloud_config.get("security_group_ids"),
        )
        if security_group_ids:
            if (
                not isinstance(security_group_ids, list)
                or not all(
                    isinstance(group, str) and group
                    for group in security_group_ids
                )
            ):
                raise ValueError("security_group_ids must be a list of IDs")
            create_kwargs["ex_security_group_ids"] = security_group_ids
        subnet_id = kwargs.get("subnet_id", cloud_config.get("subnet_id"))
        if subnet_id:
            subnets = self.driver.ex_list_subnets(subnet_ids=[subnet_id])
            selected_subnet = next(
                (subnet for subnet in subnets if subnet.id == subnet_id),
                None,
            )
            if selected_subnet is None:
                raise ValueError(f"Subnet {subnet_id} not found")
            create_kwargs["ex_subnet"] = selected_subnet
        assign_public_ip = kwargs.get(
            "assign_public_ip", cloud_config.get("assign_public_ip", False)
        )
        if not isinstance(assign_public_ip, bool):
            raise ValueError("assign_public_ip must be a boolean")
        create_kwargs["ex_assign_public_ip"] = assign_public_ip
        node = self.driver.create_node(
            name=vm_name,
            image=selected_image,
            size=selected_size,
            **create_kwargs,
        )
        logger.info("Created AWS EC2 instance %s (ID: %s)", vm_name, node.id)
        return node.id


    def exists(self, name: str) -> bool:
        """Check whether an AWS EC2 instance exists by name or ID."""
        if not name:
            return False
        try:
            return self._find_node(name) is not None
        except Exception:
            return False

    def info(self, name: str | None = None, kind: str = "vm") -> dict[str, Any]:
        """Return information about an EC2 instance by name or ID."""
        if not name:
            return {"error": "VM name or instance ID is required"}
        try:
            node = self._find_node(name)
            if node is None:
                return {"error": f"VM {name} not found in AWS"}
            return {
                "ID": node.id,
                "Name": node.name,
                "IP": node.public_ips[0] if node.public_ips else "N/A",
                "Status": node.state,
                "RAM": getattr(node, "ram", "N/A"),
                "CPUs": getattr(node, "cpus", "N/A"),
            }
        except Exception as e:
            return {"error": str(e)}

    def stop(self, name: str | None = None) -> bool:
        """Request that an existing AWS EC2 instance stop."""
        if not name:
            return False
        try:
            node = self._find_node(name)
            if node is None:
                return False
            return bool(self.driver.stop_node(node))
        except Exception as e:
            logger.error("Error stopping AWS VM %s: %s", name, e)
            return False

    def delete(self, name: str | None = None) -> bool:
        """Request termination of an existing AWS EC2 instance."""
        if not name:
            return False
        try:
            node = self._find_node(name)
            if node is None:
                return False
            return bool(self.driver.destroy_node(node))
        except Exception as e:
            logger.error("Error deleting AWS VM %s: %s", name, e)
            return False





    @staticmethod
    def _elastic_ip_resource(address):
        """Build a Libcloud-compatible reference to an EIP allocation."""
        allocation_id = address.extra.get("allocation_id")
        if not allocation_id:
            raise ValueError("Elastic IP is missing its allocation ID")
        return SimpleNamespace(id=allocation_id)

    def _is_managed_elastic_ip(self, address) -> bool:
        """Check whether an Elastic IP carries this provider's ownership tags."""
        resource = self._elastic_ip_resource(address)
        tags = self.driver.ex_describe_tags(resource)
        return (
            tags.get("cloudmesh-ai-vm:managed") == "true"
            and tags.get("cloudmesh-ai-vm:resource") == "elastic-ip"
        )

    def _tag_elastic_ip(self, address) -> bool:
        """Mark an Elastic IP allocation as managed by this provider."""
        resource = self._elastic_ip_resource(address)
        return bool(
            self.driver.ex_create_tags(
                resource,
                {
                    "cloudmesh-ai-vm:managed": "true",
                    "cloudmesh-ai-vm:resource": "elastic-ip",
                },
            )
        )

    def assign_floating_ip(self, name: str) -> str | None:
        """Allocate and associate a VPC Elastic IP with an EC2 instance."""
        node = self._find_node(name)
        if node is None:
            raise ValueError(f"VM {name} not found in AWS")

        existing = self.driver.ex_describe_all_addresses(
            only_associated=True
        )
        for address in existing:
            if address.instance_id == node.id and address.domain == "vpc":
                if not self._is_managed_elastic_ip(address):
                    raise RuntimeError(
                        f"Elastic IP {address.ip} is not managed by "
                        "cloudmesh-ai-vm"
                    )
                return address.ip

        address = self.driver.ex_allocate_address(domain="vpc")

        try:
            if not self._tag_elastic_ip(address):
                raise RuntimeError(
                    f"Failed to tag Elastic IP {address.ip} for ownership"
                )

            association_id = self.driver.ex_associate_address_with_node(
                node=node,
                elastic_ip=address,
                domain="vpc",
            )
            if not association_id:
                raise RuntimeError(
                    "AWS did not return an Elastic IP association ID"
                )
            return address.ip

        except Exception:
            try:
                addresses = self.driver.ex_describe_all_addresses()
                allocation_id = address.extra.get("allocation_id")
                if not allocation_id:
                    raise RuntimeError("Missing Elastic IP allocation ID")

                current = next(
                    (
                        item for item in addresses
                        if item.extra.get("allocation_id") == allocation_id
                    ),
                    None,
                )

                if current is None:
                    logger.error(
                        "Cannot verify Elastic IP %s; manual reconciliation required",
                        address.ip,
                    )
                elif current.instance_id:
                    logger.error(
                        "Elastic IP %s is associated; manual cleanup required",
                        address.ip,
                    )
                else:
                    released = self.driver.ex_release_address(
                        elastic_ip=current,
                        domain="vpc",
                    )
                    if not released:
                        logger.error(
                            "Failed to release Elastic IP %s", address.ip
                        )
            except Exception:
                logger.exception(
                    "Could not verify or clean up Elastic IP %s",
                    address.ip,
                )
            raise

    def release_floating_ip(
        self, name: str, release_allocation: bool = True
    ) -> bool:
        """Disassociate an Elastic IP; optionally release its allocation."""
        node = self._find_node(name)
        if node is None:
            return False
        addresses = self.driver.ex_describe_all_addresses(
            only_associated=True
        )
        associated = [
            address for address in addresses
            if address.instance_id == node.id
            and address.domain == "vpc"
        ]
        if not associated:
            return False
        if len(associated) > 1:
            raise RuntimeError(
                f"VM {name} has multiple Elastic IPs; "
                "explicit address selection is required"
            )
        address = associated[0]

        if not self._is_managed_elastic_ip(address):
            raise RuntimeError(
                f"Elastic IP {address.ip} is not managed by cloudmesh-ai-vm; "
                "refusing to disassociate or release it"
            )

        if not address.extra.get("association_id"):
            raise RuntimeError("Missing Elastic IP association ID")
        if release_allocation and not address.extra.get("allocation_id"):
            raise RuntimeError("Missing Elastic IP allocation ID")
        disassociated = self.driver.ex_disassociate_address(
            elastic_ip=address,
            domain="vpc",
        )
        if not disassociated:
            return False
        if not release_allocation:
            logger.info(
                "Disassociated Elastic IP %s without releasing allocation",
                address.ip,
            )
            return True
        return bool(
            self.driver.ex_release_address(
                elastic_ip=address,
                domain="vpc",
            )
        )

    def restart(self, name: str | None = None) -> bool:
        """Reboot an existing running EC2 instance."""
        if not name:
            return False
        try:
            node = self._find_node(name)
            if node is None:
                return False

            reboot = getattr(self.driver, "reboot_node", None)
            if not callable(reboot):
                raise ProviderFeatureNotSupported(
                    self.cloud_name, "restart"
                )

            return bool(reboot(node))
        except ProviderFeatureNotSupported:
            raise
        except Exception as e:
            logger.error("Error restarting AWS VM %s: %s", name, e)
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
        """Reboot a running instance or start an existing stopped instance."""
        if not name:
            return False
        try:
            node = self._find_node(name)
            if node is None:
                return False
            from libcloud.compute.types import NodeState
            if node.state == NodeState.STOPPED:
                return bool(self.driver.start_node(node))
            if node.state == NodeState.RUNNING:
                return bool(self.driver.reboot_node(node))
            logger.warning(
                "Cannot reset AWS VM %s in state %s", name, node.state
            )
            return False
        except Exception as e:
            logger.error("Error resetting AWS VM %s: %s", name, e)
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
