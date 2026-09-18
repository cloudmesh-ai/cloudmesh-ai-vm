import pytest
from unittest.mock import patch, MagicMock
import subprocess
from src.local.VBoxManager import Provider

@pytest.fixture
def mock_config():
    return {"clouds": {"vbox": {}}}

@pytest.fixture
def provider(mock_config):
    return Provider(mock_config)

def test_start_success(provider):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="Started", returncode=0)
        assert provider.start(name="vbox-vm") == "vbox-vm"
        mock_run.assert_called_once_with(["VBoxManage", "startvm", "vbox-vm", "--type", "headless"], capture_output=True, text=True, check=True)

def test_stop_success(provider):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="Stopped", returncode=0)
        assert provider.stop(name="vbox-vm") is True
        mock_run.assert_called_once_with(["VBoxManage", "controlvm", "vbox-vm", "poweroff"], capture_output=True, text=True, check=True)

def test_delete_success(provider):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="Deleted", returncode=0)
        assert provider.delete(name="vbox-vm") is True
        mock_run.assert_called_once_with(["VBoxManage", "unregistervm", "vbox-vm", "--delete"], capture_output=True, text=True, check=True)

def test_list_parsing(provider):
    mock_output = (
        '"VM 1" {uuid1}\n'
        '"VM 2" {uuid2}\n'
    )
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout=mock_output, returncode=0)
        vms = provider.list()
        assert len(vms) == 2
        assert vms[0]["Name"] == "VM 1"
        assert vms[0]["UUID"] == "uuid1"
        assert vms[1]["Name"] == "VM 2"
        assert vms[1]["UUID"] == "uuid2"

def test_suspend_success(provider):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="Suspended", returncode=0)
        assert provider.suspend(name="vbox-vm") is True
        mock_run.assert_called_once_with(["VBoxManage", "controlvm", "vbox-vm", "savestate"], capture_output=True, text=True, check=True)

def test_restart_success(provider):
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(stdout="Success", returncode=0)
        assert provider.restart(name="vbox-vm") is True
        assert mock_run.call_count == 2
        mock_run.assert_any_call(["VBoxManage", "controlvm", "vbox-vm", "poweroff"], capture_output=True, text=True, check=True)
        mock_run.assert_any_call(["VBoxManage", "startvm", "vbox-vm", "--type", "headless"], capture_output=True, text=True, check=True)
