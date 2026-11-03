"""Regression tests for VM SSH command failure handling."""

import subprocess
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from cloudmesh.ai.command.vm import cmx


def test_ssh_nonzero_exit_code_is_reported_as_failure():
    """An SSH process returning a nonzero exit code must fail the CLI."""
    provider = MagicMock()
    provider.cloud_name = "test-openstack"
    provider.info.return_value = {"ip": "192.0.2.10"}

    cloud_config = {
        "key_path": "/tmp/test-private-key",
        "user": "ubuntu",
    }

    with (
        patch(
            "cloudmesh.ai.command.vm.ssh.get_active_provider",
            return_value=provider,
        ),
        patch(
            "cloudmesh.ai.command.vm.ssh.resolve_vm_name",
            return_value="test-vm",
        ),
        patch(
            "cloudmesh.ai.command._shared.context.state.config.get_cloud_config",
            return_value=cloud_config,
        ),
        patch(
            "cloudmesh.ai.command.vm.ssh.subprocess.run",
            return_value=subprocess.CompletedProcess(
                args=["ssh"],
                returncode=255,
            ),
        ) as mock_run,
    ):
        result = CliRunner().invoke(cmx, ["vm", "ssh", "test-vm"])

    mock_run.assert_called_once()
    assert result.exit_code != 0
    assert "/tmp/test-private-key" not in result.output


def test_ssh_called_process_error_does_not_expose_private_key():
    """SSH subprocess exceptions must not reveal sensitive command arguments."""
    provider = MagicMock()
    provider.cloud_name = "test-openstack"
    provider.info.return_value = {"ip": "192.0.2.10"}

    private_key = "/tmp/sensitive-private-key"
    cloud_config = {
        "key_path": private_key,
        "user": "ubuntu",
    }

    error = subprocess.CalledProcessError(
        returncode=255,
        cmd=["ssh", "-i", private_key, "ubuntu@192.0.2.10"],
    )

    with (
        patch(
            "cloudmesh.ai.command.vm.ssh.get_active_provider",
            return_value=provider,
        ),
        patch(
            "cloudmesh.ai.command.vm.ssh.resolve_vm_name",
            return_value="test-vm",
        ),
        patch(
            "cloudmesh.ai.command._shared.context.state.config.get_cloud_config",
            return_value=cloud_config,
        ),
        patch(
            "cloudmesh.ai.command.vm.ssh.subprocess.run",
            side_effect=error,
        ) as mock_run,
    ):
        result = CliRunner().invoke(cmx, ["vm", "ssh", "test-vm"])

    mock_run.assert_called_once()
    assert result.exit_code != 0
    assert private_key not in result.output
    assert "SSH connection failed" in result.output


def test_ssh_timeout_reports_safe_error():
    """SSH timeout errors must not expose private-key paths."""
    provider = MagicMock()
    provider.cloud_name = "test-openstack"
    provider.info.return_value = {"ip": "192.0.2.10"}

    private_key = "/tmp/sensitive-timeout-key"
    cloud_config = {
        "key_path": private_key,
        "user": "ubuntu",
    }

    error = subprocess.TimeoutExpired(
        cmd=["ssh", "-i", private_key, "ubuntu@192.0.2.10"],
        timeout=30,
    )

    with (
        patch(
            "cloudmesh.ai.command.vm.ssh.get_active_provider",
            return_value=provider,
        ),
        patch(
            "cloudmesh.ai.command.vm.ssh.resolve_vm_name",
            return_value="test-vm",
        ),
        patch(
            "cloudmesh.ai.command._shared.context.state.config.get_cloud_config",
            return_value=cloud_config,
        ),
        patch(
            "cloudmesh.ai.command.vm.ssh.subprocess.run",
            side_effect=error,
        ) as mock_run,
    ):
        result = CliRunner().invoke(cmx, ["vm", "ssh", "test-vm"])

    mock_run.assert_called_once()
    assert result.exit_code != 0
    assert "SSH connection timed out" in result.output
    assert private_key not in result.output
