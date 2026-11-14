from unittest.mock import MagicMock, patch

import pytest

from cloudmesh.ai.vm.aws.AwsManager import Provider as AwsProvider
from cloudmesh.ai.vm.azure.AzureManager import Provider as AzureProvider
from cloudmesh.ai.vm.google.GoogleManager import Provider as GoogleProvider

# Mock configuration for all hyperscalers
MOCK_CONFIG = {
    "clouds": {
        "aws": {
            "access_key": "test-access",
            "secret_key": "test-secret",
            "region": "us-east-1",
        },
        "azure": {
            "tenant_id": "test-tenant",
            "subscription_id": "test-sub",
            "client_id": "test-client",
            "client_secret": "test-secret",
        },
        "google": {
            "project_id": "test-project",
            "private_key": "/path/to/key.json",
        },
    }
}


class TestHyperscalers:
    """
    Unit tests for AWS, Azure, and Google providers.
    Focuses on provider-specific overrides.
    """

    # --- AWS Tests ---
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

    def test_aws_provider_info(self):
        provider = AwsProvider(MOCK_CONFIG)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="aws-cli/2.0.0")
            info = provider.get_provider_info()

            assert info["provider"] == "AWS"
            assert info["version"] == "aws-cli/2.0.0"
            assert info["config"]["region"] == "us-east-1"

    # --- Azure Tests ---
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

    def test_azure_provider_info(self):
        provider = AzureProvider(MOCK_CONFIG)
        info = provider.get_provider_info()

        assert info["provider"] == "Azure"
        assert info["config"]["subscription_id"] == "test-sub"
        assert info["config"]["tenant_id"] == "test-tenant"

    # --- Google Tests ---
    @patch("cloudmesh.ai.vm.google.GoogleManager.GCEDriver")
    def test_google_init(self, mock_driver_class):
        mock_driver_class.return_value = MagicMock()
        provider = GoogleProvider(MOCK_CONFIG)

        mock_driver_class.assert_called_once_with(
            project_id="test-project", private_key="/path/to/key.json"
        )
        assert provider.cloud_name == "google"

    def test_google_provider_info(self):
        provider = GoogleProvider(MOCK_CONFIG)

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="google-cloud-sdk 400.0.0\nOther info"
            )
            info = provider.get_provider_info()

            assert info["provider"] == "Google"
            assert info["version"] == "google-cloud-sdk 400.0.0"
            assert info["config"]["project_id"] == "test-project"

    # --- Common Logic Tests (wait_for_status) ---
    @pytest.mark.parametrize(
        "provider_cls", [AwsProvider, AzureProvider, GoogleProvider]
    )
    def test_wait_for_status_success(self, provider_cls):
        provider = provider_cls(MOCK_CONFIG)
        provider.driver = MagicMock()

        # Mock the node to return 'running' status
        mock_node = MagicMock()
        mock_node.state = "running"
        provider.driver.get_node.return_value = mock_node

        assert (
            provider.wait_for_status(name="test-vm", target_status="running", timeout=1)
            is True
        )

    @pytest.mark.parametrize(
        "provider_cls", [AwsProvider, AzureProvider, GoogleProvider]
    )
    def test_wait_for_status_timeout(self, provider_cls):
        provider = provider_cls(MOCK_CONFIG)
        provider.driver = MagicMock()

        # Mock the node to always return 'stopped'
        mock_node = MagicMock()
        mock_node.state = "stopped"
        provider.driver.get_node.return_value = mock_node

        # Short timeout for testing
        assert (
            provider.wait_for_status(name="test-vm", target_status="running", timeout=1)
            is False
        )
