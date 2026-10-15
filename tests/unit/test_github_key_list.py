from unittest.mock import patch

from click.testing import CliRunner

from cloudmesh.ai.command.vm.key.github import github


def test_github_key_list_uses_api_fields():
    """Display GitHub SSH keys using actual API response fields."""
    keys = [{
        "id": 12345,
        "title": "Test SSH Key",
        "key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest",
        "verified": True,
    }]

    with patch("cloudmesh.ai.command.vm.key.github.KeyManager") as manager:
        manager.return_value.github_list.return_value = keys
        result = CliRunner().invoke(github, ["list"])

    assert result.exit_code == 0, result.output
    assert "Test SSH Key" in result.output
    assert "ssh-ed25519" in result.output
    assert "12345" in result.output


def test_github_key_list_empty():
    """Handle GitHub accounts without registered SSH keys."""
    with patch("cloudmesh.ai.command.vm.key.github.KeyManager") as manager:
        manager.return_value.github_list.return_value = []
        result = CliRunner().invoke(github, ["list"])

    assert result.exit_code == 0, result.output
    assert "No SSH keys found on GitHub." in result.output
