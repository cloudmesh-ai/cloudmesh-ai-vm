#!/usr/bin/env python3
import sys
from unittest.mock import MagicMock, patch

from cloudmesh.ai.vm.openstack.OpenstackManager import OpenstackManager


def test_get_floating_ip_libcloud_only():
    """
    Verify that _get_floating_ip retrieves the IP from libcloud
    and does NOT rely on the CLI fallback when the driver has the data.
    """
    # Mock config
    config = MagicMock()
    config.clouds = {"jetstream": {"auth": {"auth_url": "http://fake"}}}

    # Initialize manager (mocking _get_driver to avoid real auth)
    with patch.object(OpenstackManager, "_get_driver", return_value=MagicMock()):
        mgr = OpenstackManager(config, cloud_name="jetstream")

        # Case 1: Driver has the public IP
        mock_node = MagicMock()
        mock_node.name = "test-vm"
        mock_node.public_ips = ["1.2.3.4"]

        with patch.object(mgr, "_find_node", return_value=mock_node), \
             patch.object(mgr, "_run_cli_command", side_effect=RuntimeError("CLI should not be called!")):
            fip = mgr._get_floating_ip("test-vm")
            print(f"Result (Driver has IP): {fip}")
            assert fip == "1.2.3.4", "Should have retrieved IP from libcloud driver"

        # Case 2: Driver does NOT have the IP (forces fallback)
        mock_node_no_ip = MagicMock()
        mock_node_no_ip.name = "test-vm"
        mock_node_no_ip.public_ips = []

        with patch.object(mgr, "_find_node", return_value=mock_node_no_ip), \
             patch.object(mgr, "_run_cli_command", side_effect=RuntimeError("CLI failed as expected")):
            fip = mgr._get_floating_ip("test-vm")
            print(f"Result (Driver lacks IP, CLI fails): {fip}")
            assert fip is None, "Should return None when both driver and CLI fail"

    print("\n✅ Verification successful: _get_floating_ip uses libcloud first.")


if __name__ == "__main__":
    try:
        test_get_floating_ip_libcloud_only()
    except Exception as e:
        print(f"\n❌ Verification failed: {e}")
        sys.exit(1)
