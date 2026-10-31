"""Test that the ``cmx vm start`` command respects the ``--noip`` flag.

The CLI should invoke the provider's ``start`` method with ``assign_ip=False``
when ``--noip`` is passed (or when ``--ip no`` is used).  This test patches the
``get_active_provider`` helper to return a mock provider and verifies the call
arguments.
"""

from unittest.mock import MagicMock, patch
import pytest
from click.testing import CliRunner

from cloudmesh.ai.command.vm import cmx


@pytest.fixture
def runner():
    return CliRunner()


def test_vm_start_noip_flag_passes_assign_ip_false(runner):
    mock_provider = MagicMock()
    mock_provider.cloud_name = "mock-cloud"
    # Simulate a successful start returning the VM name.
    mock_provider.start.return_value = "test-vm"

    with patch(
        "cloudmesh.ai.command.vm.start.get_active_provider",
        return_value=mock_provider,
    ):
        result = runner.invoke(cmx, ["vm", "start", "test-vm", "--noip"])

    # The command should exit cleanly and display the success message.
    assert result.exit_code == 0
    assert "Successfully started VM test-vm" in result.output

    # Verify that ``assign_ip`` was explicitly set to ``False``.
    mock_provider.start.assert_called_once_with(
        name="test-vm", assign_ip=False, duration=None
    )