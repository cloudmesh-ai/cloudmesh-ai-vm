import pytest
from unittest.mock import MagicMock
from cloudmesh.ai.vm.local.MultipassManager import Provider
from cloudmesh.ai.vm.exceptions import VMResourceError

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
    p = Provider(mock_config)
    p._run_command = MagicMock()
    return p

def test_start_with_name_and_config(provider):
    vm_name = "test-vm"
    result = provider.start(name=vm_name)

    # Verify the command constructed
    expected_command = ["multipass", "launch", "-c", "2", "-m", "4GiB", "-d", "20GiB", "-n", vm_name, "22.04"]
    provider._run_command.assert_called_once_with(
        expected_command,
        stream=True
    )
    assert result == vm_name

def test_start_without_name(provider):
    result = provider.start()

    expected_command = ["multipass", "launch", "-c", "2", "-m", "4GiB", "-d", "20GiB", "22.04"]
    provider._run_command.assert_called_once_with(
        expected_command,
        stream=True
    )
    assert result == "multipass-generated"

def test_stop_success(provider):
    # Mock Multipass list output for exists()
    mock_list_result = MagicMock(stdout="Name State IPv4 Image\ntest-vm Running 192.168.64.5 Ubuntu 22.04 LTS\n")

    def side_effect(command, **kwargs):
        if command == ["multipass", "list"]:
            return mock_list_result
        return MagicMock()

    provider._run_command.side_effect = side_effect

    assert provider.stop(name="test-vm") is True
    provider._run_command.assert_any_call(["multipass", "stop", "test-vm"])

def test_stop_failure(provider):
    # Mock Multipass list output to be empty so exists() returns False
    mock_list_result = MagicMock(stdout="Name State IPv4 Image\n")

    def side_effect(command, **kwargs):
        if command == ["multipass", "list"]:
            return mock_list_result
        return MagicMock()

    provider._run_command.side_effect = side_effect

    with pytest.raises(VMResourceError):
        provider.stop(name="non-existent")

def test_delete_success(provider):
    # Mock Multipass list output for exists()
    mock_list_result = MagicMock(stdout="Name State IPv4 Image\ntest-vm Running 192.168.64.5 Ubuntu 22.04 LTS\n")

    def side_effect(command, **kwargs):
        if command == ["multipass", "list"]:
            return mock_list_result
        return MagicMock()

    provider._run_command.side_effect = side_effect

    assert provider.delete(name="test-vm") is True
    provider._run_command.assert_any_call(["multipass", "delete", "test-vm"])
    provider._run_command.assert_any_call(["multipass", "purge"])

def test_list_parsing(provider):
    # Mock Multipass output
    mock_output = (
        "Name                    State             IPv4             Image\n"
        "vm-1                    Running           192.168.64.5     Ubuntu 22.04 LTS\n"
        "vm-2                    Stopped           192.168.64.6     Ubuntu 22.04 LTS\n"
    )
    provider._run_command.return_value = MagicMock(stdout=mock_output)

    vms = provider.list()

    assert len(vms) == 2
    assert vms[0]["name"] == "vm-1"
    assert vms[0]["status"] == "Running"
    assert vms[1]["name"] == "vm-2"
    assert vms[1]["status"] == "Stopped"

def test_restart_success(provider):
    # Mock Multipass list output for exists()
    mock_list_result = MagicMock(stdout="Name State IPv4 Image\ntest-vm Running 192.168.64.5 Ubuntu 22.04 LTS\n")

    def side_effect(command, **kwargs):
        if command == ["multipass", "list"]:
            return mock_list_result
        return MagicMock()

    provider._run_command.side_effect = side_effect

    assert provider.restart(name="test-vm") is True
    provider._run_command.assert_any_call(["multipass", "stop", "test-vm"])
    provider._run_command.assert_any_call(["multipass", "start", "test-vm"])

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
