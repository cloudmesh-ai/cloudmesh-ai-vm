from unittest.mock import MagicMock, patch, mock_open, PropertyMock

import pytest

from cloudmesh.ai.vm.openstack.ChameleonManager import Provider
from cloudmesh.ai.vm.exceptions import VMProviderError
from keystoneauth1.exceptions.catalog import EndpointNotFound


@pytest.fixture
def mock_config():
    return {
        "clouds": {
            "chameleon": {
                "site": "kvm@tacc",
                "project_name": "test-project",
                "auth_url": "https://api.tacc.chameleoncloud.org/v3",
                "username": "test-user",
                "password": "test-password",
                "domain_name": "Default",
            }
        }
    }


@pytest.fixture
def provider(mock_config):
    # We must patch all the references that ChameleonManager imports from chi
    # Using patch.start() to ensure the mocks are active during the Provider's lifecycle
    # Only patch the top‑level ``chi`` reference and the authentication shim.
    # The inner ``chi`` sub‑modules (server, lease, network, ...) are accessed
    # via attributes on the patched ``chi`` MagicMock, so separate patches are
    # unnecessary and cause attribute errors after we removed the direct imports.
    patchers = [
        patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi"),
        patch("cloudmesh.ai.vm.openstack.ChameleonManager.authenticate_chi_from_cloud"),
    ]

    mocks = [p.start() for p in patchers]
    mock_chi = mocks[0]

    # Configure basic defaults for the mock_chi to avoid common attribute errors
    mock_chi.get.side_effect = lambda key: {
        "site": "kvm@tacc",
        "project_name": "test-project",
        "project_id": "proj-123",
        "user_id": "user-456",
        "allocation": "1000 SU",
    }.get(key)

    # ---------------------------------------------------------------------
    # Prepare a dummy ``openstack`` module to avoid importing the real SDK.
    # This dummy module provides a ``connect`` function that returns a MagicMock
    # with a ``compute`` attribute that raises ``EndpointNotFound`` when accessed.
    # The mock also supplies minimal ``session.auth`` and other network attributes
    # used by the provider code.
    # ---------------------------------------------------------------------
    import sys
    import types
    mock_conn = MagicMock()
    # Simulate missing compute endpoint by making ``compute`` a property that raises.
    type(mock_conn).compute = PropertyMock(
        side_effect=EndpointNotFound(
            "publicURL endpoint for compute service in KVM@TACC region not found"
        )
    )
    # Provide stub attributes accessed by the provider
    mock_conn.session = MagicMock()
    mock_conn.session.auth = MagicMock()
    # Provide mock network attributes accessed later in the start flow.
    mock_conn.network = MagicMock()
    mock_conn.network.ports.return_value = []
    mock_conn.network.floating_ips.return_value = []

    dummy_openstack = types.ModuleType("openstack")
    dummy_openstack.connect = MagicMock(return_value=mock_conn)
    # Ensure the dummy module appears in ``sys.modules`` before any import.
    sys.modules["openstack"] = dummy_openstack

    # Provide basic chi.server attributes required by Provider.start.
    mock_chi.server = MagicMock()
    mock_chi.server.list_keypair.return_value = []
    mock_chi.server.update_keypair.return_value = True
    # get_server should return ``None`` to indicate the VM does not already exist.
    mock_chi.server.get_server.return_value = None

    try:
        p = Provider(mock_config, cloud_name="chameleon")
        yield p
    finally:
        # Clean up the dummy module to avoid side‑effects for other tests.
        sys.modules.pop("openstack", None)
        for p in reversed(patchers):
            p.stop()


def test_list_regions(provider):
    with patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi:
        mock_chi.context.list_sites.return_value = {
            "kvm@tacc": {"description": "TACC KVM site", "status": "active"},
            "kvm@clemson": {"description": "Clemson KVM site", "status": "active"},
        }

        regions = provider.list_regions()

        assert isinstance(regions, list)
        assert len(regions) >= 1
        tacc_region = next((r for r in regions if r["name"] == "kvm@tacc"), None)
        assert tacc_region is not None
        assert tacc_region["description"] == "TACC KVM site"


def test_create_reservation_success(provider):
    with patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi:
        mock_chi.lease.lease_duration.return_value = ("2026-10-06", "2026-10-07")
        # Mock the lease object returned by create_lease
        mock_lease = MagicMock()
        mock_lease.id = "lease-123"
        mock_chi.lease.create_lease.return_value = mock_lease

        result = provider.create_reservation(
            name="smoke-reservation", node_type="bare_metal", count=1, duration=1
        )

        assert result == "lease-123"


def test_create_reservation_no_project(provider):
    provider.config["clouds"]["chameleon"]["project_name"] = None

    result = provider.create_reservation(
        name="smoke-reservation", node_type="bare_metal", count=1
    )

    assert result is None


def test_get_account_info_success(provider):
    # The provider fixture already configures mock_chi.get
    info = provider.get_account_info()

    assert info["site"] == "kvm@tacc"
    assert info["project_name"] == "test-project"
    assert info["project_id"] == "proj-123"
    assert info["user_id"] == "user-456"
    assert info["allocation"] == "1000 SU"


def test_start_compute_endpoint_missing(provider):
    """Ensure that a missing compute endpoint is detected early and raises a clear error.

    The provider should attempt to validate the OpenStack SDK connection before
    performing any key‑pair operations. When the compute service endpoint is not
    available, ``VMProviderError`` with a helpful hint must be raised.
    """
    # Ensure a key path is defined and mock the file read for the public key.
    provider.config["clouds"]["chameleon"]["key_path"] = "/tmp/fake.pub"

    # Mock the chi server calls to avoid unrelated failures.
    import cloudmesh.ai.vm.openstack.ChameleonManager as cm
    cm.chi.server.list_keypair.return_value = []

    # Patch "open" to return a dummy public key. The dummy ``openstack`` module
    # (injected by the ``provider`` fixture) already raises ``EndpointNotFound``
    # for the compute service, so we only need to patch the file read.
    with patch("builtins.open", mock_open(read_data="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQCtest")):
        with pytest.raises(VMProviderError) as excinfo:
            provider.start(name="test-vm")

        # The raised error should contain a concise hint about the compute
        # endpoint configuration.
        assert "Compute service endpoint not found" in str(excinfo.value)


def _fake_server(name: str, server_id: str):
    """Build a minimal fake ``chi`` server object for ``delete()`` tests."""
    s = MagicMock()
    s.name = name
    s.id = server_id
    s.get_metadata.return_value = {}
    return s


# ---------------------------------------------------------------------------
# delete() matching and safety tests (regression guards for issue #123)
# All tests run fully mocked: no Chameleon credentials or network access.
# ---------------------------------------------------------------------------


def test_delete_exact_name_match(provider):
    """An exact name match deletes the right server and nothing else."""
    with patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi:
        server_a = _fake_server("vm-a", "11111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        server_b = _fake_server("vm-b", "22222222-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
        initial_servers = [server_a, server_b]
        deleted_ids = set()
        mock_chi.server.delete_server.side_effect = deleted_ids.add
        mock_chi.server.list_servers.side_effect = lambda: [
            server for server in initial_servers
            if server.id not in deleted_ids
        ]
        mock_chi.server.get_server.side_effect = Exception("not found by name")

        with patch.object(provider, "release_floating_ip") as mock_release:
            result = provider.delete("vm-b")

        assert result is True
        mock_chi.server.delete_server.assert_called_once_with(server_b.id)
        # FIP cleanup must be handed the verified server object.
        mock_release.assert_called_once_with("vm-b", server=server_b)


def test_delete_by_exact_id(provider):
    """An exact server ID match deletes the right server."""
    with patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi:
        server_a = _fake_server("vm-a", "11111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        server_b = _fake_server("vm-b", "22222222-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
        initial_servers = [server_a, server_b]
        deleted_ids = set()
        mock_chi.server.delete_server.side_effect = deleted_ids.add
        mock_chi.server.list_servers.side_effect = lambda: [
            server for server in initial_servers
            if server.id not in deleted_ids
        ]
        mock_chi.server.get_server.side_effect = Exception("not found")

        with patch.object(provider, "release_floating_ip") as mock_release:
            result = provider.delete(server_b.id)

        assert result is True
        mock_chi.server.delete_server.assert_called_once_with(server_b.id)
        mock_release.assert_called_once_with("vm-b", server=server_b)


def test_delete_nonexistent_with_single_server_is_safe(provider, capsys):
    """Regression test for issue #123.

    When the requested VM does not exist and exactly one unrelated server is
    present, ``delete()`` must NOT select or delete that server, must not
    release or dissociate any floating IP, and must not fall back to the
    single active server.
    """
    with patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi:
        # Precondition: exactly one unrelated VM exists.
        only_server = _fake_server(
            "production-vm", "33333333-cccc-4ccc-8ccc-cccccccccccc"
        )
        mock_chi.server.list_servers.return_value = [only_server]
        mock_chi.server.get_server.side_effect = Exception("not found")
        listed = mock_chi.server.list_servers()
        assert listed == [only_server]
        assert only_server.name == "production-vm"

        with patch.object(provider, "release_floating_ip") as mock_release:
            result = provider.delete("nonexistent-vm")

        assert result is False
        # The unrelated VM must never be deleted.
        mock_chi.server.delete_server.assert_not_called()
        # No floating-IP release or dissociation may happen.
        mock_release.assert_not_called()
        # The original single-server fallback message must never be printed.
        captured = capsys.readouterr()
        assert "Targeting:" not in captured.out
        assert "did not match directly" not in captured.out


def test_delete_ambiguous_prefix_rejected(provider):
    """A prefix matching more than one server must not trigger any deletion."""
    with patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi:
        server_a = _fake_server("vm-a", "abcd1234-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        server_b = _fake_server("vm-b", "abcd1234-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
        mock_chi.server.list_servers.return_value = [server_a, server_b]
        mock_chi.server.get_server.side_effect = Exception("not found")

        with patch.object(provider, "release_floating_ip") as mock_release:
            result = provider.delete("abcd1234")

        assert result is False
        mock_chi.server.delete_server.assert_not_called()
        mock_release.assert_not_called()


def test_delete_unique_uuid_prefix(provider):
    """An unambiguous ID prefix (>= 8 chars, exactly one match) deletes that server."""
    with patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi:
        server_a = _fake_server("vm-a", "11111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        server_b = _fake_server("vm-b", "22222222-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
        initial_servers = [server_a, server_b]
        deleted_ids = set()
        mock_chi.server.delete_server.side_effect = deleted_ids.add
        mock_chi.server.list_servers.side_effect = lambda: [
            server for server in initial_servers
            if server.id not in deleted_ids
        ]
        mock_chi.server.get_server.side_effect = Exception("not found")

        with patch.object(provider, "release_floating_ip") as mock_release:
            result = provider.delete("11111111")

        assert result is True
        mock_chi.server.delete_server.assert_called_once_with(server_a.id)
        mock_release.assert_called_once_with("vm-a", server=server_a)


def test_delete_api_failure_raises_vm_provider_error(provider):
    """A chi API failure during deletion surfaces as a VMProviderError."""
    with patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi:
        server_a = _fake_server("vm-a", "11111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        mock_chi.server.list_servers.return_value = [server_a]
        mock_chi.server.get_server.side_effect = Exception("not found")
        mock_chi.server.delete_server.side_effect = RuntimeError("chi API down")

        with patch.object(provider, "release_floating_ip"), pytest.raises(
            VMProviderError, match="CHI delete failed"
        ):
            provider.delete("vm-a")


def test_delete_get_server_mismatch_is_never_deleted(provider):
    """A server returned by get_server() that does not match the requested
    identifier must be ignored and can never be deleted.
    """
    with patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi:
        target = _fake_server("vm-a", "11111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        unrelated = _fake_server("other-vm", "99999999-eeee-4eee-8eee-eeeeeeeeeeee")
        initial_servers = [target, unrelated]
        deleted_ids = set()
        mock_chi.server.delete_server.side_effect = deleted_ids.add
        mock_chi.server.list_servers.side_effect = lambda: [
            server for server in initial_servers
            if server.id not in deleted_ids
        ]
        # get_server() erroneously returns an unrelated VM.
        mock_chi.server.get_server.return_value = unrelated

        with patch.object(provider, "release_floating_ip") as mock_release:
            result = provider.delete("vm-a")

        assert result is True
        # The unrelated VM returned by get_server() must never be deleted;
        # only the validated target is.
        mock_chi.server.delete_server.assert_called_once_with(target.id)
        mock_release.assert_called_once_with("vm-a", server=target)


def test_delete_duplicate_exact_name_rejected(provider):
    """Two servers sharing the requested exact name are ambiguous: none is deleted."""
    with patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi:
        server_a = _fake_server("vm-dup", "11111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        server_b = _fake_server("vm-dup", "22222222-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
        mock_chi.server.list_servers.return_value = [server_a, server_b]
        mock_chi.server.get_server.side_effect = Exception("ambiguous")

        with patch.object(provider, "release_floating_ip") as mock_release:
            result = provider.delete("vm-dup")

        assert result is False
        mock_chi.server.delete_server.assert_not_called()
        mock_release.assert_not_called()


def test_delete_invalid_uuid_prefix_rejected(provider):
    """UUID-prefix matching requires at least 8 hexadecimal characters."""
    with patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi:
        # Non-standard (non-UUID) ID used to exercise the hexadecimal rule.
        server_x = _fake_server("vm-x", "ghij1234-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        server_a = _fake_server("vm-a", "abcd1234-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        mock_chi.server.list_servers.return_value = [server_x, server_a]
        mock_chi.server.get_server.side_effect = Exception("not found")

        with patch.object(provider, "release_floating_ip") as mock_release:
            # Eight characters, but not hexadecimal -> not a valid prefix.
            assert provider.delete("ghij1234") is False
            # Hexadecimal, but shorter than eight characters -> not a prefix.
            assert provider.delete("abcd12") is False

        mock_chi.server.delete_server.assert_not_called()
        mock_release.assert_not_called()


def test_delete_get_server_conflicting_id_uses_list_entry(provider):
    """A get_server() result with the requested name but a different ID than
    the list_servers() entry is ignored; the list entry is the target.
    """
    with patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi:
        list_entry = _fake_server("vm-a", "11111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        stale = _fake_server("vm-a", "99999999-eeee-4eee-8eee-eeeeeeeeeeee")
        deleted_ids = set()
        mock_chi.server.delete_server.side_effect = deleted_ids.add
        mock_chi.server.list_servers.side_effect = lambda: [
            server for server in [list_entry]
            if server.id not in deleted_ids
        ]
        # get_server() returns a stale object: same name, different ID.
        mock_chi.server.get_server.return_value = stale

        with patch.object(provider, "release_floating_ip") as mock_release:
            result = provider.delete("vm-a")

        assert result is True
        # The conflicting unlisted ID must never be deleted.
        mock_chi.server.delete_server.assert_called_once_with(list_entry.id)
        # FIP cleanup must receive the verified list entry, not the stale
        # object returned by get_server().
        mock_release.assert_called_once_with("vm-a", server=list_entry)


def test_delete_get_server_unlisted_prefix_vm_rejected(provider):
    """An unlisted VM returned by get_server() that matches the requested
    UUID prefix is ignored; only the listed server may be deleted.
    """
    with patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi:
        listed = _fake_server("vm-a", "11111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        unlisted = _fake_server("ghost-vm", "11111111-ffff-4fff-8fff-ffffffffffff")
        deleted_ids = set()
        mock_chi.server.delete_server.side_effect = deleted_ids.add
        mock_chi.server.list_servers.side_effect = lambda: [
            server for server in [listed]
            if server.id not in deleted_ids
        ]
        # get_server() returns a VM that is not part of list_servers().
        mock_chi.server.get_server.return_value = unlisted

        with patch.object(provider, "release_floating_ip") as mock_release:
            result = provider.delete("11111111")

        assert result is True
        # Only the listed server is deleted; the unlisted one is untouched.
        mock_chi.server.delete_server.assert_called_once_with(listed.id)
        mock_release.assert_called_once_with("vm-a", server=listed)


def test_delete_conflicting_id_and_name_rejected(provider):
    """An identifier that is the exact ID of one server and the exact name of
    a different server is conflicting: nothing may be deleted.
    """
    with patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi:
        by_id = _fake_server("other-vm", "abc123")
        by_name = _fake_server("abc123", "22222222-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
        mock_chi.server.list_servers.return_value = [by_id, by_name]
        # Even if get_server() returns the ID match, the conflict must block.
        mock_chi.server.get_server.return_value = by_id

        with patch.object(provider, "release_floating_ip") as mock_release:
            result = provider.delete("abc123")

        assert result is False
        mock_chi.server.delete_server.assert_not_called()
        mock_release.assert_not_called()


def test_delete_releases_fip_only_of_verified_server(provider):
    """FIP cleanup during delete must act only on the verified server object,
    even when get_server() would resolve the name to a different VM.
    """
    with patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi:
        target = _fake_server("vm-a", "11111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        target.addresses = {
            "ext-net": [
                {"addr": "10.0.0.5", "OS-EXT-IPS:type": "fixed"},
                {"addr": "129.97.1.100", "OS-EXT-IPS:type": "floating"},
            ]
        }
        other = _fake_server("vm-a", "99999999-eeee-4eee-8eee-eeeeeeeeeeee")
        other.addresses = {
            "ext-net": [{"addr": "129.97.1.200", "OS-EXT-IPS:type": "floating"}]
        }
        deleted_ids = set()
        mock_chi.server.delete_server.side_effect = deleted_ids.add
        mock_chi.server.list_servers.side_effect = lambda: [
            server for server in [target]
            if server.id not in deleted_ids
        ]
        # get_server() would resolve the name to an unrelated, unlisted VM.
        mock_chi.server.get_server.return_value = other

        result = provider.delete("vm-a")

        assert result is True
        # Only the verified server's FIP is detached; the unrelated VM's FIP
        # (129.97.1.200) must never be touched.
        target.detach_floating_ip.assert_called_once_with(
            "129.97.1.100", delete=True
        )
        other.detach_floating_ip.assert_not_called()
        mock_chi.server.delete_server.assert_called_once_with(target.id)


def test_release_floating_ip_with_verified_server_skips_name_lookup(provider):
    """Passing the validated server object skips all name-based lookups."""
    with patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi:
        server = _fake_server("vm-a", "11111111-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
        server.addresses = {
            "ext-net": [{"addr": "129.97.1.100", "OS-EXT-IPS:type": "floating"}]
        }
        mock_chi.server.get_server.side_effect = AssertionError(
            "name-based lookup must not happen when a server object is given"
        )

        result = provider.release_floating_ip("vm-a", server=server)

        assert result is True
        mock_chi.server.get_server.assert_not_called()
        server.detach_floating_ip.assert_called_once_with("129.97.1.100", delete=True)


def test_delete_vm_and_exclusive_lease_success(provider):
    """Delete the exact VM and release its exclusive lease."""
    import cloudmesh.ai.vm.openstack.ChameleonManager as cm

    server = MagicMock()
    server.id = "vm-123"
    server.name = "test-vm"
    server.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-123"
    }

    lease = MagicMock()
    lease.id = "lease-123"
    lease.name = "res-test-vm"
    lease.flavor_reservations = [
        {
            "id": "reservation-123",
            "resource_type": "flavor:instance",
            "amount": 1,
        }
    ]
    lease.device_reservations = []
    lease.node_reservations = []
    lease.fip_reservations = []
    lease.network_reservations = []

    cm.chi.server.list_servers.side_effect = [[server], [], []]
    cm.chi.lease.get_lease.return_value = lease

    with (
        patch.object(provider, "_setup_chi_context"),
        patch.object(provider, "release_floating_ip"),
    ):
        result = provider.delete("test-vm")

    assert result is True
    cm.chi.server.delete_server.assert_called_once_with("vm-123")
    cm.chi.lease.get_lease.assert_called_once_with("lease-123")
    lease.delete.assert_called_once()


def test_delete_vm_without_lease_metadata(provider):
    """Delete a legacy VM without guessing or deleting a lease."""
    import cloudmesh.ai.vm.openstack.ChameleonManager as cm

    server = MagicMock()
    server.id = "vm-legacy"
    server.name = "legacy-vm"
    server.get_metadata.return_value = {}

    cm.chi.server.list_servers.side_effect = [[server], []]

    with (
        patch.object(provider, "_setup_chi_context"),
        patch.object(provider, "release_floating_ip"),
    ):
        result = provider.delete("legacy-vm")

    assert result is True
    cm.chi.server.delete_server.assert_called_once_with("vm-legacy")
    cm.chi.lease.get_lease.assert_not_called()


def test_delete_vm_preserves_shared_lease(provider):
    """Never release a lease referenced by another existing VM."""
    import cloudmesh.ai.vm.openstack.ChameleonManager as cm

    target = MagicMock()
    target.id = "vm-123"
    target.name = "target-vm"
    target.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-shared"
    }

    other = MagicMock()
    other.id = "vm-456"
    other.name = "other-vm"
    other.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-shared"
    }

    lease = MagicMock()
    lease.id = "lease-shared"
    lease.name = "res-target-vm"
    lease.flavor_reservations = [
        {"id": "reservation-123", "amount": 1}
    ]
    lease.device_reservations = []
    lease.node_reservations = []
    lease.fip_reservations = []
    lease.network_reservations = []

    cm.chi.server.list_servers.side_effect = [
        [target, other],
        [other],
        [other],
    ]
    cm.chi.lease.get_lease.return_value = lease

    with (
        patch.object(provider, "_setup_chi_context"),
        patch.object(provider, "release_floating_ip"),
    ):
        with pytest.raises(VMProviderError, match="still associated"):
            provider.delete("target-vm")

    cm.chi.server.delete_server.assert_called_once_with("vm-123")
    lease.delete.assert_not_called()


def test_delete_vm_failure_preserves_lease(provider):
    """Preserve the lease when Nova rejects the VM deletion request."""
    import cloudmesh.ai.vm.openstack.ChameleonManager as cm

    server = MagicMock()
    server.id = "vm-123"
    server.name = "test-vm"
    server.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-123"
    }

    cm.chi.server.list_servers.return_value = [server]
    cm.chi.server.delete_server.side_effect = RuntimeError(
        "Nova deletion failed"
    )

    with (
        patch.object(provider, "_setup_chi_context"),
        patch.object(provider, "release_floating_ip"),
    ):
        with pytest.raises(VMProviderError, match="Nova deletion failed"):
            provider.delete("test-vm")

    cm.chi.server.delete_server.assert_called_once_with("vm-123")
    cm.chi.lease.get_lease.assert_not_called()


def test_delete_vm_timeout_preserves_lease(provider):
    """Preserve the lease when VM deletion cannot be confirmed."""
    import cloudmesh.ai.vm.openstack.ChameleonManager as cm

    server = MagicMock()
    server.id = "vm-123"
    server.name = "test-vm"
    server.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-123"
    }

    cm.chi.server.list_servers.return_value = [server]

    with (
        patch.object(provider, "_setup_chi_context"),
        patch.object(provider, "release_floating_ip"),
        patch.object(
            provider, "_wait_for_server_deletion", return_value=False
        ) as wait_mock,
    ):
        with pytest.raises(VMProviderError, match="Timed out"):
            provider.delete("test-vm")

    cm.chi.server.delete_server.assert_called_once_with("vm-123")
    wait_mock.assert_called_once_with("vm-123")
    cm.chi.lease.get_lease.assert_not_called()


def test_delete_vm_lease_cleanup_failure(provider):
    """Report partial failure when VM deletion succeeds but lease cleanup fails."""
    import cloudmesh.ai.vm.openstack.ChameleonManager as cm

    server = MagicMock()
    server.id = "vm-123"
    server.name = "test-vm"
    server.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-123"
    }

    lease = MagicMock()
    lease.id = "lease-123"
    lease.name = "res-test-vm"
    lease.flavor_reservations = [
        {"id": "reservation-123", "amount": 1}
    ]
    lease.device_reservations = []
    lease.node_reservations = []
    lease.fip_reservations = []
    lease.network_reservations = []
    lease.delete.side_effect = RuntimeError("Blazar unavailable")

    cm.chi.server.list_servers.side_effect = [[server], [], []]
    cm.chi.lease.get_lease.return_value = lease

    with (
        patch.object(provider, "_setup_chi_context"),
        patch.object(provider, "release_floating_ip"),
    ):
        with pytest.raises(VMProviderError, match="Blazar unavailable"):
            provider.delete("test-vm")

    cm.chi.server.delete_server.assert_called_once_with("vm-123")
    lease.delete.assert_called_once()


def test_delete_vm_without_server_id_preserves_lease(provider):
    """Never delete a VM or release its lease without a valid server ID."""
    import cloudmesh.ai.vm.openstack.ChameleonManager as cm

    server = MagicMock()
    server.id = None
    server.name = "test-vm"
    server.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-123"
    }

    cm.chi.server.list_servers.return_value = [server]

    with (
        patch.object(provider, "_setup_chi_context"),
        patch.object(provider, "release_floating_ip") as mock_release,
    ):
        with pytest.raises(VMProviderError, match="server ID is unavailable"):
            provider.delete("test-vm")

    mock_release.assert_not_called()
    cm.chi.server.delete_server.assert_not_called()
    server.delete.assert_not_called()
    cm.chi.lease.get_lease.assert_not_called()


def test_delete_preserves_lease_when_legacy_vm_exists(provider):
    """Unknown ownership on another VM must prevent lease cleanup."""
    import cloudmesh.ai.vm.openstack.ChameleonManager as cm

    target = MagicMock()
    target.id = "server-123"
    target.name = "test-vm"
    target.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-123"
    }

    legacy = MagicMock()
    legacy.id = "server-legacy"
    legacy.name = "legacy-vm"
    legacy.get_metadata.return_value = {}

    lease = MagicMock()
    lease.id = "lease-123"
    lease.name = "res-test-vm"
    lease.flavor_reservations = [{"id": "reservation-123", "amount": 1}]

    cm.chi.server.list_servers.side_effect = [
        [target, legacy],
        [legacy],
        [legacy],
    ]
    cm.chi.lease.get_lease.return_value = lease

    with (
        patch.object(provider, "_setup_chi_context"),
        patch.object(provider, "release_floating_ip"),
    ):
        with pytest.raises(VMProviderError, match="lease metadata is missing"):
            provider.delete("test-vm")

    cm.chi.server.delete_server.assert_called_once_with("server-123")
    lease.delete.assert_not_called()


def test_delete_releases_lease_with_unrelated_tagged_vm(provider):
    """A VM with a different lease ID must not block cleanup."""
    import cloudmesh.ai.vm.openstack.ChameleonManager as cm

    target = MagicMock()
    target.id = "server-123"
    target.name = "test-vm"
    target.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-123"
    }

    unrelated = MagicMock()
    unrelated.id = "server-other"
    unrelated.name = "other-vm"
    unrelated.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-other"
    }

    lease = MagicMock()
    lease.id = "lease-123"
    lease.name = "res-test-vm"
    lease.flavor_reservations = [{"id": "reservation-123", "amount": 1}]
    lease.device_reservations = []
    lease.node_reservations = []
    lease.fip_reservations = []
    lease.network_reservations = []

    cm.chi.server.list_servers.side_effect = [
        [target, unrelated],
        [unrelated],
        [unrelated],
    ]
    cm.chi.lease.get_lease.return_value = lease

    with (
        patch.object(provider, "_setup_chi_context"),
        patch.object(provider, "release_floating_ip"),
    ):
        assert provider.delete("test-vm") is True

    cm.chi.server.delete_server.assert_called_once_with("server-123")
    lease.delete.assert_called_once_with()


@pytest.fixture
def lease_start_setup(provider, monkeypatch):
    """Prepare Provider.start() for isolated lease tests."""
    import cloudmesh.ai.vm.openstack.ChameleonManager as cm
    from cloudmesh.ai.vm.openstack.OpenstackManager import OpenstackManager

    monkeypatch.delenv("CLOUDMESH_CHAMELEON_MOCK", raising=False)

    provider.config["clouds"]["chameleon"].update({
        "key_path": "/tmp/test-chameleon-key.pub",
        "image": "test-image",
        "flavor": "test-flavor",
    })

    connection = MagicMock()
    connection.compute = MagicMock()

    monkeypatch.setattr(
        OpenstackManager,
        "_get_sdk_conn",
        lambda self: connection,
    )

    cm.chi.server.list_keypair.return_value = []
    cm.chi.server.get_server.return_value = None
    cm.chi.server.get_flavor_id.return_value = "flavor-123"

    with (
        patch.object(provider, "_setup_chi_context"),
        patch("builtins.open", mock_open(read_data="ssh-rsa TESTKEY")),
    ):
        yield cm


def test_start_rejects_existing_active_lease(provider, lease_start_setup):
    """An active lease must not be reused for a new VM."""
    cm = lease_start_setup

    existing = MagicMock()
    existing.name = "res-test-vm"
    existing.id = "existing-lease"
    existing.status = "ACTIVE"

    cm.chi.lease.list_leases.return_value = [existing]

    with pytest.raises(VMProviderError, match="Refusing to reuse"):
        provider.start(name="test-vm")

    cm.chi.lease.Lease.assert_not_called()


def test_start_rejects_existing_pending_lease(provider, lease_start_setup):
    """Pending reservations must also be protected."""
    cm = lease_start_setup

    existing = MagicMock()
    existing.name = "res-test-vm"
    existing.id = "pending-lease"
    existing.status = "PENDING"

    cm.chi.lease.list_leases.return_value = [existing]

    with pytest.raises(VMProviderError, match="Refusing to reuse"):
        provider.start(name="test-vm")

    cm.chi.lease.Lease.assert_not_called()


def test_start_allows_terminated_lease_name(provider, lease_start_setup):
    """A terminated lease must not trigger the active-lease conflict."""
    cm = lease_start_setup

    existing = MagicMock()
    existing.name = "res-test-vm"
    existing.id = "old-lease"
    existing.status = "TERMINATED"

    cm.chi.lease.list_leases.return_value = [existing]

    lease = cm.chi.lease.Lease.return_value
    lease.id = "new-lease"
    lease.flavor_reservations = [{"id": "reservation-123"}]

    server = cm.chi.server.Server.return_value
    server.id = "server-123"

    provider.start(name="test-vm", assign_ip=False)

    lease.submit.assert_called_once_with(idempotent=False)
    server.set_metadata_item.assert_called_once_with(
        "cloudmesh_lease_id", "new-lease"
    )


def test_start_lease_listing_failure_blocks_creation(provider, lease_start_setup):
    """Blazar errors must never be interpreted as an empty lease list."""
    cm = lease_start_setup

    cm.chi.lease.list_leases.side_effect = RuntimeError(
        "Blazar API unavailable"
    )

    with pytest.raises(Exception, match="Blazar API unavailable"):
        provider.start(name="test-vm")

    cm.chi.lease.Lease.assert_not_called()


def test_start_metadata_failure_preserves_resources(provider, lease_start_setup):
    """Metadata failure must report resources without deleting them."""
    cm = lease_start_setup

    cm.chi.lease.list_leases.return_value = []

    lease = cm.chi.lease.Lease.return_value
    lease.id = "lease-123"
    lease.flavor_reservations = [{"id": "reservation-123"}]

    server = cm.chi.server.Server.return_value
    server.id = "server-123"
    server.set_metadata_item.side_effect = RuntimeError(
        "Nova metadata API unavailable"
    )

    with pytest.raises(VMProviderError) as excinfo:
        provider.start(name="test-vm", assign_ip=False)

    message = str(excinfo.value)

    assert "server-123" in message
    assert "lease-123" in message
    assert "Inspect Chameleon resources before retrying" in message

    server.set_metadata_item.assert_called_once_with(
        "cloudmesh_lease_id", "lease-123"
    )
    cm.chi.server.delete_server.assert_not_called()
    lease.delete.assert_not_called()


def test_delete_aborts_when_server_listing_unavailable(provider):
    """Never attempt VM deletion when the server listing is unavailable."""
    import cloudmesh.ai.vm.openstack.ChameleonManager as cm

    cm.chi.server.list_servers.return_value = None

    with patch.object(provider, "_setup_chi_context"):
        with pytest.raises(
            VMProviderError,
            match="Unable to retrieve Chameleon server listing",
        ):
            provider.delete("test-vm")

    cm.chi.server.delete_server.assert_not_called()
    cm.chi.lease.get_lease.assert_not_called()


def test_delete_preserves_lease_with_malformed_flavor_reservation(provider):
    """Malformed reservation data must never trigger lease deletion."""
    import cloudmesh.ai.vm.openstack.ChameleonManager as cm

    server = MagicMock()
    server.id = "server-123"
    server.name = "test-vm"
    server.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-123"
    }

    lease = MagicMock()
    lease.id = "lease-123"
    lease.name = "res-test-vm"
    lease.flavor_reservations = ["invalid-reservation"]

    cm.chi.server.list_servers.side_effect = [
        [server],
        [],
        [],
    ]
    cm.chi.lease.get_lease.return_value = lease

    with (
        patch.object(provider, "_setup_chi_context"),
        patch.object(provider, "release_floating_ip"),
    ):
        with pytest.raises(
            VMProviderError,
            match="does not have an exclusive single-instance",
        ):
            provider.delete("test-vm")

    cm.chi.server.delete_server.assert_called_once_with("server-123")
    lease.delete.assert_not_called()


def test_start_lease_activation_failure_preserves_resources(
    provider, lease_start_setup
):
    """An uncertain lease activation must preserve resources for inspection."""
    cm = lease_start_setup
    cm.chi.lease.list_leases.return_value = []

    lease = cm.chi.lease.Lease.return_value
    lease.id = "lease-123"
    lease.wait.side_effect = TimeoutError("Lease activation timed out")

    with pytest.raises(VMProviderError) as excinfo:
        provider.start(name="test-vm", assign_ip=False)

    assert "Lease activation timed out" in str(excinfo.value)
    assert "VM name: test-vm" in str(excinfo.value)
    assert "lease ID: lease-123" in str(excinfo.value)
    assert "inspect them before attempting cleanup" in str(excinfo.value)
    cm.chi.server.Server.assert_not_called()
    cm.chi.server.delete_server.assert_not_called()
    lease.delete.assert_not_called()


def test_start_vm_launch_failure_preserves_lease(provider, lease_start_setup):
    """A failed VM launch must not automatically destroy its reservation."""
    cm = lease_start_setup
    cm.chi.lease.list_leases.return_value = []

    lease = cm.chi.lease.Lease.return_value
    lease.id = "lease-123"
    lease.flavor_reservations = [{"id": "reservation-123"}]
    lease.get_reserved_flavors.return_value = [MagicMock(name="reserved-flavor")]

    server = cm.chi.server.Server.return_value
    server.submit.side_effect = RuntimeError("Nova server creation failed")

    with pytest.raises(VMProviderError) as excinfo:
        provider.start(name="test-vm", assign_ip=False)

    assert "Nova server creation failed" in str(excinfo.value)
    assert "VM name: test-vm" in str(excinfo.value)
    assert "lease ID: lease-123" in str(excinfo.value)
    assert "inspect them before attempting cleanup" in str(excinfo.value)
    lease.delete.assert_not_called()
    cm.chi.server.delete_server.assert_not_called()


def test_start_pre_vm_failure_rolls_back_owned_lease(
    provider, lease_start_setup
):
    """Release a newly created lease when VM submission never began."""
    cm = lease_start_setup
    cm.chi.lease.list_leases.return_value = []

    lease = cm.chi.lease.Lease.return_value
    lease.id = "lease-123"
    lease.name = "res-test-vm"
    lease.flavor_reservations = [
        {"id": "reservation-123", "amount": 1}
    ]
    lease.device_reservations = []
    lease.node_reservations = []
    lease.fip_reservations = []
    lease.network_reservations = []

    lease.get_reserved_flavors.side_effect = RuntimeError(
        "Reserved flavor unavailable"
    )

    cm.chi.server.list_servers.return_value = []

    with pytest.raises(VMProviderError) as excinfo:
        provider.start(name="test-vm", assign_ip=False)

    assert "Reserved flavor unavailable" in str(excinfo.value)
    cm.chi.server.Server.assert_not_called()
    cm.chi.server.delete_server.assert_not_called()
    lease.delete.assert_called_once_with()


def test_start_pre_vm_failure_preserves_referenced_lease(
    provider, lease_start_setup
):
    """Never roll back a lease referenced by an existing VM."""
    cm = lease_start_setup
    cm.chi.lease.list_leases.return_value = []

    lease = cm.chi.lease.Lease.return_value
    lease.id = "lease-123"
    lease.name = "res-test-vm"
    lease.flavor_reservations = [
        {"id": "reservation-123", "amount": 1}
    ]
    lease.device_reservations = []
    lease.node_reservations = []
    lease.fip_reservations = []
    lease.network_reservations = []

    lease.get_reserved_flavors.side_effect = RuntimeError(
        "Reserved flavor unavailable"
    )

    existing_server = MagicMock()
    existing_server.id = "other-server-456"
    existing_server.name = "other-vm"
    existing_server.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-123"
    }
    cm.chi.server.list_servers.return_value = [existing_server]

    with pytest.raises(VMProviderError) as excinfo:
        provider.start(name="test-vm", assign_ip=False)

    message = str(excinfo.value)
    assert "Reserved flavor unavailable" in message
    assert "Lease is referenced by an existing VM" in message
    lease.delete.assert_not_called()
    cm.chi.server.delete_server.assert_not_called()


def test_start_security_group_failure_rolls_back_vm_and_lease(
    provider, lease_start_setup, monkeypatch
):
    """A failed SG attachment rolls back the owned VM before its lease."""
    cm = lease_start_setup
    cm.chi.lease.list_leases.return_value = []

    lease = cm.chi.lease.Lease.return_value
    lease.id = "lease-123"
    lease.name = "res-test-vm"
    lease.flavor_reservations = [
        {"id": "reservation-123", "amount": 1}
    ]
    lease.device_reservations = []
    lease.node_reservations = []
    lease.fip_reservations = []
    lease.network_reservations = []

    server = cm.chi.server.Server.return_value
    server.id = "server-123"
    server.name = "test-vm"
    server.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-123"
    }

    # The server must be absent before provisioning and present afterward.
    cm.chi.server.list_servers.side_effect = [[server], []]
    cm.chi.server.get_server.return_value = None

    monkeypatch.setattr(
        provider,
        "_wait_for_server_deletion",
        MagicMock(return_value=True),
    )

    cm.chi.network.list_security_groups.return_value = [
        MagicMock(name="existing-sg", id="sg-123")
    ]
    server.add_security_group.side_effect = RuntimeError(
        "Security group attachment failed"
    )

    with pytest.raises(VMProviderError) as excinfo:
        provider.start(name="test-vm", assign_ip=False)

    assert "Security group attachment failed" in str(excinfo.value)
    cm.chi.server.delete_server.assert_called_once_with("server-123")
    provider._wait_for_server_deletion.assert_called_once_with("server-123")
    lease.delete.assert_called_once_with()


def test_start_vm_deletion_timeout_preserves_lease(
    provider, lease_start_setup, monkeypatch
):
    """Never release the lease when VM deletion cannot be confirmed."""
    cm = lease_start_setup
    cm.chi.lease.list_leases.return_value = []

    lease = cm.chi.lease.Lease.return_value
    lease.id = "lease-123"
    lease.name = "res-test-vm"
    lease.flavor_reservations = [
        {"id": "reservation-123", "amount": 1}
    ]
    lease.device_reservations = []
    lease.node_reservations = []
    lease.fip_reservations = []
    lease.network_reservations = []

    server = cm.chi.server.Server.return_value
    server.id = "server-123"
    server.name = "test-vm"
    server.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-123"
    }

    cm.chi.server.get_server.return_value = None
    cm.chi.server.list_servers.return_value = [server]

    monkeypatch.setattr(
        provider,
        "_wait_for_server_deletion",
        MagicMock(return_value=False),
    )

    cm.chi.network.list_security_groups.return_value = [
        MagicMock(name="existing-sg", id="sg-123")
    ]
    server.add_security_group.side_effect = RuntimeError(
        "Security group attachment failed"
    )

    with pytest.raises(VMProviderError) as excinfo:
        provider.start(name="test-vm", assign_ip=False)

    message = str(excinfo.value)

    assert "Security group attachment failed" in message
    assert "VM deletion could not be confirmed" in message

    cm.chi.server.delete_server.assert_called_once_with("server-123")
    provider._wait_for_server_deletion.assert_called_once_with("server-123")
    lease.delete.assert_not_called()


def test_start_vm_ownership_mismatch_preserves_resources(
    provider, lease_start_setup
):
    """Never delete a VM whose lease metadata does not match."""
    cm = lease_start_setup
    cm.chi.lease.list_leases.return_value = []

    lease = cm.chi.lease.Lease.return_value
    lease.id = "lease-123"
    lease.name = "res-test-vm"
    lease.flavor_reservations = [
        {"id": "reservation-123", "amount": 1}
    ]
    lease.device_reservations = []
    lease.node_reservations = []
    lease.fip_reservations = []
    lease.network_reservations = []

    server = cm.chi.server.Server.return_value
    server.id = "server-123"
    server.name = "test-vm"
    server.get_metadata.return_value = {
        "cloudmesh_lease_id": "different-lease"
    }

    cm.chi.server.get_server.return_value = None
    cm.chi.server.list_servers.return_value = [server]

    cm.chi.network.list_security_groups.return_value = [
        MagicMock(name="existing-sg", id="sg-123")
    ]
    server.add_security_group.side_effect = RuntimeError(
        "Security group attachment failed"
    )

    with pytest.raises(VMProviderError) as excinfo:
        provider.start(name="test-vm", assign_ip=False)

    message = str(excinfo.value)

    assert "Security group attachment failed" in message
    assert "VM lease ownership could not be verified" in message

    cm.chi.server.delete_server.assert_not_called()
    lease.delete.assert_not_called()


def test_start_rollback_preserves_preexisting_floating_ip(
    provider, lease_start_setup, monkeypatch
):
    """Rollback must not delete an IP allocated before provisioning."""
    cm = lease_start_setup
    cm.chi.lease.list_leases.return_value = []

    lease = cm.chi.lease.Lease.return_value
    lease.id = "lease-123"
    lease.name = "res-test-vm"
    lease.flavor_reservations = [
        {"id": "reservation-123", "amount": 1}
    ]
    lease.device_reservations = []
    lease.node_reservations = []
    lease.fip_reservations = []
    lease.network_reservations = []

    server = cm.chi.server.Server.return_value
    server.id = "server-123"
    server.name = "test-vm"
    server.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-123"
    }
    server.associate_floating_ip.return_value = "129.114.10.20"

    cm.chi.server.get_server.return_value = None
    cm.chi.server.list_servers.side_effect = [[server], []]

    cm.chi.network.neutron.return_value.list_floatingips.return_value = {
        "floatingips": [
            {
                "id": "preexisting-ip-123",
                "floating_ip_address": "129.114.10.20",
                "port_id": None,
            }
        ]
    }

    monkeypatch.setattr(
        provider,
        "_wait_for_server_deletion",
        MagicMock(return_value=True),
    )

    cm.chi.network.list_security_groups.return_value = [
        MagicMock(name="existing-sg", id="sg-123")
    ]
    server.add_security_group.side_effect = RuntimeError(
        "Security group attachment failed"
    )

    with pytest.raises(VMProviderError) as excinfo:
        provider.start(name="test-vm", assign_ip=True)

    assert "Security group attachment failed" in str(excinfo.value)
    server.detach_floating_ip.assert_not_called()
    cm.chi.network.neutron.return_value.delete_floatingip.assert_not_called()
    cm.chi.server.delete_server.assert_called_once_with("server-123")
    lease.delete.assert_called_once_with()


def test_start_rollback_releases_new_floating_ip(
    provider, lease_start_setup, monkeypatch
):
    """Release a newly allocated IP after a verified provisioning failure."""
    cm = lease_start_setup
    cm.chi.lease.list_leases.return_value = []

    lease = cm.chi.lease.Lease.return_value
    lease.id = "lease-123"
    lease.name = "res-test-vm"
    lease.flavor_reservations = [
        {"id": "reservation-123", "amount": 1}
    ]
    lease.device_reservations = []
    lease.node_reservations = []
    lease.fip_reservations = []
    lease.network_reservations = []

    server = cm.chi.server.Server.return_value
    server.id = "server-123"
    server.name = "test-vm"
    server.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-123"
    }
    server.associate_floating_ip.return_value = "129.114.10.20"

    cm.chi.server.get_server.return_value = None
    cm.chi.server.list_servers.side_effect = [[server], []]

    monkeypatch.setattr(
        "chi.network.get_network_id",
        lambda network_name: "public-network-123",
    )

    neutron = cm.chi.network.neutron.return_value
    neutron.create_floatingip.return_value = {
        "floatingip": {
            "id": "new-ip-123",
            "floating_ip_address": "129.114.10.20",
            "port_id": None,
        }
    }
    neutron.list_floatingips.side_effect = [
        {"floatingips": []},
        {
            "floatingips": [
                {
                    "id": "new-ip-123",
                    "floating_ip_address": "129.114.10.20",
                    "port_id": None,  # VM has already been deleted
                }
            ]
        },
    ]

    monkeypatch.setattr(
        provider,
        "_wait_for_server_deletion",
        MagicMock(return_value=True),
    )

    cm.chi.network.list_security_groups.return_value = [
        MagicMock(name="existing-sg", id="sg-123")
    ]
    server.add_security_group.side_effect = RuntimeError(
        "Security group attachment failed"
    )

    with pytest.raises(VMProviderError) as excinfo:
        provider.start(name="test-vm", assign_ip=True)

    assert "Security group attachment failed" in str(excinfo.value)
    cm.chi.server.delete_server.assert_called_once_with("server-123")
    neutron.delete_floatingip.assert_called_once_with("new-ip-123")
    assert server.associate_floating_ip.call_count == 1
    assert neutron.list_floatingips.call_count >= 2
    lease.delete.assert_called_once_with()


def test_start_rollback_deletes_new_security_group(
    provider, lease_start_setup, monkeypatch
):
    """Rollback deletes an owned security group after VM deletion."""
    cm = lease_start_setup
    cm.chi.lease.list_leases.return_value = []

    lease = cm.chi.lease.Lease.return_value
    lease.id = "lease-123"
    lease.name = "res-test-vm"
    lease.flavor_reservations = [{"id": "reservation-123", "amount": 1}]
    lease.device_reservations = []
    lease.node_reservations = []
    lease.fip_reservations = []
    lease.network_reservations = []

    server = cm.chi.server.Server.return_value
    server.id = "server-123"
    server.name = "test-vm"
    server.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-123"
    }

    cm.chi.server.get_server.return_value = None
    cm.chi.server.list_servers.side_effect = [[server], []]

    monkeypatch.setattr(
        provider,
        "_wait_for_server_deletion",
        MagicMock(return_value=True),
    )

    cm.chi.network.list_security_groups.return_value = []
    security_group = cm.chi.network.SecurityGroup.return_value
    security_group.id = "new-sg-123"
    security_group.name = "test-user-allow-ssh"

    neutron = cm.chi.network.neutron.return_value
    neutron.list_security_groups.return_value = {
        "security_groups": [
            {
                "id": "new-sg-123",
                "name": "test-user-allow-ssh",
            }
        ]
    }
    neutron.list_ports.return_value = {"ports": []}

    server.add_security_group.side_effect = RuntimeError(
        "Security group attachment failed"
    )

    with pytest.raises(VMProviderError) as excinfo:
        provider.start(name="test-vm", assign_ip=False)

    assert "Security group attachment failed" in str(excinfo.value)
    cm.chi.server.delete_server.assert_called_once_with("server-123")
    neutron.delete_security_group.assert_called_once_with("new-sg-123")
    lease.delete.assert_called_once_with()

def test_start_rollback_preserves_referenced_security_group(
    provider, lease_start_setup, monkeypatch
):
    """Rollback preserves a security group referenced by another port."""
    cm = lease_start_setup
    cm.chi.lease.list_leases.return_value = []

    lease = cm.chi.lease.Lease.return_value
    lease.id = "lease-123"
    lease.name = "res-test-vm"
    lease.flavor_reservations = [{"id": "reservation-123", "amount": 1}]
    lease.device_reservations = []
    lease.node_reservations = []
    lease.fip_reservations = []
    lease.network_reservations = []

    server = cm.chi.server.Server.return_value
    server.id = "server-123"
    server.name = "test-vm"
    server.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-123"
    }

    cm.chi.server.get_server.return_value = None
    cm.chi.server.list_servers.side_effect = [[server], []]

    monkeypatch.setattr(
        provider,
        "_wait_for_server_deletion",
        MagicMock(return_value=True),
    )

    cm.chi.network.list_security_groups.return_value = []
    security_group = cm.chi.network.SecurityGroup.return_value
    security_group.id = "new-sg-123"
    security_group.name = "test-user-allow-ssh"

    neutron = cm.chi.network.neutron.return_value
    neutron.list_security_groups.return_value = {
        "security_groups": [
            {
                "id": "new-sg-123",
                "name": "test-user-allow-ssh",
            }
        ]
    }
    neutron.list_ports.return_value = {
        "ports": [
            {
                "id": "other-port-123",
                "security_groups": ["new-sg-123"],
            }
        ]
    }

    server.add_security_group.side_effect = RuntimeError(
        "Security group attachment failed"
    )

    with pytest.raises(VMProviderError) as excinfo:
        provider.start(name="test-vm", assign_ip=False)

    assert "Security group attachment failed" in str(excinfo.value)
    cm.chi.server.delete_server.assert_called_once_with("server-123")
    neutron.delete_security_group.assert_not_called()
    assert "still referenced by a network port" in str(excinfo.value)
    lease.delete.assert_called_once_with()

def test_start_rollback_reports_security_group_cleanup_failure(
    provider, lease_start_setup, monkeypatch
):
    """Report security group deletion failures without hiding the cause."""
    cm = lease_start_setup
    cm.chi.lease.list_leases.return_value = []

    lease = cm.chi.lease.Lease.return_value
    lease.id = "lease-123"
    lease.name = "res-test-vm"
    lease.flavor_reservations = [{"id": "reservation-123", "amount": 1}]
    lease.device_reservations = []
    lease.node_reservations = []
    lease.fip_reservations = []
    lease.network_reservations = []

    server = cm.chi.server.Server.return_value
    server.id = "server-123"
    server.name = "test-vm"
    server.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-123"
    }

    cm.chi.server.get_server.return_value = None
    cm.chi.server.list_servers.side_effect = [[server], []]

    monkeypatch.setattr(
        provider,
        "_wait_for_server_deletion",
        MagicMock(return_value=True),
    )

    cm.chi.network.list_security_groups.return_value = []
    security_group = cm.chi.network.SecurityGroup.return_value
    security_group.id = "new-sg-123"
    security_group.name = "test-user-allow-ssh"

    neutron = cm.chi.network.neutron.return_value
    neutron.list_security_groups.return_value = {
        "security_groups": [
            {
                "id": "new-sg-123",
                "name": "test-user-allow-ssh",
            }
        ]
    }
    neutron.list_ports.return_value = {"ports": []}
    neutron.delete_security_group.side_effect = RuntimeError(
        "Security group deletion API unavailable"
    )

    server.add_security_group.side_effect = RuntimeError(
        "Security group attachment failed"
    )

    with pytest.raises(VMProviderError) as excinfo:
        provider.start(name="test-vm", assign_ip=False)

    assert "Security group attachment failed" in str(excinfo.value)
    cm.chi.server.delete_server.assert_called_once_with("server-123")
    neutron.delete_security_group.assert_called_once_with("new-sg-123")
    assert "Security group deletion API unavailable" in str(excinfo.value)
    assert "Security group attachment failed" in str(excinfo.value)
    lease.delete.assert_called_once_with()


def test_start_floating_ip_allocation_failure_preserves_uncertain_resources(
    provider, lease_start_setup, monkeypatch
):
    """Do not delete an IP when allocation outcome is uncertain."""
    cm = lease_start_setup
    cm.chi.lease.list_leases.return_value = []

    lease = cm.chi.lease.Lease.return_value
    lease.id = "lease-123"
    lease.name = "res-test-vm"
    lease.flavor_reservations = [{"id": "reservation-123", "amount": 1}]
    lease.device_reservations = []
    lease.node_reservations = []
    lease.fip_reservations = []
    lease.network_reservations = []

    server = cm.chi.server.Server.return_value
    server.id = "server-123"
    server.name = "test-vm"
    server.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-123"
    }

    cm.chi.server.get_server.return_value = None
    cm.chi.server.list_servers.side_effect = [[server], []]

    monkeypatch.setattr(
        provider,
        "_wait_for_server_deletion",
        MagicMock(return_value=True),
    )
    monkeypatch.setattr(
        "chi.network.get_network_id",
        lambda network_name: "public-network-123",
    )

    neutron = cm.chi.network.neutron.return_value
    neutron.list_floatingips.return_value = {"floatingips": []}
    neutron.create_floatingip.side_effect = TimeoutError(
        "Floating IP allocation request timed out"
    )

    with pytest.raises(VMProviderError) as excinfo:
        provider.start(name="test-vm", assign_ip=True)

    message = str(excinfo.value)
    assert "Floating IP allocation request timed out" in message
    assert "inspect them before attempting cleanup" in message

    neutron.delete_floatingip.assert_not_called()
    cm.chi.server.delete_server.assert_called_once_with("server-123")
    provider._wait_for_server_deletion.assert_called_once_with("server-123")
    lease.delete.assert_called_once_with()

def test_start_security_group_creation_timeout_preserves_unknown_group(
    provider, lease_start_setup, monkeypatch
):
    """Preserve an unidentified group after a creation timeout."""
    cm = lease_start_setup
    cm.chi.lease.list_leases.return_value = []

    lease = cm.chi.lease.Lease.return_value
    lease.id = "lease-123"
    lease.name = "res-test-vm"
    lease.flavor_reservations = [{"id": "reservation-123", "amount": 1}]
    lease.device_reservations = []
    lease.node_reservations = []
    lease.fip_reservations = []
    lease.network_reservations = []

    server = cm.chi.server.Server.return_value
    server.id = "server-123"
    server.name = "test-vm"
    server.get_metadata.return_value = {
        "cloudmesh_lease_id": "lease-123"
    }

    cm.chi.server.get_server.return_value = None
    cm.chi.server.list_servers.side_effect = [[server], []]

    monkeypatch.setattr(
        provider,
        "_wait_for_server_deletion",
        MagicMock(return_value=True),
    )

    cm.chi.network.list_security_groups.return_value = []
    security_group = cm.chi.network.SecurityGroup.return_value
    security_group.id = "new-sg-123"
    security_group.name = "test-user-allow-ssh"
    security_group.submit.side_effect = TimeoutError(
        "Security group creation request timed out"
    )

    neutron = cm.chi.network.neutron.return_value
    neutron.list_security_groups.return_value = {
        "security_groups": [
            {
                "id": "new-sg-123",
                "name": "test-user-allow-ssh",
            }
        ]
    }
    neutron.list_ports.return_value = {"ports": []}

    server.add_security_group.side_effect = RuntimeError(
        "Security group attachment failed"
    )

    with pytest.raises(VMProviderError) as excinfo:
        provider.start(name="test-vm", assign_ip=False)

    message = str(excinfo.value)
    assert "Security group creation request timed out" in message
    assert "VM name: test-vm" in message

    security_group.submit.assert_called_once_with()
    server.add_security_group.assert_not_called()
    neutron.delete_security_group.assert_not_called()
    cm.chi.server.delete_server.assert_called_once_with("server-123")
    lease.delete.assert_called_once_with()
