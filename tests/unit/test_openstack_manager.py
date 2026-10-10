from unittest.mock import MagicMock, PropertyMock, patch
import pytest
from cloudmesh.ai.vm.exceptions import VMProviderError
from cloudmesh.ai.vm.openstack.OpenstackManager import OpenstackManager

@pytest.fixture
def mock_driver():
    return MagicMock()

@pytest.fixture
def provider(mock_driver):
    config = {
        "clouds": {
            "test-openstack": {
                "image": "test-image",
                "flavor": "test-flavor",
                "key_path": "~/.ssh/id_rsa",
                "security_group": "ssh-access",
            }
        }
    }
    with patch.object(OpenstackManager, "_get_driver", return_value=mock_driver):
        p = OpenstackManager(config, cloud_name="test-openstack")
        return p

def test_start_uses_configured_key_and_security_group(provider, mock_driver):
    """OpenStack VM creation should attach the configured SSH key and security group."""
    image = MagicMock()
    image.name = "test-image"
    mock_driver.list_images.return_value = [image]

    flavor = MagicMock()
    flavor.name = "test-flavor"
    mock_driver.list_sizes.return_value = [flavor]

    security_group = MagicMock()
    security_group.name = "ssh-access"
    mock_driver.ex_list_security_groups.return_value = [security_group]

    node = MagicMock()
    node.id = "vm-123"
    mock_driver.create_node.return_value = node

    # Mock wait_for_active to return True immediately
    with patch.object(provider, "wait_for_active", return_value=True), \
         patch.object(provider, "assign_floating_ip", return_value="1.2.3.4"), \
         patch.object(provider, "wait_for_login", return_value=True):
        result = provider.start(name="test-vm")

    assert result == "vm-123"
    mock_driver.create_node.assert_called_once_with(
        name="test-vm",
        image=image,
        size=flavor,
        ex_keyname="id_rsa",
        ex_security_groups=[security_group],
    )

def test_start_does_not_create_vm_when_security_group_is_missing(provider, mock_driver):
    """OpenStack VM creation should fail before boot when the security group is missing."""
    # Update config for this specific test case
    provider.config["clouds"]["test-openstack"]["security_group"] = "missing-group"

    image = MagicMock()
    image.name = "test-image"
    mock_driver.list_images.return_value = [image]

    flavor = MagicMock()
    flavor.name = "test-flavor"
    mock_driver.list_sizes.return_value = [flavor]

    mock_driver.ex_list_security_groups.return_value = []

    with pytest.raises(VMProviderError, match="Could not find security group missing-group"):
        provider.start(name="test-vm")

    mock_driver.create_node.assert_not_called()

def test_start_prefers_explicit_key_name(provider, mock_driver):
    """An explicit OpenStack key name should override the name derived from key_path."""
    provider.config["clouds"]["test-openstack"]["key_name"] = "custom-cloud-key"

    image = MagicMock()
    image.name = "test-image"
    mock_driver.list_images.return_value = [image]

    flavor = MagicMock()
    flavor.name = "test-flavor"
    mock_driver.list_sizes.return_value = [flavor]

    security_group = MagicMock()
    security_group.name = "ssh-access"
    mock_driver.ex_list_security_groups.return_value = [security_group]

    node = MagicMock()
    node.id = "vm-123"
    mock_driver.create_node.return_value = node

    with patch.object(provider, "wait_for_active", return_value=True), \
         patch.object(provider, "assign_floating_ip", return_value="1.2.3.4"), \
         patch.object(provider, "wait_for_login", return_value=True):
        provider.start(name="test-vm")

    assert mock_driver.create_node.call_args.kwargs["ex_keyname"] == "custom-cloud-key"

def test_get_provider_info_uses_supported_configuration_fields(provider, mock_driver):
    """Provider info should query only supported, non-sensitive OpenStack fields."""
    # Patch 'version' on the class specifically to avoid property setter issues
    with patch("cloudmesh.ai.vm.openstack.OpenstackManager.OpenstackManager.version", new_callable=PropertyMock) as mock_version:
        mock_version.return_value = ["CLI: test", "libcloud: test"]

        with patch.object(
            provider,
            "_run_cli_command",
            return_value=(
                '{"region_name": "IU", '
                '"auth.auth_url": "https://example.invalid/v3/"}'
            ),
        ) as run_cli:
            info = provider.get_provider_info()

    run_cli.assert_called_once_with([
        "openstack",
        "configuration",
        "show",
        "-f",
        "json",
        "-c",
        "region_name",
        "-c",
        "auth.auth_url",
    ])

    assert info["provider"] == "OpenStack"
    assert info["cloud_name"] == "test-openstack"
    assert info["region"] == "IU"
    assert info["auth_url"] == "https://example.invalid/v3/"
