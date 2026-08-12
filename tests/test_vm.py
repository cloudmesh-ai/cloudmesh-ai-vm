import pytest
from click.testing import CliRunner
from cloudmesh.ai.cmc.main import cli

def test_hello():
    runner = CliRunner()
    result = runner.invoke(cli, ["vm", "hello"])
    assert result.exit_code == 0
    assert "Hello from vm!" in result.output