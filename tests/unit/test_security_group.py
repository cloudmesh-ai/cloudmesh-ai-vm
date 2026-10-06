from unittest.mock import MagicMock, patch
from click.testing import CliRunner
from cloudmesh.ai.command.vm import cmx

def test_security_group_preset_failure_cleans_up_partial_group():
    """
    A failed preset must not leave a partially configured security group.
    """
    runner = CliRunner()
    provider = MagicMock()

    provider.create_security_group.return_value = True
    provider.add_security_group_rule.side_effect = [
        "rule-1",
        RuntimeError("simulated rule creation failure"),
    ]
    provider.delete_security_group.return_value = True

    with patch("cloudmesh.ai.command.vm.security_group.get_active_provider", return_value=provider):
        result = runner.invoke(cmx, ["vm", "security-group", "create", "test-web", "--preset", "web-server"])

    assert result.exit_code != 0
    provider.delete_security_group.assert_called_once_with("test-web")

def test_security_group_preset_failure_reports_cleanup_failure():
    """
    Preserve the preset failure when rollback of the security group also fails.
    """
    runner = CliRunner()
    provider = MagicMock()

    provider.create_security_group.return_value = True
    provider.add_security_group_rule.side_effect = RuntimeError("simulated rule creation failure")
    provider.delete_security_group.side_effect = RuntimeError("simulated cleanup failure")

    with patch("cloudmesh.ai.command.vm.security_group.get_active_provider", return_value=provider):
        result = runner.invoke(cmx, ["vm", "security-group", "create", "test-web", "--preset", "web-server"])

    assert result.exit_code != 0
    assert "Failed to apply preset" in result.output
    assert "simulated rule creation failure" in result.output
    assert "simulated cleanup failure" in result.output
