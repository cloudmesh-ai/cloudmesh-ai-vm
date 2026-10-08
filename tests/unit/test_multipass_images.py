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

def test_get_images_uses_find(provider):
    provider._run_command.return_value = MagicMock(stdout=(
        '{"errors": [], "images": {'
        '"22.04": {"aliases": ["jammy"], "os": "Ubuntu", "release": "22.04 LTS", "remote": "", "version": "20261004"},'
        '"24.04": {"aliases": ["noble"], "os": "Ubuntu", "release": "24.04 LTS", "remote": "", "version": "20260926"}}}'
    ))
    images = provider.get_images()
    provider._run_command.assert_called_once_with(["multipass", "find", "--format", "json"], stream=False)
    assert [i["name"] for i in images] == ["22.04", "24.04"]
    assert images[0]["aliases"] == "jammy"
