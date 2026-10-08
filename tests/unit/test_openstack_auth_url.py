import pytest
from unittest.mock import MagicMock, patch
from cloudmesh.ai.vm.openstack.OpenstackManager import OpenstackManager


@pytest.mark.parametrize("auth_url", [
    "https://kvm.tacc.chameleoncloud.org:5000/v3",
    "https://kvm.tacc.chameleoncloud.org:5000/v3/",
    "https://kvm.tacc.chameleoncloud.org:5000",
])
def test_auth_url_without_v3_suffix(auth_url, tmp_path, monkeypatch):
    # Point HOME at an empty dir so the real ~/.config/openstack/clouds.yaml is not read
    monkeypatch.setenv("HOME", str(tmp_path))
    config = {"clouds": {"chameleon": {
        "auth": {
            "auth_url": auth_url,
            "application_credential_id": "id",
            "application_credential_secret": "secret",
        },
        "region_name": "KVM@TACC",
    }}}
    driver_cls = MagicMock()
    with patch("libcloud.compute.providers.get_driver", return_value=driver_cls):
        OpenstackManager(config, cloud_name="chameleon")

    assert driver_cls.call_args.kwargs["ex_force_auth_url"] == "https://kvm.tacc.chameleoncloud.org:5000"
