import pytest
from unittest.mock import patch, MagicMock
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
    """Fixture that provides a Provider instance with _run_command mocked."""
    with patch.object(Provider, "_run_command") as mock_run:
        # Mock return value for _verify_installation in __init__
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        provider = Provider(mock_config)
        # Reset mock to clear the call from __init__
        mock_run.reset_mock()
        # Assign the mock to the instance for easy access in tests
        provider._run_command = mock_run
        yield provider

def test_init_success():
    with patch.object(Provider, "_run_command") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        config = {"clouds": {}}
        p = Provider(config)
        mock_run.assert_called_once_with(["limactl", "--version"])

def test_init_failure():
    with patch.object(Provider, "_run_command") as mock_run:
        mock_run.side_effect = Exception("limactl not found")
        config = {"clouds": {}}
        with pytest.raises(VMProviderError, match="limactl not found"):
            Provider(config)

def test_start_with_name(provider):
    vm_name = "test-vm"
    provider._run_command.return_value = MagicMock(returncode=0, stdout="Started")

    result = provider.start(name=vm_name)

    assert result == vm_name
    provider._run_command.assert_called_with(
        ["limactl", "start", "--name", vm_name, "--tty=false", "template:ubuntu"],
        stream=True
    )

def test_start_default_name(provider):
    provider._run_command.return_value = MagicMock(returncode=0, stdout="Started")

    result = provider.start()

    assert result == "lima-vm"
    provider._run_command.assert_called_with(
        ["limactl", "start", "--name", "lima-vm", "--tty=false", "template:ubuntu"],
        stream=True
    )

def test_stop_success(provider):
    def side_effect(command, **kwargs):
        if command == ["limactl", "list"]:
            return MagicMock(returncode=0, stdout="NAME STATUS IMAGE\ntest-vm Running ubuntu\n")
        return MagicMock(returncode=0, stdout="Stopped")

    provider._run_command.side_effect = side_effect

    assert provider.stop(name="test-vm") is True
    provider._run_command.assert_any_call(["limactl", "stop", "test-vm"])

def test_delete_success(provider):
    def side_effect(command, **kwargs):
        if command == ["limactl", "list"]:
            return MagicMock(returncode=0, stdout="NAME STATUS IMAGE\ntest-vm Running ubuntu\n")
        return MagicMock(returncode=0, stdout="Deleted")

    provider._run_command.side_effect = side_effect

    assert provider.delete(name="test-vm") is True
    provider._run_command.assert_any_call(
        ["limactl", "delete", "-f", "test-vm"],
        stream=True
    )

def test_list_parsing(provider):
    mock_output = (
        "NAME              STATUS    IMAGE\n"
        "vm-1              Running   ubuntu\n"
        "vm-2              Stopped   fedora\n"
    )
    provider._run_command.return_value = MagicMock(
        stdout=mock_output,
        returncode=0
    )

    vms = provider.list()

    assert len(vms) == 2
    assert vms[0]["name"] == "vm-1"
    assert vms[0]["status"] == "Running"
    assert vms[1]["name"] == "vm-2"
    assert vms[1]["status"] == "Stopped"

def test_login(provider):
    def side_effect(command, **kwargs):
        if command == ["limactl", "list"]:
            return MagicMock(returncode=0, stdout="NAME STATUS IMAGE\ntest-vm Running ubuntu\n")
        return MagicMock(returncode=0, stdout="Shell")

    provider._run_command.side_effect = side_effect
    assert provider.login(name="test-vm") is True
    provider._run_command.assert_any_call(["limactl", "shell", "test-vm"])

def test_restart(provider):
    def side_effect(command, **kwargs):
        if command == ["limactl", "list"]:
            return MagicMock(returncode=0, stdout="NAME STATUS IMAGE\ntest-vm Running ubuntu\n")
        return MagicMock(returncode=0, stdout="Success")

    provider._run_command.side_effect = side_effect

    assert provider.restart(name="test-vm") is True
    provider._run_command.assert_any_call(["limactl", "stop", "test-vm"])
    provider._run_command.assert_any_call(["limactl", "start", "test-vm"])

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
