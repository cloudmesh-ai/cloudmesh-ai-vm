from unittest.mock import MagicMock, patch
from cloudmesh.ai.vm.openstack.OpenstackManager import OpenstackManager


def make_provider():
    with patch.object(OpenstackManager, "_get_driver", return_value=MagicMock(spec=[
        "list_nodes", "suspend_node", "reboot_node", "ex_list_floating_ips"])):
        p = OpenstackManager({"clouds": {"chameleon": {}}}, cloud_name="chameleon")
    node = MagicMock(id="abc", state="running", public_ips=[], private_ips=["10.0.0.5"])
    node.name = "vm-1"
    p.driver.list_nodes.return_value = [node]
    p.driver.ex_list_floating_ips.return_value = []
    return p, node


def test_info_without_driver_get_node():
    # libcloud's OpenStack_1_1_NodeDriver has no get_node()
    p, node = make_provider()
    info = p.info("vm-1")
    assert info["ID"] == "abc"
    assert info["PrivateIPs"] == ["10.0.0.5"]


def test_suspend_and_restart_without_driver_get_node():
    p, node = make_provider()
    assert p.suspend("vm-1") is True
    p.driver.suspend_node.assert_called_once_with(node)
    assert p.restart("vm-1") is True
    p.driver.reboot_node.assert_called_once_with(node)
