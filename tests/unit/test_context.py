import pytest
from unittest.mock import MagicMock, patch
import click
from cloudmesh.ai.command.vm._shared.context import resolve_vms, VMContext

@pytest.fixture
def mock_ctx():
    ctx = MagicMock(spec=click.Context)
    ctx.obj = VMContext()
    return ctx

@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.cloud_name = "test-cloud"
    provider.get_cloud_config.return_value = {"username": "testuser"}
    provider.list.return_value = [
        {"name": "testuser-1", "created_at": "2023-01-01T00:00:00Z"},
        {"name": "testuser-2", "created_at": "2023-01-02T00:00:00Z"},
        {"name": "web-prod-1", "created_at": "2023-01-03T00:00:00Z"},
        {"name": "web-prod-2", "created_at": "2023-01-04T00:00:00Z"},
        {"name": "db-master", "created_at": "2023-01-05T00:00:00Z"},
    ]
    return provider

@patch("cloudmesh.ai.command.vm._shared.context.get_active_provider")
def test_resolve_vms_single_name(mock_get_provider, mock_ctx, mock_provider):
    mock_get_provider.return_value = mock_provider
    assert resolve_vms(mock_ctx, name="testuser-1") == ["testuser-1"]

@patch("cloudmesh.ai.command.vm._shared.context.get_active_provider")
def test_resolve_vms_range_expansion(mock_get_provider, mock_ctx, mock_provider):
    mock_get_provider.return_value = mock_provider
    # Test explicit hostlist expansion
    assert resolve_vms(mock_ctx, name="node[1-2]") == ["node-1", "node-2"]
    # Test range with existing base
    assert resolve_vms(mock_ctx, name="testuser[1-2]") == ["testuser-1", "testuser-2"]

@patch("cloudmesh.ai.command.vm._shared.context.get_active_provider")
def test_resolve_vms_wildcard_match(mock_get_provider, mock_ctx, mock_provider):
    mock_get_provider.return_value = mock_provider
    # Match multiple
    assert resolve_vms(mock_ctx, name="web-*") == ["web-prod-1", "web-prod-2"]
    # Match single
    assert resolve_vms(mock_ctx, name="db-*") == ["db-master"]
    # Match with '?'
    assert resolve_vms(mock_ctx, name="testuser-?") == ["testuser-1", "testuser-2"]

@patch("cloudmesh.ai.command.vm._shared.context.get_active_provider")
def test_resolve_vms_regex_match(mock_get_provider, mock_ctx, mock_provider):
    mock_get_provider.return_value = mock_provider
    # Complex regex
    assert resolve_vms(mock_ctx, name=".*-prod-.*") == ["web-prod-1", "web-prod-2"]

@patch("cloudmesh.ai.command.vm._shared.context.get_active_provider")
def test_resolve_vms_no_match_raises_exception(mock_get_provider, mock_ctx, mock_provider):
    mock_get_provider.return_value = mock_provider
    with pytest.raises(click.ClickException) as excinfo:
        resolve_vms(mock_ctx, name="nonexistent-*")
    assert "No VMs found matching pattern" in str(excinfo.value)

@patch("cloudmesh.ai.command.vm._shared.context.get_active_provider")
def test_resolve_vms_count(mock_get_provider, mock_ctx, mock_provider):
    mock_get_provider.return_value = mock_provider
    # Should return the last 2 VMs sorted by created_at descending
    # sorted: db-master (5th), web-prod-2 (4th), web-prod-1 (3rd)...
    result = resolve_vms(mock_ctx, count=2)
    assert "db-master" in result
    assert "web-prod-2" in result
    assert len(result) == 2

@patch("cloudmesh.ai.command.vm._shared.context.get_active_provider")
@patch("cloudmesh.ai.command.vm._shared.context.state")
def test_resolve_vms_last_vm(mock_state, mock_get_provider, mock_ctx, mock_provider):
    mock_get_provider.return_value = mock_provider
    mock_state.get_last_vm.return_value = "testuser-1"

    # When no name, count, or range is provided, it should resolve to last VM
    assert resolve_vms(mock_ctx) == ["testuser-1"]
