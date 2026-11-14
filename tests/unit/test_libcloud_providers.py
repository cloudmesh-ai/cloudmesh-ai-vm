from unittest.mock import MagicMock, patch

import pytest

from cloudmesh.ai.vm.aws.AwsManager import Provider as AwsProvider
from cloudmesh.ai.vm.azure.AzureManager import Provider as AzureProvider
from cloudmesh.ai.vm.exceptions import ProviderFeatureNotSupported
from cloudmesh.ai.vm.google.GoogleManager import Provider as GoogleProvider

# Mock configuration
MOCK_CONFIG = {
    "clouds": {
        "aws": {
            "access_key": "test-access",
            "secret_key": "test-secret",
            "region": "us-east-1",
            "image": "ami-123",
            "size": "t2.micro",
        },
        "azure": {
            "tenant_id": "test-tenant",
            "subscription_id": "test-sub",
            "client_id": "test-client",
            "client_secret": "test-secret",
            "image": "ubuntu-22.04",
            "size": "Standard_DS1_v2",
        },
        "google": {
            "project_id": "test-project",
            "private_key": "/path/to/key.json",
            "image": "ubuntu-2204-lts",
            "size": "n1-standard-1",
        },
    }
}


class TestLibcloudProviders:
    """
    Test suite for AWS, Azure, and Google providers implementing LibcloudManager.
    """

    @pytest.fixture
    def mock_driver(self):
        driver = MagicMock()
        # Mock images and sizes
        mock_image = MagicMock()
        mock_image.name = "test-image"
        driver.list_images.return_value = [mock_image]

        mock_size = MagicMock()
        mock_size.name = "test-size"
        mock_size.id = "test-size-id"
        driver.list_sizes.return_value = [mock_size]

        # Mock node
        mock_node = MagicMock()
        mock_node.name = "test-vm"
        mock_node.id = "vm-123"
        mock_node.state = "running"
        mock_node.public_ips = ["1.2.3.4"]
        driver.create_node.return_value = mock_node
        driver.get_node.return_value = mock_node
        driver.list_nodes.return_value = [mock_node]

        return driver

    @patch("cloudmesh.ai.vm.aws.AwsManager.get_driver")
    def test_aws_init(self, mock_get_driver):
        mock_driver_class = MagicMock()
        mock_get_driver.return_value = mock_driver_class
        provider = AwsProvider(MOCK_CONFIG)
        mock_get_driver.assert_called_once()
        mock_driver_class.assert_called_once_with(
            key="test-access",
            secret="test-secret",
            region="us-east-1",
        )
        assert provider.cloud_name == "aws"

    @patch("cloudmesh.ai.vm.azure.AzureManager.AzureDriver")
    def test_azure_init(self, mock_driver_class):
        mock_driver_class.return_value = MagicMock()
        provider = AzureProvider(MOCK_CONFIG)

        mock_driver_class.assert_called_once_with(
            tenant_id="test-tenant",
            subscription_id="test-sub",
            client_id="test-client",
            client_secret="test-secret",
        )
        assert provider.cloud_name == "azure"

    @patch("cloudmesh.ai.vm.google.GoogleManager.GCEDriver")
    def test_google_init(self, mock_driver_class):
        mock_driver_class.return_value = MagicMock()
        provider = GoogleProvider(MOCK_CONFIG)

        mock_driver_class.assert_called_once_with(
            project_id="test-project", private_key="/path/to/key.json"
        )
        assert provider.cloud_name == "google"

    def test_lifecycle_methods(self, mock_driver):
        # Test using AWS Provider as the representative for LibcloudManager logic
        with patch(
            "cloudmesh.ai.vm.aws.AwsManager.get_driver",
            return_value=MagicMock(return_value=mock_driver),
        ):
            provider = AwsProvider(MOCK_CONFIG)

            # Configure AWS-compatible image and instance type IDs.
            provider.config["clouds"]["aws"]["image"] = "ami-123"
            provider.config["clouds"]["aws"]["size"] = "t3.micro"

            mock_image = mock_driver.list_images.return_value[0]
            mock_image.id = "ami-123"

            mock_size = mock_driver.list_sizes.return_value[0]
            mock_size.id = "t3.micro"

            # Existing VM must not conflict with the new VM name.
            existing_node = mock_driver.list_nodes.return_value[0]
            existing_node.name = "existing-vm"
            mock_driver.get_node.return_value = None

            # Test Start
            result = provider.start(name="test-vm")
            assert result == "vm-123"
            mock_driver.list_images.assert_called_once_with(
                ex_image_ids=["ami-123"]
            )
            mock_driver.create_node.assert_called_once_with(
                name="test-vm",
                image=mock_image,
                size=mock_size,
                ex_assign_public_ip=False,
            )

            # Simulate AWS returning two distinct instances.
            created_node = mock_driver.create_node.return_value
            created_node.name = "test-vm"

            existing_node = MagicMock()
            existing_node.name = "existing-vm"
            existing_node.id = "i-existing"
            existing_node.state = "running"
            existing_node.public_ips = []

            mock_driver.list_nodes.return_value = [
                existing_node,
                created_node,
            ]

            # Test Stop
            assert provider.stop(name="test-vm") is True
            mock_driver.stop_node.assert_called_once_with(created_node)

            # Test Delete
            assert provider.delete(name="test-vm") is True
            mock_driver.destroy_node.assert_called_once_with(created_node)

            # Test List
            vms = provider.list()
            assert len(vms) == 2
            assert {vm["Name"] for vm in vms} == {
                "existing-vm",
                "test-vm",
            }

    def test_unsupported_methods(self, mock_driver):
        # Create a node mock that explicitly lacks the suspend/reboot methods
        # Using spec=[] ensures that hasattr() returns False for any attribute
        mock_node = MagicMock(spec=[])
        mock_driver.get_node.return_value = mock_node

        with patch(
            "cloudmesh.ai.vm.aws.AwsManager.get_driver", return_value=mock_driver
        ):
            provider = AwsProvider(MOCK_CONFIG)

            # AWS suspend is supported by mapping it to stop().
            with patch.object(
                provider,
                "stop",
                return_value=True,
            ) as mock_stop:
                assert provider.suspend(name="test-vm") is True
                mock_stop.assert_called_once_with("test-vm")

            # Restart should raise ProviderFeatureNotSupported only when
            # neither the node nor the driver provides reboot support.
            mock_node = MagicMock(spec=[])

            limited_driver = MagicMock(spec=["get_node"])
            limited_driver.get_node.return_value = mock_node

            provider.driver = limited_driver

            with pytest.raises(ProviderFeatureNotSupported):
                provider.restart(name="test-vm")
    def test_missing_config(self):
        incomplete_config = {"clouds": {"aws": {}}}
        with patch(
            "cloudmesh.ai.vm.aws.AwsManager.get_driver", return_value=MagicMock()
        ):
            provider = AwsProvider(incomplete_config)
            # start() should raise ConfigError if image is missing
            with pytest.raises(Exception) as excinfo:
                provider.start(name="test")
            assert "Missing 'image'" in str(excinfo.value)


class TestAwsElasticIP:
    """Mocked tests for AWS EC2 Elastic IP management."""

    @pytest.fixture
    def provider_and_resources(self):
        provider = AwsProvider.__new__(AwsProvider)
        provider.driver = MagicMock()
        provider.driver.ex_describe_tags.return_value = {
            "cloudmesh-ai-vm:managed": "true",
            "cloudmesh-ai-vm:resource": "elastic-ip",
        }

        node = MagicMock()
        node.id = "i-123456"

        address = MagicMock()
        address.ip = "203.0.113.10"
        address.domain = "vpc"
        address.instance_id = node.id
        address.extra = {
            "allocation_id": "eipalloc-123",
            "association_id": "eipassoc-123",
        }

        return provider, node, address

    def test_allocate_and_associate(self, provider_and_resources):
        provider, node, address = provider_and_resources
        address.instance_id = None
        provider.driver.ex_describe_all_addresses.return_value = []
        provider.driver.ex_allocate_address.return_value = address
        provider.driver.ex_associate_address_with_node.return_value = (
            "eipassoc-123"
        )

        with patch.object(provider, "_find_node", return_value=node):
            assert provider.assign_floating_ip(node.id) == address.ip

        provider.driver.ex_allocate_address.assert_called_once_with(
            domain="vpc"
        )
        provider.driver.ex_associate_address_with_node.assert_called_once_with(
            node=node, elastic_ip=address, domain="vpc"
        )
        tag_resource, tag_values = (
            provider.driver.ex_create_tags.call_args.args
        )
        assert tag_resource.id == "eipalloc-123"
        assert tag_values == {
            "cloudmesh-ai-vm:managed": "true",
            "cloudmesh-ai-vm:resource": "elastic-ip",
        }

    def test_tagging_failure_cleanup(self, provider_and_resources):
        provider, node, address = provider_and_resources
        address.instance_id = None
        provider.driver.ex_describe_all_addresses.side_effect = [
            [],
            [address],
        ]
        provider.driver.ex_allocate_address.return_value = address
        provider.driver.ex_create_tags.return_value = False
        provider.driver.ex_release_address.return_value = True

        with patch.object(provider, "_find_node", return_value=node):
            with pytest.raises(RuntimeError, match="Failed to tag"):
                provider.assign_floating_ip(node.id)

        provider.driver.ex_associate_address_with_node.assert_not_called()
        provider.driver.ex_release_address.assert_called_once_with(
            elastic_ip=address,
            domain="vpc",
        )

    def test_tagging_exception_cleanup(self, provider_and_resources):
        """Clean up an allocation when AWS raises during tagging."""
        provider, node, address = provider_and_resources
        address.instance_id = None

        provider.driver.ex_describe_all_addresses.side_effect = [
            [],
            [address],
        ]
        provider.driver.ex_allocate_address.return_value = address
        provider.driver.ex_create_tags.side_effect = RuntimeError(
            "Simulated AWS tagging API failure"
        )
        provider.driver.ex_release_address.return_value = True

        with patch.object(provider, "_find_node", return_value=node):
            with pytest.raises(
                RuntimeError, match="Simulated AWS tagging API failure"
            ):
                provider.assign_floating_ip(node.id)

        provider.driver.ex_associate_address_with_node.assert_not_called()
        provider.driver.ex_release_address.assert_called_once_with(
            elastic_ip=address,
            domain="vpc",
        )

    def test_cleanup_when_allocation_state_cannot_be_verified(
        self, provider_and_resources
    ):
        """Never release an allocation when AWS state cannot be verified."""
        provider, node, address = provider_and_resources
        address.instance_id = None

        provider.driver.ex_describe_all_addresses.side_effect = [
            [],
            RuntimeError("AWS DescribeAddresses unavailable"),
        ]
        provider.driver.ex_allocate_address.return_value = address
        provider.driver.ex_create_tags.return_value = True
        provider.driver.ex_associate_address_with_node.side_effect = (
            RuntimeError("Simulated association failure")
        )

        with patch.object(provider, "_find_node", return_value=node):
            with pytest.raises(RuntimeError, match="association failure"):
                provider.assign_floating_ip(node.id)

        provider.driver.ex_release_address.assert_not_called()


    def test_reuse_existing_address(self, provider_and_resources):
        provider, node, address = provider_and_resources
        provider.driver.ex_describe_all_addresses.return_value = [address]

        with patch.object(provider, "_find_node", return_value=node):
            assert provider.assign_floating_ip(node.id) == address.ip

        provider.driver.ex_allocate_address.assert_not_called()

    def test_assign_missing_instance(self, provider_and_resources):
        provider, _, _ = provider_and_resources

        with patch.object(provider, "_find_node", return_value=None):
            with pytest.raises(ValueError):
                provider.assign_floating_ip("missing-vm")

        provider.driver.ex_allocate_address.assert_not_called()

    def test_association_failure_cleanup(self, provider_and_resources):
        provider, node, address = provider_and_resources
        address.instance_id = None
        provider.driver.ex_describe_all_addresses.side_effect = [
            [],
            [address],
        ]
        provider.driver.ex_allocate_address.return_value = address
        provider.driver.ex_associate_address_with_node.side_effect = (
            RuntimeError("Simulated association failure")
        )
        provider.driver.ex_release_address.return_value = True

        with patch.object(provider, "_find_node", return_value=node):
            with pytest.raises(
                RuntimeError, match="Simulated association failure"
            ):
                provider.assign_floating_ip(node.id)

        provider.driver.ex_release_address.assert_called_once_with(
            elastic_ip=address, domain="vpc"
        )

    def test_release_rejects_unmanaged_elastic_ip(
        self, provider_and_resources
    ):
        """Never disassociate an Elastic IP without ownership evidence."""
        provider, node, address = provider_and_resources
        provider.driver.ex_describe_all_addresses.return_value = [address]
        provider.driver.ex_describe_tags.return_value = {}

        with patch.object(provider, "_find_node", return_value=node):
            with pytest.raises(
                (ValueError, RuntimeError),
                match="(?i)managed|ownership|unmanaged",
            ):
                provider.release_floating_ip(
                    node.id,
                    release_allocation=True,
                )

        provider.driver.ex_disassociate_address.assert_not_called()
        provider.driver.ex_release_address.assert_not_called()

    def test_default_release_releases_allocation(
        self, provider_and_resources
    ):
        provider, node, address = provider_and_resources
        provider.driver.ex_describe_all_addresses.return_value = [address]
        provider.driver.ex_disassociate_address.return_value = True
        provider.driver.ex_release_address.return_value = True

        with patch.object(provider, "_find_node", return_value=node):
            assert provider.release_floating_ip(node.id) is True

        provider.driver.ex_disassociate_address.assert_called_once_with(
            elastic_ip=address, domain="vpc"
        )
        provider.driver.ex_release_address.assert_called_once_with(
            elastic_ip=address, domain="vpc"
        )

    def test_explicit_disassociation_preserves_allocation(
        self, provider_and_resources
    ):
        provider, node, address = provider_and_resources
        provider.driver.ex_describe_all_addresses.return_value = [address]
        provider.driver.ex_disassociate_address.return_value = True

        with patch.object(provider, "_find_node", return_value=node):
            assert provider.release_floating_ip(
                node.id, release_allocation=False
            ) is True

        provider.driver.ex_disassociate_address.assert_called_once_with(
            elastic_ip=address, domain="vpc"
        )
        provider.driver.ex_release_address.assert_not_called()

    def test_failed_disassociation_prevents_release(
        self, provider_and_resources
    ):
        provider, node, address = provider_and_resources
        provider.driver.ex_describe_all_addresses.return_value = [address]
        provider.driver.ex_disassociate_address.return_value = False

        with patch.object(provider, "_find_node", return_value=node):
            assert provider.release_floating_ip(
                node.id, release_allocation=True
            ) is False

        provider.driver.ex_release_address.assert_not_called()

    def test_release_missing_instance(self, provider_and_resources):
        provider, _, _ = provider_and_resources

        with patch.object(provider, "_find_node", return_value=None):
            assert provider.release_floating_ip("missing-vm") is False

        provider.driver.ex_disassociate_address.assert_not_called()
        provider.driver.ex_release_address.assert_not_called()

    def test_release_without_associated_ip(self, provider_and_resources):
        provider, node, _ = provider_and_resources
        provider.driver.ex_describe_all_addresses.return_value = []

        with patch.object(provider, "_find_node", return_value=node):
            assert provider.release_floating_ip(node.id) is False

        provider.driver.ex_disassociate_address.assert_not_called()
        provider.driver.ex_release_address.assert_not_called()


class TestAwsEC2Creation:
    """Mocked validation tests for AWS EC2 instance creation."""

    @pytest.fixture
    def setup_aws(self):
        provider = AwsProvider.__new__(AwsProvider)
        provider.driver = MagicMock()

        config = {
            "image": "ami-123456",
            "size": "t3.micro",
        }
        provider.get_cloud_config = MagicMock(return_value=config)
        provider._find_node = MagicMock(return_value=None)

        image = MagicMock()
        image.id = "ami-123456"

        size = MagicMock()
        size.id = "t3.micro"
        size.name = "t3.micro"

        provider.driver.list_images.return_value = [image]
        provider.driver.list_sizes.return_value = [size]
        provider.driver.create_node.return_value.id = "i-new123"

        return provider, image, size

    def test_successful_creation(self, setup_aws):
        provider, image, size = setup_aws

        result = provider.start(name="test-ec2")

        assert result == "i-new123"
        provider.driver.list_images.assert_called_once_with(
            ex_image_ids=["ami-123456"]
        )
        provider.driver.create_node.assert_called_once_with(
            name="test-ec2",
            image=image,
            size=size,
            ex_assign_public_ip=False,
        )

    def test_explicit_flavor_overrides_config(self, setup_aws):
        provider, image, size = setup_aws

        size.id = "t3.small"
        size.name = "t3.small"

        result = provider.start(
            name="test-ec2",
            flavor="t3.small",
        )

        assert result == "i-new123"
        provider.driver.create_node.assert_called_once_with(
            name="test-ec2",
            image=image,
            size=size,
            ex_assign_public_ip=False,
        )

    def test_invalid_ami(self, setup_aws):
        provider, _, _ = setup_aws

        with pytest.raises(ValueError, match="AMI ID"):
            provider.start(name="test-ec2", image="ubuntu-latest")

        provider.driver.create_node.assert_not_called()

    def test_duplicate_instance(self, setup_aws):
        provider, _, _ = setup_aws
        provider._find_node.return_value = MagicMock()

        with pytest.raises(ValueError, match="already exists"):
            provider.start(name="test-ec2")

        provider.driver.create_node.assert_not_called()

    def test_missing_instance_type(self, setup_aws):
        provider, _, _ = setup_aws
        provider.get_cloud_config.return_value = {
            "image": "ami-123456"
        }

        with pytest.raises(ValueError, match="size"):
            provider.start(name="test-ec2")

        provider.driver.create_node.assert_not_called()

    def test_unknown_ami(self, setup_aws):
        provider, _, _ = setup_aws
        provider.driver.list_images.return_value = []

        with pytest.raises(ValueError, match="not found"):
            provider.start(name="test-ec2")

        provider.driver.create_node.assert_not_called()

    def test_unknown_instance_type(self, setup_aws):
        provider, _, _ = setup_aws
        provider.driver.list_sizes.return_value = []

        with pytest.raises(ValueError, match="not found"):
            provider.start(name="test-ec2")

        provider.driver.create_node.assert_not_called()

    def test_valid_subnet(self, setup_aws):
        provider, image, size = setup_aws

        subnet = MagicMock()
        subnet.id = "subnet-123"
        provider.driver.ex_list_subnets.return_value = [subnet]

        result = provider.start(
            name="test-ec2",
            subnet_id="subnet-123",
            key_name="test-key",
            security_group_ids=["sg-123"],
            assign_public_ip=True,
        )

        assert result == "i-new123"
        provider.driver.ex_list_subnets.assert_called_once_with(
            subnet_ids=["subnet-123"]
        )
        provider.driver.create_node.assert_called_once_with(
            name="test-ec2",
            image=image,
            size=size,
            ex_keyname="test-key",
            ex_security_group_ids=["sg-123"],
            ex_subnet=subnet,
            ex_assign_public_ip=True,
        )

    def test_invalid_subnet(self, setup_aws):
        provider, _, _ = setup_aws
        provider.driver.ex_list_subnets.return_value = []

        with pytest.raises(ValueError, match="Subnet"):
            provider.start(name="test-ec2", subnet_id="subnet-invalid")

        provider.driver.create_node.assert_not_called()

    def test_invalid_security_groups(self, setup_aws):
        provider, _, _ = setup_aws

        with pytest.raises(ValueError, match="security_group_ids"):
            provider.start(
                name="test-ec2",
                security_group_ids="sg-123",
            )

        provider.driver.create_node.assert_not_called()

    def test_invalid_public_ip_setting(self, setup_aws):
        provider, _, _ = setup_aws

        with pytest.raises(ValueError, match="boolean"):
            provider.start(
                name="test-ec2",
                assign_public_ip="yes",
            )

        provider.driver.create_node.assert_not_called()


class TestAwsReset:
    """Regression tests for AWS EC2 reset behavior."""

    @pytest.fixture
    def setup_aws(self):
        provider = AwsProvider.__new__(AwsProvider)
        provider.driver = MagicMock()
        return provider

    def test_reset_running_instance_reboots(self, setup_aws):
        from libcloud.compute.types import NodeState

        provider = setup_aws
        node = MagicMock()
        node.state = NodeState.RUNNING
        provider.driver.reboot_node.return_value = True

        with patch.object(provider, "_find_node", return_value=node):
            assert provider.reset("test-vm") is True

        provider.driver.reboot_node.assert_called_once_with(node)
        provider.driver.start_node.assert_not_called()

    def test_reset_stopped_instance_starts(self, setup_aws):
        from libcloud.compute.types import NodeState

        provider = setup_aws
        node = MagicMock()
        node.state = NodeState.STOPPED
        provider.driver.start_node.return_value = True

        with patch.object(provider, "_find_node", return_value=node):
            assert provider.reset("test-vm") is True

        provider.driver.start_node.assert_called_once_with(node)
        provider.driver.reboot_node.assert_not_called()

    def test_reset_pending_instance_returns_false(self, setup_aws):
        from libcloud.compute.types import NodeState

        provider = setup_aws
        node = MagicMock()
        node.state = NodeState.PENDING

        with patch.object(provider, "_find_node", return_value=node):
            assert provider.reset("test-vm") is False

        provider.driver.start_node.assert_not_called()
        provider.driver.reboot_node.assert_not_called()

    def test_reset_missing_instance_returns_false(self, setup_aws):
        provider = setup_aws

        with patch.object(provider, "_find_node", return_value=None):
            assert provider.reset("missing-vm") is False

        provider.driver.start_node.assert_not_called()
        provider.driver.reboot_node.assert_not_called()
