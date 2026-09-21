import pytest
from unittest.mock import patch, MagicMock
import subprocess
from cloudmesh.ai.vm.local.MultipassManager import Provider

@pytest.fixture
def mock_config():
    return {
        "clouds": {
            "multipass": {
                "image": "22.04",
                "cpus": 2,
                "memory": "4GiB",
                "disk": "20GiB"
            }
        }
    }

@pytest.fixture
def provider(mock_config):
    return Provider(mock_config)

def test_start_with_name_and_config(provider):
    # Mock subprocess.run for _run_interactive
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        
        vm_name = "test-vm"
        result = provider.start(name=vm_name)
        
        # Verify the command constructed
        expected_command = ["multipass", "launch", "-c", "2", "-m", "4GiB", "-d", "20GiB", "-n", vm_name, "22.04"]
        mock_run.assert_called_once_with(
            expected_command,
            capture_output=False,
            check=True
        )
        assert result == vm_name

def test_start_without_name(provider):
    # Mock subprocess.run for _run_interactive
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        
        result = provider.start()
        
        expected_command = ["multipass", "launch", "-c", "2", "-m", "4GiB", "-d", "20GiB", "22.04"]
        mock_run.assert_called_once_with(
            expected_command,
            capture_output=False,
            check=True
        )
        assert result == "multipass-generated"

def test_stop_success(provider):
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout = iter(["Stopped\n"])
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("", "")
        mock_popen.return_value = mock_process
        
        assert provider.stop(name="test-vm") is True
        mock_popen.assert_called_once_with(
            ["multipass", "stop", "test-vm"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            bufsize=1
        )

def test_stop_failure(provider):
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout = iter(["VM not found\n"])
        mock_process.returncode = 1
        mock_process.communicate.return_value = ("", "")
        mock_popen.return_value = mock_process
        
        assert provider.stop(name="non-existent") is False

def test_delete_success(provider):
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout = iter(["Deleted\n"])
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("", "")
        mock_popen.return_value = mock_process
        
        assert provider.delete(name="test-vm") is True
        # Should call both delete and purge
        assert mock_popen.call_count == 2
        mock_popen.assert_any_call(
            ["multipass", "delete", "test-vm"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            bufsize=1
        )
        mock_popen.assert_any_call(
            ["multipass", "purge"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            bufsize=1
        )

def test_list_parsing(provider):
    # Mock Multipass output
    mock_output = (
        "Name                    State             IPv4             Image\n"
        "vm-1                    Running           192.168.64.5     Ubuntu 22.04 LTS\n"
        "vm-2                    Stopped           192.168.64.6     Ubuntu 22.04 LTS\n"
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(
            stdout=mock_output, 
            returncode=0
        )
        
        vms = provider.list()
        
        assert len(vms) == 2
        assert vms[0]["name"] == "vm-1"
        assert vms[0]["status"] == "Running"
        assert vms[1]["name"] == "vm-2"
        assert vms[1]["status"] == "Stopped"

def test_restart_success(provider):
    with patch("subprocess.Popen") as mock_popen, \
         patch("subprocess.run") as mock_run:
        # Mock Popen for stop()
        mock_process = MagicMock()
        mock_process.stdout = iter(["Success\n"])
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("", "")
        mock_popen.return_value = mock_process
        
        # Mock run for start()
        mock_run.return_value = MagicMock(returncode=0)
        
        assert provider.restart(name="test-vm") is True
        # Verify stop was called then start
        mock_popen.assert_any_call(
            ["multipass", "stop", "test-vm"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.STDOUT, 
            text=True, 
            bufsize=1
        )
        mock_run.assert_any_call(
            ["multipass", "start", "test-vm"],
            capture_output=False,
            check=True
        )

def test_getters(provider):
    # Test flavor getter
    flavors = provider.get_flavors()
    assert isinstance(flavors, list)
    assert len(flavors) > 0
    assert "name" in flavors[0]
    
    # Test keys getter
    keys = provider.get_keys()
    assert isinstance(keys, list)
    assert "name" in keys[0]
    
    # Test security groups getter
    sg = provider.get_security_groups()
    assert isinstance(sg, list)
    assert "name" in sg[0]
