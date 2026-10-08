from unittest.mock import MagicMock, patch
from cloudmesh.ai.vm.openstack.OpenstackManager import OpenstackManager


def make_provider(public_ips):
    with patch.object(OpenstackManager, "_get_driver", return_value=MagicMock(spec=["list_nodes"])):
        p = OpenstackManager({"clouds": {"chameleon": {}}}, cloud_name="chameleon")
    node = MagicMock(id="abc", public_ips=public_ips, private_ips=["10.56.0.23"])
    node.name = "vm-1"
    p.driver.list_nodes.return_value = [node]
    # Current openstack CLI output format; the old parser does not understand it
    p._run_cli_command = MagicMock(return_value="{'sharednet1': ['10.56.0.23', '129.114.27.8']}")
    return p


def test_floating_ip_from_libcloud_node():
    assert make_provider(["129.114.27.8"])._get_floating_ip("vm-1") == "129.114.27.8"


def test_no_floating_ip():
    assert make_provider([])._get_floating_ip("vm-1") is None
