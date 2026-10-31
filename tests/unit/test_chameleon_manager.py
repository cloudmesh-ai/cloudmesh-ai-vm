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
