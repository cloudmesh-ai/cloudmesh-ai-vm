import pytest
from unittest.mock import patch, MagicMock
import subprocess
from cloudmesh.ai.vm.local.Wsl2Manager import Provider

@pytest.fixture
def mock_config():
    return {
        "clouds": {
            "wsl2": {
                "rootfs": "/path/to/rootfs.tar",
                "install_dir": "C:\\WSL",
                "wsl_username": "wsluser",
                "host_username": "winuser"
            }
        }
    }

@pytest.fixture
def provider(mock_config):
    provider = Provider(mock_config)
    provider._get_wsl_binary = MagicMock(return_value="wsl")
    provider._run_command = MagicMock()
    return provider

def test_start_existing(provider):
    with patch.object(provider, "exists", return_value=True):
        provider._run_command.return_value = MagicMock(stdout="Started", returncode=0)

        result = provider.start(name="Ubuntu-22.04")

        assert result == "Ubuntu-22.04"
        provider._run_command.assert_called_once_with(
            ["wsl", "-d", "Ubuntu-22.04"]
        )

def test_start_import(provider):
    # First call to list distros (not found), second to import, third to start
    provider._run_command.side_effect = [
        MagicMock(stdout="OtherDistro\n", returncode=0),
        MagicMock(stdout="Imported", returncode=0),
        MagicMock(stdout="Started", returncode=0)
    ]

    result = provider.start(name="NewDistro")

    assert result == "NewDistro"
    provider._run_command.assert_any_call(["wsl", "--import", "NewDistro", "C:\\WSL", "/path/to/rootfs.tar"])
    provider._run_command.assert_any_call(["wsl", "-d", "NewDistro"])

def test_stop_success(provider):
    with patch.object(provider, "exists", return_value=True):
        provider._run_command.return_value = MagicMock(stdout="Stopped", returncode=0)
        assert provider.stop(name="test-distro") is True
        provider._run_command.assert_called_once_with(["wsl", "--terminate", "test-distro"])

def test_delete_success(provider):
    with patch.object(provider, "exists", return_value=True):
        provider._run_command.return_value = MagicMock(stdout="Deleted", returncode=0)
        assert provider.delete(name="test-distro") is True
        provider._run_command.assert_called_once_with(["wsl", "--unregister", "test-distro"])

def test_list_parsing(provider):
    mock_output = (
        "Name            State           Version\n"
        "Ubuntu          Running         2\n"
        "Debian          Stopped         2\n"
    )
    provider._run_command.return_value = MagicMock(stdout=mock_output, returncode=0)
    vms = provider.list()
    assert len(vms) == 2
    assert vms[0]["Name"] == "Ubuntu"
    assert vms[0]["State"] == "Running"
    assert vms[1]["Name"] == "Debian"

def test_login(provider):
    provider._run_command.return_value = MagicMock(returncode=0)
    assert provider.login(name="test-distro") is True
    provider._run_command.assert_called_once_with(["wsl", "-d", "test-distro"], stream=True)

def test_link_ssh_dir_success(provider):
    with patch.object(provider, "exists", return_value=True):
        provider._run_command.return_value = MagicMock(stdout="Linked", returncode=0)
        assert provider.link_ssh_dir(name="test-distro") is True

        expected_cmd = "rm -rf /home/wsluser/.ssh && ln -s /mnt/c/Users/winuser/.ssh /home/wsluser/.ssh"
        provider._run_command.assert_called_once_with(["wsl", "-d", "test-distro", "-u", "root", "sh", "-c", expected_cmd])

def test_link_ssh_dir_missing_config(provider):
    provider.config = {"clouds": {"wsl2": {}}} # Empty config
    assert provider.link_ssh_dir(name="test-distro") is False
