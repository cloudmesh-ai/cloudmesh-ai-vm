import pytest
from unittest.mock import patch, MagicMock, PropertyMock
import subprocess
from cloudmesh.ai.vm.local.LimaManager import Provider
from cloudmesh.ai.vm.exceptions import VMProviderError

@pytest.fixture
def mock_config():
    return {
        "clouds": {
            "lima": {
                "template": "ubuntu"
            }
        }
    }

@pytest.fixture
def provider(mock_config):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        return Provider(mock_config)

def test_init_success():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        config = {"clouds": {}}
        p = Provider(config)
        mock_run.assert_called_once_with(["limactl", "--version"], capture_output=True, check=True)

def test_init_failure():
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = FileNotFoundError
        config = {"clouds": {}}
        with pytest.raises(VMProviderError, match="limactl not found"):
            Provider(config)

def test_start_with_name(provider):
    # Mock Popen for _run_command
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout = ["Success\n"]
        mock_process.returncode = 0
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        vm_name = "test-vm"
        result = provider.start(name=vm_name)
        
        assert result == vm_name
        mock_popen.assert_called_once_with(
            ["limactl", "start", "--name", vm_name, "template:ubuntu"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

def test_start_default_name(provider):
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout = ["Success\n"]
        mock_process.returncode = 0
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        result = provider.start()
        
        assert result == "lima-vm"
        mock_popen.assert_called_once_with(
            ["limactl", "start", "--name", "lima-vm", "template:ubuntu"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

def test_stop_success(provider):
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout = ["Stopped\n"]
        mock_process.returncode = 0
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        assert provider.stop(name="test-vm") is True
        mock_popen.assert_called_once_with(
            ["limactl", "stop", "test-vm"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

def test_delete_success(provider):
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout = ["Deleted\n"]
        mock_process.returncode = 0
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        assert provider.delete(name="test-vm") is True
        mock_popen.assert_called_once_with(
            ["limactl", "delete", "-f", "test-vm"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

def test_list_parsing(provider):
    # Mock limactl list output with newlines
    mock_output = (
        "NAME              STATUS    IMAGE\n"
        "vm-1              Running   ubuntu\n"
        "vm-2              Stopped   fedora\n"
    )
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        # Ensure each line ends with \n as it would come from a real process
        mock_process.stdout = [line + "\n" for line in mock_output.split("\n") if line]
        mock_process.returncode = 0
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        vms = provider.list()
        
        assert len(vms) == 2
        assert vms[0]["NAME"] == "vm-1"
        assert vms[0]["STATUS"] == "Running"
        assert vms[1]["NAME"] == "vm-2"
        assert vms[1]["STATUS"] == "Stopped"

def test_login(provider):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        assert provider.login(name="test-vm") is True
        mock_run.assert_called_once_with(["limactl", "shell", "test-vm"], check=True)

def test_restart(provider):
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout = ["Success\n"]
        mock_process.returncode = 0
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process
        
        assert provider.restart(name="test-vm") is True
        # Should call stop then start
        assert mock_popen.call_count == 2
        mock_popen.assert_any_call(["limactl", "stop", "test-vm"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        mock_popen.assert_any_call(["limactl", "start", "test-vm"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)

def test_getters(provider):
    flavors = provider.get_flavors()
    assert len(flavors) > 0
    assert flavors[0]["name"] == "default"
    
    keys = provider.get_keys()
    assert len(keys) == 1
    assert keys[0]["name"] == "lima-ssh-key"
    
    sgs = provider.get_security_groups()
    assert len(sgs) == 1
    assert sgs[0]["name"] == "default"
