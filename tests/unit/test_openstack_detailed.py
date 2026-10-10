import pytest
from unittest.mock import MagicMock, patch
from cloudmesh.ai.vm.openstack.OpenstackManager import OpenstackManager
from cloudmesh.ai.vm.exceptions import VMProviderError, VMResourceError

# Mock configuration for OpenStack tests
MOCK_CONFIG = {
    "clouds": {
        "test-openstack": {
            "image": "test-image",
            "flavor": "test-flavor",
            "auth_url": "https://example.invalid/v3/",
            "region_name": "RegionOne",
        }
    }
}

class TestOpenstackDetailed:
    """
    Detailed unit tests for OpenstackManager focused on CLI fallbacks,
    floating IP logic, and error handling.
    """

    @pytest.fixture
    def provider(self):
        driver = MagicMock()
        with patch.object(OpenstackManager, "_get_driver", return_value=driver):
            provider = OpenstackManager(MOCK_CONFIG, cloud_name="test-openstack")
            provider.driver = driver
            return provider

    def test_run_cli_command_success(self, provider):
        """Verify that _run_cli_command correctly sets env vars and returns output."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="success-output")

            result = provider._run_cli_command(["openstack", "server", "list"])

            assert result == "success-output"
            # Verify env vars were set
            args, kwargs = mock_run.call_args
            assert kwargs["env"]["OS_CLOUD"] == "test-openstack"

    def test_run_cli_command_failure(self, provider):
        """Verify that _run_cli_command raises VMProviderError on non-zero exit."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stderr="some error")

            with pytest.raises(VMProviderError, match="CLI command failed"):
                provider._run_cli_command(["openstack", "server", "list"])

    def test_list_cli_fallback_success(self, provider):
        """Test that list() falls back to CLI when libcloud returns no results."""
        # 1. Mock libcloud to return empty list
        provider.driver.list_nodes.return_value = []

        # 2. Mock CLI output
        mock_cli_output = "Name\tID\tStatus\tImage\tFlavor\tNetworks\nvm1\tid1\tACTIVE\timg1\tflv1\tnet1"
        with patch.object(provider, "_run_cli_command", return_value=mock_cli_output):
            vms = provider.list()

            assert len(vms) == 1
            assert vms[0]["name"] == "vm1"
            assert vms[0]["id"] == "id1"
            assert vms[0]["status"] == "ACTIVE"

    def test_get_floating_ip_success(self, provider):
        """Verify _get_floating_ip correctly parses the 'addresses' output."""
        mock_output = "network: a=10.0.0.1,net-id=net1; floating: a=1.2.3.4,net-id=net2"
        with patch.object(provider, "_run_cli_command", return_value=mock_output), \
             patch.object(provider, "_find_node", return_value=MagicMock(public_ips=[])):
            ip = provider._get_floating_ip("test-vm")
            assert ip == "1.2.3.4"

    def test_get_floating_ip_none(self, provider):
        """Verify _get_floating_ip returns None when no floating IP is assigned."""
        mock_output = "network: a=10.0.0.1,net-id=net1"
        with patch.object(provider, "_run_cli_command", return_value=mock_output), \
             patch.object(provider, "_find_node", return_value=MagicMock(public_ips=[])):
            ip = provider._get_floating_ip("test-vm")
            assert ip is None

    def test_assign_floating_ip_success(self, provider):
        """Test assigning a floating IP via CLI."""
        # Mock driver objects
        mock_node = MagicMock()
        mock_node.name = "test-vm"
        mock_node.id = "id-123"

        mock_fip = MagicMock()
        mock_fip.ip = "1.2.3.4"

        provider.driver.ex_create_floating_ip.return_value = mock_fip
        provider.driver._find_node.return_value = mock_node # Not used by manager, manager uses _find_node

        with patch.object(provider, "_find_node", return_value=mock_node), \
             patch.object(provider, "wait_for_active", return_value=True), \
             patch.object(provider, "_wait_for_network", return_value=True):

            ip = provider.assign_floating_ip("test-vm")
            assert ip == "1.2.3.4"
            provider.driver.ex_attach_floating_ip_to_node.assert_called_once_with(mock_node, mock_fip)

    def test_release_floating_ip_success(self, provider):
        """Test releasing a floating IP."""
        # Mock driver objects
        mock_node = MagicMock()
        mock_node.name = "test-vm"
        mock_node.public_ips = ["1.2.3.4"]

        mock_fip = MagicMock()
        mock_fip.ip = "1.2.3.4"

        provider.driver.ex_get_floating_ip.return_value = mock_fip

        with patch.object(provider, "_find_node", return_value=mock_node):
            result = provider.release_floating_ip("test-vm")
            assert result is True
            provider.driver.ex_detach_floating_ip_from_node.assert_called_once_with(mock_node, mock_fip)
            provider.driver.ex_delete_floating_ip.assert_called_once_with(mock_fip)
