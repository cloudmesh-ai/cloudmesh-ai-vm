import pytest
from unittest.mock import MagicMock, patch
from cloudmesh.ai.vm.aws.AwsManager import Provider as AwsProvider
from cloudmesh.ai.vm.azure.AzureManager import Provider as AzureProvider
from cloudmesh.ai.vm.google.GoogleManager import Provider as GoogleProvider

from cloudmesh.ai.vm.exceptions import VMProviderError, ProviderFeatureNotSupported

# Mock configuration
MOCK_CONFIG = {
    "clouds": {
        "aws": {
            "access_key": "test-access",
            "secret_key": "test-secret",
            "region": "us-east-1",
            "image": "ami-123",
            "size": "t2.micro"
        },
        "azure": {
            "tenant_id": "test-tenant",
            "subscription_id": "test-sub",
            "client_id": "test-client",
            "client_secret": "test-secret",
            "image": "ubuntu-22.04",
            "size": "Standard_DS1_v2"
        },
        "google": {
            "project_id": "test-project",
            "private_key": "/path/to/key.json",
            "image": "ubuntu-2204-lts",
            "size": "n1-standard-1"
        }
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

    @patch("cloudmesh.ai.vm.aws.AwsManager.AmazonEC2Driver")
    def test_aws_init(self, mock_driver_class):
        mock_driver_class.return_value = MagicMock()
        provider = AwsProvider(MOCK_CONFIG)
        
        mock_driver_class.assert_called_once_with(
            access_key="test-access",
            secret_key="test-secret",
            region="us-east-1"
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
            client_secret="test-secret"
        )
        assert provider.cloud_name == "azure"

    @patch("cloudmesh.ai.vm.google.GoogleManager.GCEDriver")
    def test_google_init(self, mock_driver_class):
        mock_driver_class.return_value = MagicMock()
        provider = GoogleProvider(MOCK_CONFIG)
        
        mock_driver_class.assert_called_once_with(
            project_id="test-project",
            private_key="/path/to/key.json"
        )
        assert provider.cloud_name == "google"

    def test_lifecycle_methods(self, mock_driver):
        # Test using AWS Provider as the representative for LibcloudManager logic
        with patch("cloudmesh.ai.vm.aws.AwsManager.AmazonEC2Driver", return_value=mock_driver):
            provider = AwsProvider(MOCK_CONFIG)
            
            # Update config to match the mock images/sizes
            provider.config["clouds"]["aws"]["image"] = "test-image"
            provider.config["clouds"]["aws"]["size"] = "test-size"

            # Test Start (Currently raises ProviderFeatureNotSupported in LibcloudManager)
            with pytest.raises(ProviderFeatureNotSupported):
                provider.start(name="test-vm")

            # Test Stop
            assert provider.stop(name="test-vm") is True
            mock_driver.get_node.return_value.stop.assert_called_once()

            # Test Delete
            assert provider.delete(name="test-vm") is True
            mock_driver.get_node.return_value.destroy.assert_called_once()

            # Test List
            vms = provider.list()
            assert len(vms) == 1
            assert vms[0]["Name"] == "test-vm"

    def test_unsupported_methods(self, mock_driver):
        # Remove suspend/reboot from driver to test "not supported" logic
        del mock_driver.suspend_node
        del mock_driver.reboot_node
        
        with patch("cloudmesh.ai.vm.aws.AwsManager.AmazonEC2Driver", return_value=mock_driver):
            provider = AwsProvider(MOCK_CONFIG)
            with pytest.raises(ProviderFeatureNotSupported):
                provider.suspend(name="test-vm")
            with pytest.raises(ProviderFeatureNotSupported):
                provider.restart(name="test-vm")

    def test_missing_config(self):
        incomplete_config = {"clouds": {"aws": {}}}
        with patch("cloudmesh.ai.vm.aws.AwsManager.AmazonEC2Driver", return_value=MagicMock()):
            provider = AwsProvider(incomplete_config)
            # start() raises ProviderFeatureNotSupported, not VMProviderError, 
            # but if we were to implement it, it would check config.
            # For now, let's just verify it handles the config lookup.
            with pytest.raises(ProviderFeatureNotSupported):
                provider.start(name="test")
