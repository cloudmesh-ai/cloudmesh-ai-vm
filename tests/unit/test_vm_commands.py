import pytest
from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from cloudmesh.ai.command.vm import cmx

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.cloud_name = "mock-cloud"
    return provider

def test_vm_start_success(runner, mock_provider):
    """Test that 'cmx vm start' successfully starts a VM."""
    with patch("cloudmesh.ai.command.vm.start.get_active_provider", return_value=mock_provider):
        mock_provider.start.return_value = "test-vm"
        result = runner.invoke(cmx, ["vm", "start", "test-vm"])
        assert result.exit_code == 0
        assert "Successfully started VM test-vm" in result.output

def test_vm_start_failure(runner, mock_provider):
    """Test that 'cmx vm start' handles failure correctly via VMCommandError."""
    with patch("cloudmesh.ai.command.vm.start.get_active_provider", return_value=mock_provider):
        mock_provider.start.return_value = False
        result = runner.invoke(cmx, ["vm", "start", "test-vm"])
        assert result.exit_code != 0
        assert "Error: Failed to start VM test-vm" in result.output

def test_vm_list_table(runner, mock_provider):
    """Test that 'cmx vm list' renders a table of VMs."""
    with patch("cloudmesh.ai.command.vm.list.get_active_provider", return_value=mock_provider):
        mock_provider.list.return_value = [
            {"name": "vm1", "ip": "1.1.1.1", "status": "Running"},
            {"name": "vm2", "ip": "2.2.2.2", "status": "Stopped"},
        ]
        result = runner.invoke(cmx, ["vm", "list"])
        assert result.exit_code == 0
        assert "vm1" in result.output
        assert "vm2" in result.output

def test_vm_info_success(runner, mock_provider):
    """Test that 'cmx vm info' displays VM details."""
    with patch("cloudmesh.ai.command.vm.info.get_active_provider", return_value=mock_provider):
        mock_provider.info.return_value = {"Name": "test-vm", "IP": "1.2.3.4", "Status": "Running"}
        result = runner.invoke(cmx, ["vm", "info", "test-vm"])
        assert result.exit_code == 0
        assert "Information for VM: test-vm" in result.output
        assert "1.2.3.4" in result.output

def test_vm_info_not_found(runner, mock_provider):
    """Test that 'cmx vm info' handles VM not found."""
    with patch("cloudmesh.ai.command.vm.info.get_active_provider", return_value=mock_provider):
        mock_provider.info.return_value = None
        result = runner.invoke(cmx, ["vm", "info", "non-existent"])
        assert result.exit_code != 0
        assert "Error" in result.output

def test_vm_key_upload_success(runner, mock_provider):
    """Test that 'cmx vm key upload-key' successfully uploads a key."""
    with patch("os.path.exists", return_value=True), \
         patch("cloudmesh.ai.command.vm.key.upload.get_active_provider", return_value=mock_provider):
        mock_provider.upload_key.return_value = True
        result = runner.invoke(cmx, ["vm", "key", "upload-key", "dummy.pub", "--name", "my-key"])
        assert result.exit_code == 0
        assert "Successfully uploaded key" in result.output

def test_vm_key_upload_unsupported(runner, mock_provider):
    """Test that 'cmx vm key upload-key' handles unsupported providers."""
    del mock_provider.upload_key 
    with patch("os.path.exists", return_value=True), \
         patch("cloudmesh.ai.command.vm.key.upload.get_active_provider", return_value=mock_provider):
        result = runner.invoke(cmx, ["vm", "key", "upload-key", "dummy.pub", "--name", "my-key"])
        assert result.exit_code != 0
        assert "Error" in result.output
