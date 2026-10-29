from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from cloudmesh.ai.vm.exceptions import VMProviderError
from cloudmesh.ai.vm.openstack.OpenstackManager import OpenstackManager


@pytest.fixture
def mock_driver():
    """Mock the OpenStack SDK connection."""
    conn = MagicMock()
    conn.compute.find_image.return_value.id = "image-123"
    conn.compute.find_flavor.return_value.id = "flavor-123"
    conn.network.find_security_group.return_value.name = "ssh-access"
    conn.region = "IU"
    conn.auth.auth_url = "https://example.invalid/v3/"
    return conn


@pytest.fixture
def provider(mock_driver):
    """Provide an OpenStack manager with an isolated SDK connection."""
    manager = OpenstackManager(
        {
            "clouds": {
                "test-openstack": {
                    "image": "test-image",
                    "flavor": "test-flavor",
                    "security_group": "ssh-access",
                    "key_path": "~/.ssh/id_rsa.pub",
                }
            }
        },
        cloud_name="test-openstack",
    )
    with patch.object(manager, "_get_sdk_conn", return_value=mock_driver):
        yield manager


def test_start_uses_configured_key_and_security_group(provider, mock_driver):
    """OpenStack VM creation should attach the configured SSH key and security group."""
    image = MagicMock()
    image.id = "image-123"
    image.name = "test-image"
    mock_driver.compute.find_image.return_value = image

    flavor = MagicMock()
    flavor.id = "flavor-123"
    flavor.name = "test-flavor"
    mock_driver.compute.find_flavor.return_value = flavor

    security_group = MagicMock()
    security_group.id = "sg-123"
    security_group.name = "ssh-access"
    mock_driver.network.find_security_group.return_value = security_group

    node = MagicMock()
    node.id = "vm-123"
    node.name = "test-vm"
    mock_driver.compute.create_server.return_value = node

    # Mock wait_for_active to return True immediately
    with (
        patch.object(provider, "_get_default_network", return_value="test-network"),
        patch.object(provider, "wait_for_active", return_value=True),
        patch.object(provider, "assign_floating_ip", return_value="1.2.3.4"),
        patch.object(provider, "wait_for_login", return_value=True),
    ):
        result = provider.start(name="test-vm")

    assert result == "test-vm"

    mock_driver.compute.create_server.assert_called_once_with(
        name="test-vm",
        image_id=image.id,
        flavor_id=flavor.id,
        key_name="id_rsa",
        security_groups=[{"name": "ssh-access"}],
        networks=[{"uuid": "test-network"}],
    )


def test_start_does_not_create_vm_when_security_group_is_missing(provider, mock_driver):
    """OpenStack VM creation should fail before boot when the security group is missing."""
    # Update config for this specific test case
    provider.config["clouds"]["test-openstack"]["security_group"] = "missing-group"

    image = MagicMock()
    image.id = "image-123"
    image.name = "test-image"
    mock_driver.compute.find_image.return_value = image

    flavor = MagicMock()
    flavor.id = "flavor-123"
    flavor.name = "test-flavor"
    mock_driver.compute.find_flavor.return_value = flavor

    # OpenStack SDK returns None when the group is not found.
    mock_driver.network.find_security_group.return_value = None

    with pytest.raises(
        VMProviderError, match="Could not find security group missing-group"
    ):
        provider.start(name="test-vm")

    mock_driver.compute.create_server.assert_not_called()


def test_start_prefers_explicit_key_name(provider, mock_driver):
    """An explicit OpenStack key name should override the name derived from key_path."""
    provider.config["clouds"]["test-openstack"]["key_name"] = "custom-cloud-key"

    image = MagicMock()
    image.id = "image-123"
    image.name = "test-image"
    mock_driver.compute.find_image.return_value = image

    flavor = MagicMock()
    flavor.id = "flavor-123"
    flavor.name = "test-flavor"
    mock_driver.compute.find_flavor.return_value = flavor

    security_group = MagicMock()
    security_group.id = "sg-123"
    security_group.name = "ssh-access"
    mock_driver.network.find_security_group.return_value = security_group

    node = MagicMock()
    node.id = "vm-123"
    node.name = "test-vm"
    mock_driver.compute.create_server.return_value = node

    with (
        patch.object(provider, "_get_default_network", return_value="test-network"),
        patch.object(provider, "wait_for_active", return_value=True),
        patch.object(provider, "assign_floating_ip", return_value="1.2.3.4"),
        patch.object(provider, "wait_for_login", return_value=True),
    ):
        result = provider.start(name="test-vm")
    assert result == "test-vm"


def test_get_provider_info_uses_supported_configuration_fields(provider, mock_driver):
    """Provider info should expose only supported, non-sensitive SDK fields."""
    mock_driver.region = "IU"
    mock_driver.auth.auth_url = "https://example.invalid/v3/"

    with patch.object(
        type(provider),
        "version",
        new_callable=PropertyMock,
    ) as mock_version:
        mock_version.return_value = ["SDK: test"]
        info = provider.get_provider_info()

    assert info["provider"] == "OpenStack"
    assert info["cloud_name"] == "test-openstack"
    assert info["region"] == "IU"
    assert info["auth_url"] == "https://example.invalid/v3/"
    assert info["version"] == ["SDK: test"]

    assert "password" not in info
    assert "token" not in info


def test_start_cleans_up_server_when_activation_fails(provider):
    """A newly created VM should be removed if activation fails."""
    conn = MagicMock()
    conn.compute.find_image.return_value.id = "image-123"
    conn.compute.find_flavor.return_value.id = "flavor-123"
    conn.network.find_security_group.return_value.name = "default"

    server = MagicMock()
    server.id = "vm-123"
    server.name = "test-vm"
    conn.compute.create_server.return_value = server

    with (
        patch.object(provider, "_get_sdk_conn", return_value=conn),
        patch.object(provider, "_get_default_network", return_value=None),
        patch.object(provider, "wait_for_active", return_value=False),
        pytest.raises(VMProviderError, match="failed to become ACTIVE"),
    ):
        provider.start(
            name="test-vm",
            image="test-image",
            flavor="test-flavor",
            assign_ip=False,
        )

    conn.compute.create_server.assert_called_once()
    conn.compute.delete_server.assert_called_once_with(server)


def test_start_preserves_activation_error_when_cleanup_fails(provider, caplog):
    """Cleanup failure must not replace the original VM activation error."""
    conn = MagicMock()
    conn.compute.find_image.return_value.id = "image-123"
    conn.compute.find_flavor.return_value.id = "flavor-123"
    conn.network.find_security_group.return_value.name = "default"

    server = MagicMock()
    server.id = "vm-123"
    server.name = "test-vm"
    conn.compute.create_server.return_value = server
    secret = "FAKE-CLEANUP-TOKEN-12345"
    conn.compute.delete_server.side_effect = RuntimeError(
        f"Cleanup unavailable: token={secret}"
    )

    with (
        patch.object(provider, "_get_sdk_conn", return_value=conn),
        patch.object(provider, "_get_default_network", return_value=None),
        patch.object(provider, "wait_for_active", return_value=False),
        pytest.raises(VMProviderError, match="failed to become ACTIVE"),
    ):
        provider.start(
            name="test-vm",
            image="test-image",
            flavor="test-flavor",
            assign_ip=False,
        )

    conn.compute.delete_server.assert_called_once_with(server)
    assert "Failed to clean up VM" in caplog.text
    assert secret not in caplog.text


def test_run_command_does_not_expose_sensitive_ssh_stderr(provider):
    """SSH failures must not expose sensitive diagnostic output."""
    secret = "FAKE-SSH-SECRET-12345"

    result = MagicMock()
    result.returncode = 255
    result.stdout = ""
    result.stderr = f"SSH authentication failed; secret={secret}"

    with (
        patch.object(provider, "_get_floating_ip", return_value="192.0.2.10"),
        patch("subprocess.run", return_value=result) as run,
    ):
        output = provider.run_command("test-vm", "uptime")

    run.assert_called_once()
    assert secret not in output
    assert "SSH" in output


def test_run_command_handles_ssh_timeout_without_leaking_details(provider):
    """SSH timeout errors must not expose command arguments or key paths."""
    import subprocess

    secret = "FAKE-PRIVATE-KEY-PATH-12345"

    with (
        patch.object(provider, "_get_floating_ip", return_value="192.0.2.10"),
        patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(
                cmd=["ssh", "-i", secret, "ubuntu@192.0.2.10"],
                timeout=30,
            ),
        ),
    ):
        output = provider.run_command("test-vm", "uptime")

    assert "SSH Error" in output
    assert secret not in output
    assert "192.0.2.10" not in output


def test_upload_key_failure_does_not_log_sensitive_details(
    provider, mock_driver, caplog, tmp_path
):
    """Key upload failures must not expose SDK secrets in logs."""
    secret = "FAKE-KEY-UPLOAD-SECRET-12345"

    public_key = tmp_path / "test_key.pub"
    public_key.write_text("ssh-ed25519 AAAATESTKEY test@example.invalid")

    mock_driver.compute.create_keypair.side_effect = RuntimeError(
        f"Authentication failed; token={secret}"
    )

    result = provider.upload_key(str(public_key), "test-key")

    assert result is False
    mock_driver.compute.create_keypair.assert_called_once()
    assert secret not in caplog.text


def test_delete_key_failure_does_not_log_sensitive_details(
    provider, mock_driver, caplog
):
    """Key deletion failures must not expose SDK secrets in logs."""
    secret = "FAKE-KEY-DELETE-SECRET-12345"

    mock_driver.compute.delete_keypair.side_effect = RuntimeError(
        f"Authentication failed; token={secret}"
    )

    result = provider.delete_key("test-key")

    assert result is False
    mock_driver.compute.delete_keypair.assert_called_once_with("test-key")
    assert secret not in caplog.text


def test_delete_vm_continues_when_floating_ip_cleanup_fails(
    provider, mock_driver, caplog
):
    """VM deletion should proceed if floating-IP cleanup raises an error."""
    server = MagicMock()
    server.id = "vm-123"
    server.name = "test-vm"

    with (
        patch.object(provider, "exists", return_value=True),
        patch.object(provider, "_find_node", return_value=server),
        patch.object(
            provider,
            "release_floating_ip",
            side_effect=RuntimeError("Floating IP cleanup failed"),
        ),
    ):
        result = provider.delete("test-vm")

    assert result is True
    mock_driver.compute.delete_server.assert_called_once_with(server)
    assert "Floating IP cleanup failed" in caplog.text



def test_delete_continues_when_floating_ip_release_returns_false(
    provider, mock_driver, caplog
):
    """VM deletion must continue when floating-IP release returns False."""
    server = MagicMock()
    server.id = "vm-123"
    server.name = "test-vm"

    with (
        patch.object(provider, "exists", return_value=True),
        patch.object(provider, "_find_node", return_value=server),
        patch.object(provider, "release_floating_ip", return_value=False),
    ):
        result = provider.delete("test-vm")

    assert result is True
    mock_driver.compute.delete_server.assert_called_once_with(server)
    assert "Floating IP was not released" in caplog.text


def test_release_floating_ip_does_not_log_sensitive_sdk_error(
    provider, mock_driver, caplog
):
    """Floating-IP cleanup must not log sensitive SDK exception details."""
    secret = "FAKE-FLOATING-IP-TOKEN-12345"

    server = MagicMock()
    server.public_ips = ["192.0.2.10"]

    mock_driver.network.find_floating_ip.side_effect = RuntimeError(
        f"OpenStack authentication failed: token={secret}"
    )

    with patch.object(provider, "_find_node", return_value=server):
        result = provider.release_floating_ip("test-vm")

    assert result is False
    assert "Error releasing floating IP" in caplog.text
    assert secret not in caplog.text


def test_stop_does_not_expose_sensitive_sdk_errors(provider, mock_driver, caplog):
    """Stopping a VM must not disclose sensitive SDK exception details."""
    secret = "FAKE-OPENSTACK-TOKEN-12345"

    server = MagicMock()
    server.name = "test-vm"
    server.status = "ACTIVE"

    mock_driver.compute.stop_server.side_effect = RuntimeError(
        f"OpenStack authentication failed: token={secret}"
    )

    with (
        patch.object(provider, "exists", return_value=True),
        patch.object(provider, "_find_node", return_value=server),
        pytest.raises(VMProviderError) as exc_info,
    ):
        provider.stop("test-vm")

    mock_driver.compute.stop_server.assert_called_once_with(server)
    assert secret not in str(exc_info.value)
    assert secret not in caplog.text


def test_delete_does_not_expose_sensitive_sdk_errors(provider, mock_driver, caplog):
    """Deleting a VM must not disclose sensitive SDK exception details."""
    secret = "FAKE-OPENSTACK-DELETE-TOKEN-12345"

    server = MagicMock()
    server.name = "test-vm"

    mock_driver.compute.delete_server.side_effect = RuntimeError(
        f"OpenStack deletion failed: token={secret}"
    )

    with (
        patch.object(provider, "exists", return_value=True),
        patch.object(provider, "_find_node", return_value=server),
        patch.object(provider, "release_floating_ip", return_value=True),
        pytest.raises(VMProviderError) as exc_info,
    ):
        provider.delete("test-vm")

    mock_driver.compute.delete_server.assert_called_once_with(server)
    assert secret not in str(exc_info.value)
    assert secret not in caplog.text


def test_start_does_not_expose_sensitive_sdk_errors(provider, mock_driver, caplog):
    """Starting a VM must not disclose sensitive SDK exception details."""
    secret = "FAKE-OPENSTACK-START-TOKEN-12345"

    mock_driver.compute.create_server.side_effect = RuntimeError(
        f"OpenStack VM creation failed: token={secret}"
    )

    with (
        patch.object(provider, "_get_default_network", return_value=None),
        pytest.raises(VMProviderError) as exc_info,
    ):
        provider.start(
            name="test-vm",
            image="test-image",
            flavor="test-flavor",
            assign_ip=False,
        )

    mock_driver.compute.create_server.assert_called_once()
    assert secret not in str(exc_info.value)
    assert secret not in caplog.text
