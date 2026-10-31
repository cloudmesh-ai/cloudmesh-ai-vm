from unittest.mock import MagicMock, patch

from types import SimpleNamespace
import pytest

from cloudmesh.ai.vm.openstack.ChameleonManager import Provider


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
    patchers = [
        patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi"),
        patch("cloudmesh.ai.vm.openstack.ChameleonManager.network"),
        patch("cloudmesh.ai.vm.openstack.ChameleonManager.authenticate_chi_from_cloud"),
    ]

    mocks = [p.start() for p in patchers]
    mock_chi = mocks[0]

    # Update the other mocks to refer to the main mock_chi's sub-mocks
    mocks[1].network = mock_chi.network

    # Configure basic defaults for the mock_chi to avoid common attribute errors
    mock_chi.get.side_effect = lambda key: {
        "site": "kvm@tacc",
        "project_name": "test-project",
        "project_id": "proj-123",
        "user_id": "user-456",
        "allocation": "1000 SU",
    }.get(key)

    try:
        p = Provider(mock_config, cloud_name="chameleon")
        yield p
    finally:
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


def test_delete_does_not_target_unrelated_vm(provider):
    """A missing VM name must never trigger deletion of another VM."""
    existing_server = MagicMock()
    existing_server.name = "important-vm"
    existing_server.id = "server-123"

    with patch.object(provider, "_setup_chi_context"), patch(
        "cloudmesh.ai.vm.openstack.ChameleonManager.chi"
    ) as mock_chi:
        mock_chi.server.list_servers.return_value = [existing_server]
        mock_chi.server.get_server.return_value = None

        result = provider.delete("nonexistent-vm")

        assert result is False
        mock_chi.server.delete_server.assert_not_called()
        existing_server.delete.assert_not_called()


def test_delete_targets_exact_vm_name(provider):
    """Deletion must target only the VM whose name matches exactly."""
    target = MagicMock()
    target.name = "smoke-vm-123"
    target.id = "target-server-id"

    unrelated = MagicMock()
    unrelated.name = "smoke-vm-123-other"
    unrelated.id = "unrelated-server-id"

    with patch.object(provider, "_setup_chi_context"), patch.object(
        provider, "release_floating_ip"
    ), patch(
        "cloudmesh.ai.vm.openstack.ChameleonManager.chi"
    ) as mock_chi:
        mock_chi.server.list_servers.return_value = [unrelated, target]
        mock_chi.server.get_server.return_value = None

        result = provider.delete("smoke-vm-123")

        assert result is True
        mock_chi.server.delete_server.assert_called_once_with("target-server-id")
        unrelated.delete.assert_not_called()


def test_delete_rejects_mismatched_direct_lookup(provider):
    """An incorrect direct lookup must never delete an unrelated VM."""
    unrelated = MagicMock()
    unrelated.name = "important-production-vm"
    unrelated.id = "production-server-id"

    with patch.object(provider, "_setup_chi_context"), patch(
        "cloudmesh.ai.vm.openstack.ChameleonManager.chi"
    ) as mock_chi:
        mock_chi.server.get_server.return_value = unrelated
        mock_chi.server.list_servers.return_value = [unrelated]

        result = provider.delete("nonexistent-smoke-vm")

        assert result is False
        mock_chi.server.delete_server.assert_not_called()
        unrelated.delete.assert_not_called()


def test_list_propagates_server_api_failure(provider):
    """A failed VM listing must not be mistaken for an empty project."""
    with patch.object(provider, "_setup_chi_context"), patch(
        "cloudmesh.ai.vm.openstack.ChameleonManager.chi"
    ) as mock_chi:
        mock_chi.server.list_servers.side_effect = RuntimeError(
            "Simulated Chameleon API outage"
        )

        with pytest.raises(RuntimeError, match="Simulated Chameleon API outage"):
            provider.list()


def test_vm_exists_matches_exact_name_only():
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    from cloudmesh.ai.vm.openstack.ChameleonManager import Provider

    manager = object.__new__(Provider)
    manager._setup_chi_context = MagicMock()

    with patch(
        "cloudmesh.ai.vm.openstack.ChameleonManager.chi.server.nova"
    ) as mock_nova:
        mock_nova.return_value.servers.list.return_value = [
            SimpleNamespace(name="test-vm-1"),
            SimpleNamespace(name="test-vm-other"),
        ]

        assert manager._vm_exists("test-vm-1") is True
        assert manager._vm_exists("test-vm") is False


def test_vm_exists_propagates_nova_api_failure():
    from unittest.mock import MagicMock, patch

    import pytest

    from cloudmesh.ai.vm.openstack.ChameleonManager import Provider

    manager = object.__new__(Provider)
    manager._setup_chi_context = MagicMock()

    with patch(
        "cloudmesh.ai.vm.openstack.ChameleonManager.chi.server.nova"
    ) as mock_nova:
        mock_nova.return_value.servers.list.side_effect = RuntimeError(
            "Nova API unavailable"
        )

        with pytest.raises(RuntimeError, match="Nova API unavailable"):
            manager._vm_exists("test-vm")


def test_start_rejects_explicit_vm_name_collision():
    from unittest.mock import MagicMock, patch

    import pytest

    from cloudmesh.ai.vm.openstack.ChameleonManager import Provider

    manager = object.__new__(Provider)
    manager.cloud_name = "chameleon"
    manager._setup_chi_context = MagicMock()
    manager.get_cloud_config = MagicMock(
        return_value={
            "username": "test-user",
            "key_name": "test-key",
            "key_path": "/tmp/test-public-key",
            "image": "test-image",
            "flavor": "test-flavor",
        }
    )
    manager._vm_exists = MagicMock(return_value=True)
    manager.print = MagicMock()

    with (
        patch("builtins.open", create=True) as mock_open,
        patch(
            "cloudmesh.ai.vm.openstack.ChameleonManager.chi"
        ) as mock_chi,
    ):
        mock_open.return_value.__enter__.return_value.read.return_value = (
            "ssh-ed25519 AAAATEST"
        )
        mock_chi.server.list_keypair.return_value = [
            MagicMock(name="unused")
        ]

        with pytest.raises(Exception, match="refusing automatic renaming"):
            manager.start(name="existing-test-vm")

        mock_open.assert_not_called()
        mock_chi.server.list_keypair.assert_not_called()
        mock_chi.server.update_keypair.assert_not_called()
        mock_chi.lease.Lease.assert_not_called()
        mock_chi.server.Server.assert_not_called()


@pytest.mark.parametrize(
    ("cloud_keys", "list_error", "expected_message"),
    [
        (
            [SimpleNamespace(name="test-key", public_key="ssh-ed25519 DIFFERENT")],
            None,
            "refusing to overwrite an existing cloud keypair",
        ),
        (
            None,
            RuntimeError("Cloud API unavailable"),
            "Could not list cloud keypairs",
        ),
    ],
)
def test_start_fails_safely_on_ssh_key_errors(
    cloud_keys, list_error, expected_message
):
    from unittest.mock import MagicMock, patch
    from cloudmesh.ai.vm.openstack.ChameleonManager import Provider

    manager = object.__new__(Provider)
    manager.cloud_name = "chameleon"
    manager._setup_chi_context = MagicMock()
    manager.get_cloud_config = MagicMock(
        return_value={
            "username": "test-user",
            "key_name": "test-key",
            "key_path": "/tmp/test-public-key",
            "image": "test-image",
            "flavor": "test-flavor",
        }
    )
    manager._vm_exists = MagicMock(return_value=False)
    manager.print = MagicMock()

    with (
        patch("builtins.open", create=True) as mock_open,
        patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi,
    ):
        mock_open.return_value.__enter__.return_value.read.return_value = (
            "ssh-ed25519 LOCAL"
        )

        if list_error is not None:
            mock_chi.server.list_keypair.side_effect = list_error
        else:
            mock_chi.server.list_keypair.return_value = cloud_keys

        with pytest.raises(Exception, match=expected_message):
            manager.start(name="new-test-vm")

        mock_chi.server.update_keypair.assert_not_called()
        mock_chi.lease.Lease.assert_not_called()
        mock_chi.server.Server.assert_not_called()

    print(f"Verified safe startup failure: {expected_message}")


def test_start_rejects_existing_custom_security_group():
    from unittest.mock import MagicMock, patch
    from cloudmesh.ai.vm.openstack.ChameleonManager import Provider

    manager = object.__new__(Provider)
    manager.cloud_name = "chameleon"
    manager._setup_chi_context = MagicMock()
    manager.get_cloud_config = MagicMock(
        return_value={
            "username": "test-user",
            "key_name": "test-key",
            "key_path": "/tmp/test-public-key",
            "image": "test-image",
            "flavor": "test-flavor",
        }
    )
    manager._vm_exists = MagicMock(return_value=False)
    manager.print = MagicMock()

    with patch(
        "cloudmesh.ai.vm.openstack.ChameleonManager.chi"
    ) as mock_chi:
        mock_chi.network.list_security_groups.return_value = [
            SimpleNamespace(name="existing-test-sg")
        ]

        with pytest.raises(
            Exception,
            match="refusing to modify an existing security group",
        ):
            manager.start(
                name="new-test-vm",
                security_group="existing-test-sg",
            )

        mock_chi.server.list_keypair.assert_not_called()
        mock_chi.server.update_keypair.assert_not_called()
        mock_chi.lease.Lease.assert_not_called()
        mock_chi.server.Server.assert_not_called()

    print("Verified existing custom security group is protected.")


def test_start_rejects_custom_security_group_created_during_startup(tmp_path):
    """A group appearing after preflight must never receive new rules."""
    from types import SimpleNamespace
    from unittest.mock import MagicMock, patch

    import pytest

    from cloudmesh.ai.vm.openstack.ChameleonManager import Provider

    public_key = tmp_path / "test-key.pub"
    public_key.write_text("ssh-ed25519 TESTKEY")

    manager = object.__new__(Provider)
    manager.cloud_name = "chameleon"
    manager._setup_chi_context = MagicMock()
    manager._vm_exists = MagicMock(return_value=False)
    manager.print = MagicMock()
    manager.get_cloud_config = MagicMock(
        return_value={
            "username": "test-user",
            "key_name": "test-key",
            "key_path": str(public_key),
            "image": "test-image",
            "flavor": "test-flavor",
        }
    )

    existing_group = SimpleNamespace(
        name="smoke-test-sg",
        id="someone-elses-group",
    )

    with patch(
        "cloudmesh.ai.vm.openstack.ChameleonManager.chi"
    ) as mock_chi, patch(
        "cloudmesh.ai.vm.openstack.ChameleonManager.network"
    ) as mock_network:
        mock_chi.network.list_security_groups.return_value = []
        mock_network.list_security_groups.return_value = [existing_group]

        mock_chi.server.list_keypair.return_value = [
            SimpleNamespace(
                name="test-key",
                public_key="ssh-ed25519 TESTKEY",
            )
        ]

        mock_chi.lease.Lease.return_value.id = "test-reservation"
        mock_chi.lease.Lease.return_value.get_reserved_flavors.return_value = [
            SimpleNamespace(name="test-flavor")
        ]

        with pytest.raises(Exception, match="appeared during startup"):
            manager.start(
                name="smoke-test-vm",
                security_group="smoke-test-sg",
                assign_ip=False,
            )

        mock_chi.network.list_security_groups.assert_called_once_with(
            name_filter="smoke-test-sg"
        )
        mock_network.neutron.return_value.create_security_group_rule.assert_not_called()
        mock_network.SecurityGroup.assert_not_called()
        mock_chi.server.Server.return_value.add_security_group.assert_not_called()
