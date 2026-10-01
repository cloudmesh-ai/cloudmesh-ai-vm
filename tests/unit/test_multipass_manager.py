import json
import subprocess
from unittest.mock import Mock
import pytest
from cloudmesh.ai.vm.local.MultipassManager import Provider


@pytest.fixture
def provider():
    return Provider({"clouds": {"multipass": {
        "image": "24.04", "cpus": 2, "memory": "2G", "disk": "10G"
    }}})


def json_result(data):
    return subprocess.CompletedProcess([], 0, stdout=json.dumps(data), stderr="")


def test_new_vm_uses_configured_resources(provider, monkeypatch):
    monkeypatch.setattr(provider, "_run_command_silent", Mock(return_value=json_result({"list": []})))
    launch = Mock()
    monkeypatch.setattr(provider, "_run_interactive", launch)
    assert provider.start("test-vm") == "test-vm"
    launch.assert_called_once_with([
        "multipass", "launch", "-c", "2", "-m", "2G", "-d", "10G", "-n", "test-vm", "24.04"
    ])


@pytest.mark.parametrize("status", ["Stopped", "Suspended", "STOPPED"])
def test_existing_vm_resumes_without_launch(provider, monkeypatch, status):
    monkeypatch.setattr(provider, "list", Mock(return_value=[{"name": "test-vm", "status": status}]))
    command = Mock()
    monkeypatch.setattr(provider, "_run_interactive", command)
    assert provider.start("test-vm") == "test-vm"
    command.assert_called_once_with(["multipass", "start", "test-vm"])


def test_running_vm_is_not_launched_again(provider, monkeypatch):
    monkeypatch.setattr(provider, "list", Mock(return_value=[{"name": "test-vm", "status": "Running"}]))
    command = Mock()
    monkeypatch.setattr(provider, "_run_interactive", command)
    assert provider.start("test-vm") == "test-vm"
    command.assert_not_called()


@pytest.mark.parametrize("status", ["Deleted", "Starting", "Unknown"])
def test_unavailable_vm_is_not_replaced(provider, monkeypatch, status):
    monkeypatch.setattr(provider, "list", Mock(return_value=[{"name": "test-vm", "status": status}]))
    command = Mock()
    monkeypatch.setattr(provider, "_run_interactive", command)
    with pytest.raises(ValueError):
        provider.start("test-vm")
    command.assert_not_called()


def test_inventory_failure_prevents_launch(provider, monkeypatch):
    monkeypatch.setattr(provider, "list", Mock(side_effect=subprocess.CalledProcessError(1, ["multipass", "list"])))
    command = Mock()
    monkeypatch.setattr(provider, "_run_interactive", command)
    with pytest.raises(subprocess.CalledProcessError):
        provider.start("test-vm")
    command.assert_not_called()


def test_info_normalizes_state_and_preserves_details(provider, monkeypatch):
    query = Mock(return_value=json_result({"errors": [], "info": {
        "test-vm": {"state": "Running", "ipv4": ["", "192.0.2.1", "192.0.2.2"],
                    "release": "Ubuntu 24.04 LTS", "cpu_count": 2}
    }}))
    monkeypatch.setattr(provider, "_run_command_silent", query)
    result = provider.info("test-vm")
    assert (result["name"], result["status"], result["ip"]) == ("test-vm", "Running", "192.0.2.1")
    assert result["cpu_count"] == 2
    query.assert_called_once_with(["multipass", "info", "test-vm", "--format", "json"])


def test_missing_info_is_an_error(provider, monkeypatch):
    monkeypatch.setattr(provider, "_run_command_silent", Mock(return_value=json_result({"info": {}})))
    with pytest.raises(ValueError, match="No information"):
        provider.info("missing")


def test_list_preserves_multiple_addresses_and_stopped_instances(provider, monkeypatch):
    query = Mock(return_value=json_result({"list": [
        {"name": "vm-1", "state": "Running", "ipv4": ["192.0.2.1", "192.0.2.2"], "release": "24.04 LTS"},
        {"name": "vm-2", "state": "Stopped", "ipv4": []}
    ]}))
    monkeypatch.setattr(provider, "_run_command_silent", query)
    first, second = provider.list()
    assert first["ipv4"] == ["192.0.2.1", "192.0.2.2"]
    assert second["ip"] is None and second["status"] == "Stopped"
    query.assert_called_once_with(["multipass", "list", "--format", "json"])


@pytest.mark.parametrize("data", [[], {}, {"list": {}}])
def test_malformed_inventory_is_not_reported_as_empty(provider, monkeypatch, data):
    monkeypatch.setattr(provider, "_run_command_silent", Mock(return_value=json_result(data)))
    with pytest.raises(ValueError):
        provider.list()


def test_daemon_error_is_not_reported_as_empty(provider, monkeypatch):
    monkeypatch.setattr(provider, "_run_command_silent", Mock(return_value=json_result({
        "errors": ["daemon unavailable"], "list": []
    })))
    with pytest.raises(RuntimeError, match="daemon unavailable"):
        provider.list()


def test_subprocess_failure_is_propagated(provider, monkeypatch):
    run = Mock(side_effect=subprocess.CalledProcessError(7, ["multipass", "list"]))
    monkeypatch.setattr(subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        provider._run_command_silent(["multipass", "list"])
    run.assert_called_once_with(["multipass", "list"], capture_output=True, text=True, check=True)


@pytest.mark.parametrize("output", ["", "[bold]literal text\n", "test-vm\n"])
def test_guest_command_preserves_output_and_runs_only_in_guest(provider, monkeypatch, output):
    command = "printf '%s' 'hello world' | cat"
    run = Mock(return_value=subprocess.CompletedProcess([], 0, stdout=output))
    monkeypatch.setattr(provider, "_run_command_silent", run)
    assert provider.run_command("test-vm", command) == output
    run.assert_called_once_with(["multipass", "exec", "test-vm", "--", "sh", "-lc", command])


def test_guest_command_failure_is_propagated(provider, monkeypatch):
    monkeypatch.setattr(provider, "_run_command_silent", Mock(
        side_effect=subprocess.CalledProcessError(1, ["multipass", "exec"])))
    with pytest.raises(subprocess.CalledProcessError):
        provider.run_command("test-vm", "false")


@pytest.mark.parametrize("method,arguments", [
    ("stop", ["stop", "test-vm"]),
    ("delete", ["delete", "--purge", "test-vm"]),
    ("restart", ["restart", "test-vm"]),
    ("suspend", ["suspend", "test-vm"]),
])
def test_lifecycle_targets_only_requested_vm(provider, monkeypatch, method, arguments):
    run = Mock()
    monkeypatch.setattr(provider, "_run_command", run)
    assert getattr(provider, method)("test-vm") is True
    run.assert_called_once_with(["multipass", *arguments])


@pytest.mark.parametrize("method", ["stop", "delete", "restart", "suspend"])
def test_failed_lifecycle_returns_failure(provider, monkeypatch, method):
    monkeypatch.setattr(provider, "_run_command", Mock(
        side_effect=subprocess.CalledProcessError(1, ["multipass", method])))
    assert getattr(provider, method)("test-vm") is False


def test_login_uses_managed_shell(provider, monkeypatch):
    run = Mock()
    monkeypatch.setattr(provider, "_run_interactive", run)
    assert provider.login("test-vm") is True
    run.assert_called_once_with(["multipass", "shell", "test-vm"])


def test_images_use_find_not_nonexistent_images_command(provider, monkeypatch):
    query = Mock(return_value=json_result({"images": {
        "24.04": {"release": "noble", "aliases": ["noble"]}
    }}))
    monkeypatch.setattr(provider, "_run_command_silent", query)
    assert provider.get_images()[0]["name"] == "24.04"
    query.assert_called_once_with(["multipass", "find", "--format", "json"])


def test_local_resource_inventory_does_not_fabricate_keys_or_security_groups(provider):
    assert provider.get_keys() == []
    assert provider.get_security_groups() == []


def test_provider_info_does_not_hide_subprocess_failure(provider, monkeypatch):
    monkeypatch.setattr(provider, "_run_command_silent", Mock(
        side_effect=subprocess.CalledProcessError(1, ["multipass", "version"])))
    with pytest.raises(subprocess.CalledProcessError):
        provider.get_provider_info()


def test_provider_info_requires_version_output(provider, monkeypatch):
    monkeypatch.setattr(provider, "_run_command_silent", Mock(
        return_value=subprocess.CompletedProcess([], 0, stdout="")))
    with pytest.raises(ValueError, match="version information"):
        provider.get_provider_info()
