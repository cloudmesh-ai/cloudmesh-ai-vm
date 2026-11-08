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
                "disk": "20GiB",
            }
        }
    }


@pytest.fixture
def provider(mock_config):
    p = Provider(mock_config)
    # Replace external command execution with a mock.
    p._run_command = MagicMock()
    return p


def test_suspend_success(provider):
    # Mock existence check.
    provider.exists = MagicMock(return_value=True)
    # Ensure _run_command returns a successful result.
    provider._run_command.return_value = MagicMock(stdout="Suspended", returncode=0)

    assert provider.suspend(name="test-vm") is True
    provider._run_command.assert_called_with(["multipass", "suspend", "test-vm"])


def test_suspend_missing_vm(provider):
    provider.exists = MagicMock(return_value=False)
    with pytest.raises(VMResourceError):
        provider.suspend(name="nonexistent")


def test_suspend_default_resolution(provider):
    # Simulate default VM resolution.
    provider._get_default_vm = MagicMock(return_value="default-vm")
    provider.exists = MagicMock(return_value=True)
    provider._run_command.return_value = MagicMock(stdout="Suspended", returncode=0)

    assert provider.suspend() is True
    provider._run_command.assert_called_with(["multipass", "suspend", "default-vm"])
