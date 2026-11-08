from unittest.mock import MagicMock, patch

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
        patch("cloudmesh.ai.vm.openstack.ChameleonManager.server"),
        patch("cloudmesh.ai.vm.openstack.ChameleonManager.lease"),
        patch("cloudmesh.ai.vm.openstack.ChameleonManager.network"),
        patch("cloudmesh.ai.vm.openstack.ChameleonManager.keypair"),
        patch("cloudmesh.ai.vm.openstack.ChameleonManager.authenticate_chi_from_cloud"),
    ]

    mocks = [p.start() for p in patchers]
    mock_chi = mocks[0]

    # Update the other mocks to refer to the main mock_chi's sub-mocks
    mocks[1].server = mock_chi.server
    mocks[2].lease = mock_chi.lease
    mocks[3].network = mock_chi.network
    mocks[4].keypair = mock_chi.keypair

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


def test_list_vm_with_different_lease_name(provider):
    """A missing VM-name TTL mapping must not hide an existing VM."""
    from types import SimpleNamespace

    vm = SimpleNamespace(
        name="kbass-comp488-chameleon-vm",
        id="vm-123",
        status="ACTIVE",
        addresses={"sharednet1": [{"addr": "10.56.3.219"}]},
        flavor="m1.small",
        image_name="CC-Ubuntu24.04",
    )
    lease = SimpleNamespace(
        name="kbass-comp488-chameleon-test",
        end_date="2026-11-08T02:35:00",
        flavor_reservations=[],
        node_reservations=[],
        fip_reservations=[],
        network_reservations=[],
        device_reservations=[],
    )

    with patch.object(provider, "_setup_chi_context"), \
         patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi:
        mock_chi.server.list_servers.return_value = [vm]
        mock_chi.lease.list_leases.return_value = [lease]
        mock_chi.server.list_flavors.return_value = []

        results = provider.list()

    assert len(results) == 1
    assert results[0]["name"] == vm.name
    assert results[0]["status"] == "ACTIVE"
    assert results[0]["ip"] == "10.56.3.219"
    assert results[0]["ttl"] == "N/A"


def test_ttl_humanize_accepts_iso_date_string(provider):
    """ISO-formatted lease expiration dates should produce a valid TTL."""
    from datetime import datetime, timedelta, timezone

    expiration = datetime.now(timezone.utc) + timedelta(hours=2)
    result = provider.ttl_humanize(expiration.isoformat())

    assert "hour" in result.lower()
    assert result != "Unknown"


def test_list_vm_uses_matching_reservation_ttl(provider):
    """VM TTL should come from its reservation, not its name."""
    from datetime import datetime, timedelta, timezone
    from types import SimpleNamespace

    reservation_id = "826f0743-a7f5-4a9b-9f0e-ba0f189889e8"
    expiration = datetime.now(timezone.utc) + timedelta(hours=2)

    vm = SimpleNamespace(
        name="test-vm",
        id="vm-123",
        status="ACTIVE",
        addresses={},
        flavor=f"reservation:{reservation_id}",
        image_name="CC-Ubuntu24.04",
    )
    lease = SimpleNamespace(
        name="different-lease-name",
        end_date=expiration.isoformat(),
        flavor_reservations=[
            {"id": reservation_id, "resource_properties": {"name": "m1.small"}}
        ],
        node_reservations=[],
        fip_reservations=[],
        network_reservations=[],
        device_reservations=[],
    )

    with patch.object(provider, "_setup_chi_context"), \
         patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi") as mock_chi:
        mock_chi.server.list_servers.return_value = [vm]
        mock_chi.lease.list_leases.return_value = [lease]
        mock_chi.server.list_flavors.return_value = []

        results = provider.list()

    assert len(results) == 1
    assert results[0]["flavor"] == "m1.small"
    assert "hour" in results[0]["ttl"].lower()
