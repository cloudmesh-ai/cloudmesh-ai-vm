"""Regression tests for SSH-key management failures."""

from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from cloudmesh.ai.command.vm import cmx


def test_key_delete_false_result_reports_expected_error():
    """A failed key deletion must produce a meaningful CLI error."""
    provider = MagicMock()
    provider.cloud_name = "test-openstack"
    provider.delete_key.return_value = False

    with patch(
        "cloudmesh.ai.command.key.delete.get_active_provider",
        return_value=provider,
    ):
        result = CliRunner().invoke(
            cmx, ["key", "delete", "test-key"]
        )

    provider.delete_key.assert_called_once_with("test-key")
    assert result.exit_code != 0
    assert "Failed to delete key test-key" in result.output
    assert "NameError" not in result.output
    assert "Unexpected Error" not in result.output


def test_key_upload_false_result_reports_expected_error():
    """A failed key upload must produce a meaningful CLI error."""
    provider = MagicMock()
    provider.cloud_name = "test-openstack"
    provider.get_cloud_config.return_value = {}
    provider.upload_key.return_value = False

    key_path = "/tmp/test-public-key.pub"

    with patch(
        "cloudmesh.ai.command.key.upload.get_active_provider",
        return_value=provider,
    ):
        result = CliRunner().invoke(
            cmx, ["key", "upload", key_path, "--name", "test-key"]
        )

    provider.upload_key.assert_called_once_with(key_path, "test-key")
    assert result.exit_code != 0
    assert "Failed to upload key" in result.output
    assert "Unexpected Error" not in result.output


def test_key_upload_provider_exception_does_not_expose_credentials():
    """Provider exceptions must not expose credentials in CLI output."""
    provider = MagicMock()
    provider.cloud_name = "test-openstack"
    provider.get_cloud_config.return_value = {}

    secret = "SENSITIVE_TEST_TOKEN_12345"
    provider.upload_key.side_effect = RuntimeError(
        f"Cloud authentication failed: token={secret}"
    )

    key_path = "/tmp/test-public-key.pub"

    with patch(
        "cloudmesh.ai.command.key.upload.get_active_provider",
        return_value=provider,
    ):
        result = CliRunner().invoke(
            cmx, ["key", "upload", key_path, "--name", "test-key"]
        )

    provider.upload_key.assert_called_once_with(key_path, "test-key")
    assert result.exit_code != 0
    assert secret not in result.output
    assert "Failed to upload key" in result.output


def test_vm_key_upload_provider_exception_does_not_expose_credentials():
    """VM-level key upload must sanitize provider exceptions."""
    provider = MagicMock()
    provider.cloud_name = "test-openstack"
    provider.get_cloud_config.return_value = {}

    secret = "SENSITIVE_VM_KEY_TOKEN_67890"
    provider.upload_key.side_effect = RuntimeError(
        f"Cloud authentication failed: token={secret}"
    )

    key_path = "/tmp/test-vm-public-key.pub"

    with patch(
        "cloudmesh.ai.command.vm.key.upload.get_active_provider",
        return_value=provider,
    ):
        result = CliRunner().invoke(
            cmx,
            ["vm", "key", "upload", key_path, "--name", "test-key"],
        )

    provider.upload_key.assert_called_once_with(key_path, "test-key")
    assert result.exit_code != 0
    assert secret not in result.output
    assert "Failed to upload key" in result.output


def test_key_delete_provider_exception_does_not_expose_credentials():
    """Key deletion must sanitize provider exceptions."""
    provider = MagicMock()
    provider.cloud_name = "test-openstack"

    secret = "SENSITIVE_DELETE_TOKEN_98765"
    provider.delete_key.side_effect = RuntimeError(
        f"Cloud authentication failed: token={secret}"
    )

    with patch(
        "cloudmesh.ai.command.key.delete.get_active_provider",
        return_value=provider,
    ):
        result = CliRunner().invoke(
            cmx, ["key", "delete", "test-key"]
        )

    provider.delete_key.assert_called_once_with("test-key")
    assert result.exit_code != 0
    assert secret not in result.output
    assert "Failed to delete key" in result.output
