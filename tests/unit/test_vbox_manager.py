import pytest
from unittest.mock import MagicMock
from cloudmesh.ai.vm.local.VBoxManager import Provider

@pytest.fixture
def mock_config():
    return {"clouds": {"vbox": {}}}

@pytest.fixture
def provider(mock_config):
    p = Provider(mock_config)
    p._run_command = MagicMock()
    return p

def test_start_success(provider):
    # 1. For exists() -> list(), 2. For start()
    provider._run_command.side_effect = [
        MagicMock(stdout='"vbox-vm" {uuid1}\n', returncode=0),
        MagicMock(stdout="Started", returncode=0)
    ]
    assert provider.start(name="vbox-vm") == "vbox-vm"
    assert provider._run_command.call_count == 2
    provider._run_command.assert_any_call(["VBoxManage", "list", "vms"])
    provider._run_command.assert_any_call(["VBoxManage", "startvm", "vbox-vm", "--type", "headless"])

def test_stop_success(provider):
    # 1. For exists() -> list(), 2. For stop()
    provider._run_command.side_effect = [
        MagicMock(stdout='"vbox-vm" {uuid1}\n', returncode=0),
        MagicMock(stdout="Stopped", returncode=0)
    ]
    assert provider.stop(name="vbox-vm") is True
    assert provider._run_command.call_count == 2
    provider._run_command.assert_any_call(["VBoxManage", "list", "vms"])
    provider._run_command.assert_any_call(["VBoxManage", "controlvm", "vbox-vm", "poweroff"])

def test_delete_success(provider):
    # 1. For exists() -> list(), 2. For delete()
    provider._run_command.side_effect = [
        MagicMock(stdout='"vbox-vm" {uuid1}\n', returncode=0),
        MagicMock(stdout="Deleted", returncode=0)
    ]
    assert provider.delete(name="vbox-vm") is True
    assert provider._run_command.call_count == 2
    provider._run_command.assert_any_call(["VBoxManage", "list", "vms"])
    provider._run_command.assert_any_call(["VBoxManage", "unregistervm", "vbox-vm", "--delete"])

def test_list_parsing(provider):
    mock_output = (
        '"VM 1" {uuid1}\n'
        '"VM 2" {uuid2}\n'
    )
    provider._run_command.return_value = MagicMock(stdout=mock_output, returncode=0)
    vms = provider.list()
    assert len(vms) == 2
    assert vms[0]["Name"] == "VM 1"
    assert vms[0]["UUID"] == "uuid1"
    assert vms[1]["Name"] == "VM 2"
    assert vms[1]["UUID"] == "uuid2"
    provider._run_command.assert_called_once_with(["VBoxManage", "list", "vms"])

def test_suspend_success(provider):
    # 1. For exists() -> list(), 2. For suspend()
    provider._run_command.side_effect = [
        MagicMock(stdout='"vbox-vm" {uuid1}\n', returncode=0),
        MagicMock(stdout="Suspended", returncode=0)
    ]
    assert provider.suspend(name="vbox-vm") is True
    assert provider._run_command.call_count == 2
    provider._run_command.assert_any_call(["VBoxManage", "list", "vms"])
    provider._run_command.assert_any_call(["VBoxManage", "controlvm", "vbox-vm", "savestate"])

def test_restart_success(provider):
    # 1. For stop.exists() -> list()
    # 2. For stop()
    # 3. For start.exists() -> list()
    # 4. For start()
    provider._run_command.side_effect = [
        MagicMock(stdout='"vbox-vm" {uuid1}\n', returncode=0),
        MagicMock(stdout="Stopped", returncode=0),
        MagicMock(stdout='"vbox-vm" {uuid1}\n', returncode=0),
        MagicMock(stdout="Started", returncode=0)
    ]
    assert provider.restart(name="vbox-vm") is True
    assert provider._run_command.call_count == 4
    provider._run_command.assert_any_call(["VBoxManage", "controlvm", "vbox-vm", "poweroff"])
    provider._run_command.assert_any_call(["VBoxManage", "startvm", "vbox-vm", "--type", "headless"])
