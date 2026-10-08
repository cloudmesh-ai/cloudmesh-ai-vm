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

def test_unshelve_starts_existing_vm(provider):
    mock_list_result = MagicMock(stdout="Name State IPv4 Image\ntest-vm Stopped -- Ubuntu 22.04 LTS\n")

    def side_effect(command, **kwargs):
        if command == ["multipass", "list"]:
            return mock_list_result
        return MagicMock()

    provider._run_command.side_effect = side_effect

    assert provider.unshelve(name="test-vm") is True
    provider._run_command.assert_any_call(["multipass", "start", "test-vm"])
    launched = [c for c in provider._run_command.call_args_list if c.args[0][:2] == ["multipass", "launch"]]
    assert not launched

def test_unshelve_missing_vm(provider):
    provider._run_command.return_value = MagicMock(stdout="Name State IPv4 Image\n")
    with pytest.raises(VMResourceError):
        provider.unshelve(name="missing-vm")
