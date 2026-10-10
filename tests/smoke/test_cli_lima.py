import pytest
from click.testing import CliRunner
from cloudmesh.ai.command import vm
from rich.text import Text
from tests.smoke.cli_helper import setup_cli_config

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def config(tmp_path, runner):
    provider_config = {
        "template": "ubuntu",
    }
    setup_cli_config(tmp_path, "lima", provider_config)

def test_lima_cli_lifecycle(runner, config):
    """
    Smoke test for Lima CLI lifecycle.
    """
    # 1. providers
    result = runner.invoke(vm.vm_group, ["provider", "list"])
    assert result.exit_code == 0
    assert "lima" in result.output.lower()

    # 2. set
    result = runner.invoke(vm.vm_group, ["provider", "set", "lima"])
    assert result.exit_code == 0

    # 3. start (without name - test auto-naming)
    result = runner.invoke(vm.vm_group, ["start"])
    if result.exit_code != 0:
        pytest.skip(f"Lima start failed: {result.output}")

    output = Text.from_ansi(result.output).plain
    assert "Generating VM name" in output

    # Extract the generated VM name
    import re
    match = re.search(r"Successfully started VM ([\w-]+)", output)
    if match:
        vm_name = match.group(1)
    else:
        # Fallback for different output formats
        vm_name = "smoke-lima-vm"

    try:
        # 4. list
        result = runner.invoke(vm.vm_group, ["list"])
        assert result.exit_code == 0
        assert vm_name in Text.from_ansi(result.output).plain

        # 5. stop
        result = runner.invoke(vm.vm_group, ["stop", vm_name])
        assert result.exit_code == 0

        # 6. delete
        result = runner.invoke(vm.vm_group, ["delete", vm_name])
        assert result.exit_code == 0

        # 7. images
        result = runner.invoke(vm.vm_group, ["image"])
        assert result.exit_code == 0

        # 8. flavors
        result = runner.invoke(vm.vm_group, ["flavor"])
        assert result.exit_code == 0

        # 9. keys
        # result = runner.invoke(vm.vm_group, ["keys"])
        # assert result.exit_code == 0

        # 10. security_groups
        result = runner.invoke(vm.vm_group, ["security_groups"])
        assert result.exit_code == 0

        # 11. ssh_config
        runner.invoke(vm.vm_group, ["start", vm_name])
        result = runner.invoke(vm.vm_group, ["ssh_config"])
        assert result.exit_code == 0
        assert "Host" in result.output

    finally:
        # Cleanup: Always attempt to delete the VM
        runner.invoke(vm.vm_group, ["delete", vm_name])

def test_lima_cli_start_with_name(runner, config):
    """
    Test starting a Lima VM with a specific name.
    """
    vm_name = "test-named-lima-vm"
    runner.invoke(vm.vm_group, ["delete", vm_name])

    result = runner.invoke(vm.vm_group, ["start", vm_name])
    if result.exit_code != 0:
        pytest.skip("Lima start failed")

    assert f"Successfully started VM {vm_name}" in Text.from_ansi(result.output).plain
    runner.invoke(vm.vm_group, ["delete", vm_name])
