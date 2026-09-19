import pytest
from unittest.mock import patch, MagicMock
import subprocess
from cloudmesh.ai.vm.local.MultipassManager import Provider

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

def get_provider():
    return Provider(mock_config())

def test_start_with_name_and_config():
    provider = get_provider()
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout = iter(["Success\n"])
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        vm_name = "test-vm"
        result = provider.start(name=vm_name)
        
        expected_command = ["multipass", "launch", "-c", "2", "-m", "4GiB", "-d", "20GiB", "-n", vm_name, "22.04"]
        mock_popen.assert_called_once_with(
            expected_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        assert result == vm_name
    print("test_start_with_name_and_config passed")

def test_start_without_name():
    provider = get_provider()
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout = iter(["Success\n"])
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        result = provider.start()
        
        expected_command = ["multipass", "launch", "-c", "2", "-m", "4GiB", "-d", "20GiB", "22.04"]
        mock_popen.assert_called_once_with(
            expected_command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        assert result == "multipass-generated"
    print("test_start_without_name passed")

def test_stop_success():
    provider = get_provider()
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout = iter(["Stopped\n"])
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        assert provider.stop(name="test-vm") is True
        mock_popen.assert_called_once_with(
            ["multipass", "stop", "test-vm"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
    print("test_stop_success passed")

def test_stop_failure():
    provider = get_provider()
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout = iter(["VM not found\n"])
        mock_process.returncode = 1
        mock_popen.return_value = mock_process
        
        assert provider.stop(name="non-existent") is False
    print("test_stop_failure passed")

def test_delete_success():
    provider = get_provider()
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout = iter(["Deleted\n"])
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        assert provider.delete(name="test-vm") is True
        assert mock_popen.call_count == 2
    print("test_delete_success passed")

def test_list_parsing():
    provider = get_provider()
    mock_output = (
        "Name                    State             IPv4             Image\n"
        "vm-1                    Running           192.168.64.5     Ubuntu 22.04 LTS\n"
        "vm-2                    Stopped           192.168.64.6     Ubuntu 22.04 LTS\n"
    )
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout = iter(mock_output.splitlines(keepends=True))
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        vms = provider.list()
        
        assert len(vms) == 2
        assert vms[0]["Name"] == "vm-1"
        assert vms[0]["State"] == "Running"
        assert vms[1]["Name"] == "vm-2"
        assert vms[1]["State"] == "Stopped"
    print("test_list_parsing passed")

def test_restart_success():
    provider = get_provider()
    with patch("subprocess.Popen") as mock_popen:
        mock_process = MagicMock()
        mock_process.stdout = iter(["Success\n"])
        mock_process.returncode = 0
        mock_popen.return_value = mock_process
        
        assert provider.restart(name="test-vm") is True
        assert mock_popen.call_count == 2
    print("test_restart_success passed")

def test_getters():
    provider = get_provider()
    flavors = provider.get_flavors()
    assert isinstance(flavors, list)
    assert len(flavors) > 0
    assert "name" in flavors[0]
    
    keys = provider.get_keys()
    assert isinstance(keys, list)
    assert "name" in keys[0]
    
    sg = provider.get_security_groups()
    assert isinstance(sg, list)
    assert "name" in sg[0]
    print("test_getters passed")

if __name__ == "__main__":
    tests = [
        test_start_with_name_and_config,
        test_start_without_name,
        test_stop_success,
        test_stop_failure,
        test_delete_success,
        test_list_parsing,
        test_restart_success,
        test_getters,
    ]
    
    for test in tests:
        try:
            test()
        except Exception as e:
            print(f"{test.__name__} failed: {e}")
            import traceback
            traceback.print_exc()
            exit(1)
    print("All tests passed!")
