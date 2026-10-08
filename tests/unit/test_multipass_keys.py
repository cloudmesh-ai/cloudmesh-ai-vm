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

def test_upload_and_delete_key_use_key_name(provider, tmp_path):
    pub = tmp_path / "id.pub"
    pub.write_text("ssh-ed25519 AAAAC3Nza someone@laptop\n")

    assert provider.upload_key(str(pub), "smoke-key", "test-vm") is True
    upload_cmd = provider._run_command.call_args.args[0][-1]
    assert "ssh-ed25519 AAAAC3Nza someone@laptop smoke-key" in upload_cmd

    assert provider.delete_key("smoke-key", "test-vm") is True
    delete_cmd = provider._run_command.call_args.args[0][-1]
    assert "-v n=smoke-key" in delete_cmd
