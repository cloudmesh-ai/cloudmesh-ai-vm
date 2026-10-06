from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from cloudmesh.ai.vm.exceptions import VMProviderError
from cloudmesh.ai.vm.openstack.OpenstackManager import OpenstackManager


def test_start_uses_configured_key_and_security_group():
    """OpenStack VM creation should attach the configured SSH key and security group."""
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

    driver = MagicMock()

    image = MagicMock()
    image.name = "test-image"
    driver.list_images.return_value = [image]

    flavor = MagicMock()
    flavor.name = "test-flavor"
    driver.list_sizes.return_value = [flavor]

    security_group = MagicMock()
    security_group.name = "ssh-access"
    driver.ex_list_security_groups.return_value = [security_group]

    node = MagicMock()
    node.id = "vm-123"
    driver.create_node.return_value = node

    with patch.object(OpenstackManager, "_get_driver", return_value=driver):
        provider = OpenstackManager(config, cloud_name="test-openstack")
        result = provider.start(name="test-vm")

    assert result == "vm-123"
    driver.create_node.assert_called_once_with(
        name="test-vm",
        image=image,
        size=flavor,
        ex_keyname="id_rsa",
        ex_security_groups=[security_group],
    )


def test_start_does_not_create_vm_when_security_group_is_missing():
    """OpenStack VM creation should fail before boot when the security group is missing."""
    config = {
        "clouds": {
            "test-openstack": {
                "image": "test-image",
                "flavor": "test-flavor",
                "key_name": "test-key",
                "security_group": "ssh-access",
            }
        }
    }

    driver = MagicMock()

    image = MagicMock()
    image.name = "test-image"
    driver.list_images.return_value = [image]

    flavor = MagicMock()
    flavor.name = "test-flavor"
    driver.list_sizes.return_value = [flavor]

    driver.ex_list_security_groups.return_value = []

    with patch.object(OpenstackManager, "_get_driver", return_value=driver):
        provider = OpenstackManager(config, cloud_name="test-openstack")

        with pytest.raises(VMProviderError, match="Could not find security group ssh-access"):
            provider.start(name="test-vm")

    driver.create_node.assert_not_called()



def test_start_prefers_explicit_key_name():
    """An explicit OpenStack key name should override the name derived from key_path."""
    config = {
        "clouds": {
            "test-openstack": {
                "image": "test-image",
                "flavor": "test-flavor",
                "key_path": "~/.ssh/id_rsa",
                "key_name": "custom-cloud-key",
                "security_group": "ssh-access",
            }
        }
    }

    driver = MagicMock()

    image = MagicMock()
    image.name = "test-image"
    driver.list_images.return_value = [image]

    flavor = MagicMock()
    flavor.name = "test-flavor"
    driver.list_sizes.return_value = [flavor]

    security_group = MagicMock()
    security_group.name = "ssh-access"
    driver.ex_list_security_groups.return_value = [security_group]

    node = MagicMock()
    node.id = "vm-123"
    driver.create_node.return_value = node

    with patch.object(OpenstackManager, "_get_driver", return_value=driver):
        provider = OpenstackManager(config, cloud_name="test-openstack")
        provider.start(name="test-vm")

    assert driver.create_node.call_args.kwargs["ex_keyname"] == "custom-cloud-key"

def test_get_provider_info_uses_supported_configuration_fields():
    """Provider info should query only supported, non-sensitive OpenStack fields."""
    config = {"clouds": {"jetstream": {}}}
    driver = MagicMock()

    with patch.object(OpenstackManager, "_get_driver", return_value=driver):
        provider = OpenstackManager(config, cloud_name="jetstream")

        with patch.object(
            OpenstackManager,
            "version",
            new_callable=PropertyMock,
            return_value=["CLI: test", "libcloud: test"],
        ):
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
    assert info["cloud_name"] == "jetstream"
    assert info["region"] == "IU"
    assert info["auth_url"] == "https://example.invalid/v3/"    
