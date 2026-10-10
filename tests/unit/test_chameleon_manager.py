import pytest
from unittest.mock import MagicMock, patch
from cloudmesh.ai.vm.openstack.ChameleonManager import Provider
from cloudmesh.ai.vm.exceptions import VMProviderError
from .mock_chi import MockChi

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
                "domain_name": "Default"
            }
        }
    }

@pytest.fixture
def mock_chi():
    return MockChi()

@pytest.fixture
def provider(mock_config, mock_chi):
    with patch("cloudmesh.ai.vm.openstack.ChameleonManager.chi", mock_chi), \
         patch("cloudmesh.ai.vm.openstack.ChameleonManager.authenticate_chi_from_cloud"):
        p = Provider(mock_config, cloud_name="chameleon")
        return p

def test_list_regions(provider, mock_chi):
    # The mock_chi.context.list_sites already returns sites by default
    regions = provider.list_regions()

    assert isinstance(regions, list)
    assert len(regions) >= 1
    tacc_region = next((r for r in regions if r["name"] == "kvm@tacc"), None)
    assert tacc_region is not None
    assert tacc_region["description"] == "TACC KVM site"

def test_create_reservation_success(provider, mock_chi):
    result = provider.create_reservation(
        name="smoke-reservation",
        node_type="bare_metal",
        count=1,
        duration=1
    )

    # create_reservation returns the lease ID (string) in our mock
    assert isinstance(result, str)
    assert result.startswith("lease-")
    assert result in mock_chi.leases

def test_create_reservation_no_project(provider, mock_chi):
    # Modify config to remove project_name
    provider.config["clouds"]["chameleon"]["project_name"] = None

    result = provider.create_reservation(
        name="smoke-reservation",
        node_type="bare_metal",
        count=1
    )

    assert result is None

def test_get_account_info_success(provider, mock_chi):
    # Setup state in the mock
    mock_chi.config["project_id"] = "proj-123"
    mock_chi.config["user_id"] = "user-456"
    mock_chi.config["allocation"] = "1000 SU"

    info = provider.get_account_info()

    assert info["site"] == "KVM@TACC"
    assert info["project_name"] == "test-project"
    assert info["project_id"] == "proj-123"
    assert info["user_id"] == "user-456"
    assert info["allocation"] == "1000 SU"
