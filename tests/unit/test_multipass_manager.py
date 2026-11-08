import re
from unittest.mock import MagicMock
import shlex

import pytest

from cloudmesh.ai.vm.local.MultipassManager import Provider


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
    p._run_command = MagicMock()
    return p


def test_start_with_name_and_config(provider):
    vm_name = "test-vm"
    result = provider.start(name=vm_name)

    # Verify the command constructed
    expected_command = [
        "multipass",
        "launch",
        "-c",
        "2",
        "-m",
        "4GiB",
        "-d",
        "20GiB",
        "-n",
        vm_name,
        "22.04",
    ]
    provider._run_command.assert_any_call(expected_command, stream=True)
    assert result == vm_name


def test_start_without_name_exists(provider):
    # Mock Multipass list output for exists()
    def side_effect(command, **kwargs):
        if command == [
            "multipass",
            "list",
            "--format",
            "json",
        ]:
            return MagicMock(stdout='{"list": []}', returncode=0)

        if command[0:2] == ["multipass", "launch"]:
            return MagicMock(stdout="Launched: test-vm", returncode=0)

        return MagicMock(stdout="", returncode=0)

    provider._run_command.side_effect = side_effect

    vm_name = "test-vm"
    result = provider.start(name=vm_name)

    expected_command = [
        "multipass",
        "launch",
        "-c",
        "2",
        "-m",
        "4GiB",
        "-d",
        "20GiB",
        "-n",
        vm_name,
        "22.04",
    ]

    provider._run_command.assert_any_call(
        expected_command,
        stream=True,
    )

    assert result == vm_name


def test_start_without_name_generated(provider):
    def side_effect(command, **kwargs):
        if command[0:2] == ["multipass", "launch"]:
            return MagicMock(stdout="Launched: generated-vm", returncode=0)

        return MagicMock(stdout="", returncode=0)

    provider._run_command.side_effect = side_effect

    result = provider.start()

    expected_command = [
        "multipass",
        "launch",
        "-c",
        "2",
        "-m",
        "4GiB",
        "-d",
        "20GiB",
        "22.04",
    ]
    provider._run_command.assert_any_call(expected_command, stream=True)
    assert result == "generated-vm"


def test_stop_success(provider):
    # Mock Multipass list output for exists()
    def side_effect(command, **kwargs):
        if command == [
            "multipass",
            "list",
            "--format",
            "json",
        ]:
            return MagicMock(
                stdout='{"list": [{"name": "test-vm"}]}', returncode=0
            )
        return MagicMock(stdout="Stopped", returncode=0)

    provider._run_command.side_effect = side_effect

    assert provider.stop(name="test-vm") is True
    provider._run_command.assert_any_call(["multipass", "stop", "test-vm"])


def test_restart_success(provider):
    def side_effect(command, **kwargs):
        if command == [
            "multipass",
            "list",
            "--format",
            "json",
        ]:
            return MagicMock(
                stdout='{"list": [{"name": "test-vm"}]}', returncode=0
            )
        return MagicMock(stdout="OK", returncode=0)

    provider._run_command.side_effect = side_effect

    assert provider.restart(name="test-vm") is True

    provider._run_command.assert_any_call(
        ["multipass", "stop", "test-vm"]
    )

    provider._run_command.assert_any_call(
        ["multipass", "start", "test-vm"]
    )


def test_getters(provider):
    provider._run_command.return_value = MagicMock(
        stdout='[{"name": "default"}]', returncode=0
    )
    
    flavors = provider.get_flavors()
    assert isinstance(flavors, list)
    
    keys = provider.get_keys()
    assert isinstance(keys, list)
    
    security_groups = provider.get_security_groups()
    assert isinstance(security_groups, list)
    assert security_groups[0]["name"] == "default"


def test_upload_key_escaping(provider, tmp_path):
    # Create a dummy public key file with a single quote
    key_content = "ssh-rsa AAAAB3Nza... 'quote' ... user@host"
    key_file = tmp_path / "id_rsa.pub"
    key_file.write_text(key_content)

    key_name = "my'key'name"
    vm_name = "test-vm"

    assert (
        provider.upload_key(
            str(key_file),
            key_name,
            vm_name,
        )
        is True
    )

    # Compute the combined key entry and safely quote it using shlex.quote
    combined = f'{key_content} # {key_name}'
    escaped_entry = shlex.quote(combined)

    expected_cmd_part = (
        "mkdir -p ~/.ssh && chmod 700 ~/.ssh && printf '%s\n' "
        f"{escaped_entry} "
        ">> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
    )

    provider._run_command.assert_called_with(
        [
            "multipass",
            "exec",
            vm_name,
            "--",
            "bash",
            "-c",
            expected_cmd_part,
        ]
    )
def test_delete_key_escaping(provider):
    key_name = "my/key'name"
    vm_name = "test-vm"

    assert (
        provider.delete_key(
            key_name,
            vm_name,
        )
        is True
    )

    # The implementation now uses a portable grep‑based deletion. The key name
    # is passed as a separate argument to ``bash -c`` and referenced via $1.
    escaped_key = shlex.quote(key_name)

    expected_cmd = [
        "multipass",
        "exec",
        vm_name,
        "--",
        "bash",
        "-c",
        'grep -vF "$1" ~/.ssh/authorized_keys > ~/.ssh/authorized_keys.tmp && mv ~/.ssh/authorized_keys.tmp ~/.ssh/authorized_keys',
        "bash",
        escaped_key,
    ]

    provider._run_command.assert_called_with(expected_cmd)
