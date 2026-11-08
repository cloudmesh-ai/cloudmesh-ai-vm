"""Regression tests for OpenStack failure handling (Issue #103)."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from cloudmesh.ai.vm.exceptions import VMProviderError
from cloudmesh.ai.vm.openstack.OpenstackManager import OpenstackManager


def test_start_preserves_vm_when_activation_fails():
    """A VM that fails activation must remain available for debugging."""
    provider = OpenstackManager(
        {"clouds": {"test-openstack": {}}},
        cloud_name="test-openstack",
    )

    conn = MagicMock()
    conn.compute.find_image.return_value = SimpleNamespace(id="image-123")
    conn.compute.find_flavor.return_value = SimpleNamespace(id="flavor-123")
    conn.network.find_security_group.return_value = SimpleNamespace(
        name="default"
    )
    conn.compute.create_server.return_value = SimpleNamespace(
        id="vm-123",
        name="test-vm",
    )

    # Explicitly supply the mocked driver to avoid call-stack mock discovery.
    provider.driver = conn.compute
    conn.compute.find_security_group.return_value = SimpleNamespace(
        name="default"
    )

    with (
        patch.object(provider, "_get_sdk_conn", return_value=conn),
        patch.object(provider, "_get_default_network", return_value="network-123"),
        patch.object(provider, "wait_for_active", return_value=False),
        pytest.raises(VMProviderError, match="failed to become ACTIVE"),
    ):
        provider.start(name="test-vm", assign_ip=False)

    conn.compute.create_server.assert_called_once()
    conn.compute.delete_server.assert_not_called()


def test_start_handles_server_creation_failure():
    """A server creation failure must raise VMProviderError without deleting a VM."""
    provider = OpenstackManager(
        {"clouds": {"test-openstack": {}}},
        cloud_name="test-openstack",
    )

    driver = MagicMock()
    driver.find_image.return_value = SimpleNamespace(id="image-123")
    driver.find_flavor.return_value = SimpleNamespace(id="flavor-123")
    driver.find_security_group.return_value = SimpleNamespace(name="default")
    driver.create_server.side_effect = RuntimeError("Simulated server creation failure")

    provider.driver = driver

    with (
        patch.object(provider, "_get_default_network", return_value="network-123"),
        pytest.raises(VMProviderError, match="Simulated server creation failure"),
    ):
        provider.start(name="test-vm", assign_ip=False)

    driver.create_server.assert_called_once()
    driver.delete_server.assert_not_called()


def test_start_reports_floating_ip_assignment_failure():
    """Requested floating-IP assignment failure must not be reported as success."""
    provider = OpenstackManager(
        {"clouds": {"test-openstack": {}}},
        cloud_name="test-openstack",
    )

    driver = MagicMock()
    driver.find_image.return_value = SimpleNamespace(id="image-123")
    driver.find_flavor.return_value = SimpleNamespace(id="flavor-123")
    driver.find_security_group.return_value = SimpleNamespace(name="default")
    driver.create_server.return_value = SimpleNamespace(
        id="vm-123",
        name="test-vm",
    )
    provider.driver = driver

    with (
        patch.object(provider, "_get_default_network", return_value="network-123"),
        patch.object(provider, "wait_for_active", return_value=True),
        patch.object(provider, "assign_floating_ip", return_value=None) as assign_ip,
        patch.object(provider, "wait_for_login") as wait_for_login,
        pytest.raises(VMProviderError, match="floating IP|Floating IP"),
    ):
        provider.start(name="test-vm", assign_ip=True)

    assign_ip.assert_called_once_with("test-vm")
    wait_for_login.assert_not_called()
    driver.delete_server.assert_not_called()


def test_release_floating_ip_reports_sdk_deletion_failure():
    """An unsuccessful SDK floating-IP deletion must not report success."""
    provider = OpenstackManager(
        {"clouds": {"test-openstack": {}}},
        cloud_name="test-openstack",
    )

    node = SimpleNamespace(
        id="vm-123",
        public_ips=["192.0.2.10"],
        addresses={
            "public": [
                {
                    "addr": "192.0.2.10",
                    "OS-EXT-IPS:type": "floating",
                }
            ]
        },
    )
    fip = SimpleNamespace(
        id="fip-123",
        floating_ip_address="192.0.2.10",
    )

    conn = MagicMock()
    conn.network.find_floating_ip.return_value = fip
    conn.network.delete_floating_ip.return_value = False

    with (
        patch.object(provider, "_find_node", return_value=node),
        patch.object(provider, "_get_sdk_conn", return_value=conn),
    ):
        result = provider.release_floating_ip("test-vm")

    assert result is False
    conn.compute.remove_floating_ip_from_server.assert_called_once_with(
        node, fip
    )
    conn.network.delete_floating_ip.assert_called_once_with(fip)


def test_delete_reports_floating_ip_cleanup_failure():
    """VM deletion must not report complete success when IP cleanup fails."""
    provider = OpenstackManager(
        {"clouds": {"test-openstack": {}}},
        cloud_name="test-openstack",
    )

    server = SimpleNamespace(
        id="vm-123",
        name="test-vm",
        public_ips=["192.0.2.10"],
        addresses={
            "public": [
                {
                    "addr": "192.0.2.10",
                    "OS-EXT-IPS:type": "floating",
                }
            ]
        },
    )
    conn = MagicMock()

    with (
        patch.object(provider, "exists", return_value=True),
        patch.object(provider, "_find_node", return_value=server),
        patch.object(provider, "_get_sdk_conn", return_value=conn),
        patch.object(provider, "release_floating_ip", return_value=False),
        pytest.raises(VMProviderError, match="floating IP|Floating IP"),
    ):
        provider.delete("test-vm")

    conn.compute.delete_server.assert_called_once_with(server)


def test_assign_floating_ip_sdk_success():
    """SDK assignment uses the configured network and Neutron attachment."""
    provider = OpenstackManager(
        {"clouds": {"test-openstack": {"floating_ip_pool": "public"}}},
        cloud_name="test-openstack",
    )
    provider.driver = None

    server = SimpleNamespace(id="vm-123", name="test-vm")
    network = SimpleNamespace(id="public-net-123")
    fip = SimpleNamespace(
        id="fip-123",
        floating_ip_address="192.0.2.10",
    )
    port = SimpleNamespace(id="port-123", device_id="vm-123")

    conn = MagicMock()
    conn.compute.find_server.return_value = server
    conn.network.find_network.return_value = network
    conn.network.create_ip.return_value = fip
    conn.network.ports.return_value = iter([port])

    with (
        patch.object(provider, "_get_sdk_conn", return_value=conn),
        patch.object(provider, "wait_for_active", return_value=True),
        patch.object(provider, "get_cloud_config", return_value={
            "floating_ip_pool": "public",
            "username": "test-user",
        }),
    ):
        result = provider.assign_floating_ip("test-vm")

    assert result == "192.0.2.10"
    conn.network.find_network.assert_called_once_with("public")
    conn.network.create_ip.assert_called_once_with(
        floating_network_id="public-net-123",
        description="test-user – floating IP",
    )
    conn.network.ports.assert_called_once_with(device_id="vm-123")
    conn.network.update_ip.assert_called_once_with(
        "fip-123", port_id="port-123"
    )
    conn.compute.add_floating_ip_to_server.assert_not_called()


def test_assign_floating_ip_sdk_falls_back_to_compute_api():
    """Use the Compute API when Neutron floating-IP attachment fails."""
    provider = OpenstackManager(
        {"clouds": {"test-openstack": {"floating_ip_pool": "public"}}},
        cloud_name="test-openstack",
    )
    provider.driver = None

    server = SimpleNamespace(id="vm-123", name="test-vm")
    network = SimpleNamespace(id="public-net-123")
    fip = SimpleNamespace(
        id="fip-123",
        floating_ip_address="192.0.2.10",
    )
    port = SimpleNamespace(id="port-123", device_id="vm-123")

    conn = MagicMock()
    conn.compute.find_server.return_value = server
    conn.network.find_network.return_value = network
    conn.network.create_ip.return_value = fip
    conn.network.ports.return_value = iter([port])
    conn.network.update_ip.side_effect = RuntimeError(
        "Neutron attachment unavailable"
    )

    with (
        patch.object(provider, "_get_sdk_conn", return_value=conn),
        patch.object(provider, "wait_for_active", return_value=True),
        patch.object(provider, "get_cloud_config", return_value={
            "floating_ip_pool": "public",
            "username": "test-user",
        }),
    ):
        result = provider.assign_floating_ip("test-vm")

    assert result == "192.0.2.10"
    conn.network.find_network.assert_called_once_with("public")
    conn.network.create_ip.assert_called_once_with(
        floating_network_id="public-net-123",
        description="test-user – floating IP",
    )
    conn.network.ports.assert_called_once_with(device_id="vm-123")
    conn.network.update_ip.assert_called_once_with(
        "fip-123", port_id="port-123"
    )
    conn.compute.add_floating_ip_to_server.assert_called_once_with(
        server, "192.0.2.10"
    )


def test_delete_vm_without_floating_ip():
    """Deleting a VM without a floating IP should succeed."""
    provider = OpenstackManager(
        {"clouds": {"test-openstack": {}}},
        cloud_name="test-openstack",
    )

    server = SimpleNamespace(
        id="vm-123",
        name="test-vm",
        public_ips=[],
    )
    conn = MagicMock()

    with (
        patch.object(provider, "exists", return_value=True),
        patch.object(provider, "_find_node", return_value=server),
        patch.object(provider, "_get_sdk_conn", return_value=conn),
        patch.object(provider, "release_floating_ip") as release_ip,
    ):
        result = provider.delete("test-vm")

    assert result is True
    release_ip.assert_not_called()
    conn.compute.delete_server.assert_called_once_with(server)
