import pytest
from click.testing import CliRunner
from cloudmesh.ai.command import vm
from rich.text import Text
from tests.smoke.cli_helper import setup_cli_config
from tests.smoke.benchmark_helper import save_benchmark
from cloudmesh.ai.common.stopwatch import StopWatch

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
    StopWatch.clear()
    env = {"OS_CLOUD": "lima"}
    # 1. providers
    result = runner.invoke(vm.vm_group, ["provider", "list"], env=env)
    assert result.exit_code == 0
    assert "lima" in result.output.lower()

    # 2. set
    result = runner.invoke(vm.vm_group, ["provider", "set", "lima"], env=env)
    assert result.exit_code == 0

    # 3. start (without name - test auto-naming)
    with StopWatch.timer("lima_cli_start"):
        result = runner.invoke(vm.vm_group, ["start"], env=env)
    output = Text.from_ansi(result.output).plain

    # Capture the generated name even if startup fails.
    import re
    match = re.search(r"Generating VM name:\s*([\w-]+)", output)
    assert match, f"Could not determine generated VM name: {output}"
    vm_name = match.group(1)

    try:
        if result.exit_code != 0:
            pytest.fail(f"Lima start failed: {result.output}")

        assert f"Successfully started VM {vm_name}" in output
        # 4. list
        with StopWatch.timer("lima_cli_list"):
            result = runner.invoke(vm.vm_group, ["list"], env=env)
        assert result.exit_code == 0
        assert vm_name in Text.from_ansi(result.output).plain

        # 5. stop
        with StopWatch.timer("lima_cli_stop"):
            result = runner.invoke(vm.vm_group, ["stop", vm_name], env=env)
        assert result.exit_code == 0

        # 6. delete
        with StopWatch.timer("lima_cli_delete"):
            result = runner.invoke(vm.vm_group, ["delete", vm_name], env=env)
        assert result.exit_code == 0

        # 7. images
        result = runner.invoke(vm.vm_group, ["image"], env=env)
        assert result.exit_code == 0

        # 8. flavors
        result = runner.invoke(vm.vm_group, ["flavor"], env=env)
        assert result.exit_code == 0

        # 9. keys
        result = runner.invoke(vm.vm_group, ["key", "list"], env=env)
        assert result.exit_code == 0

        # 10. security_groups
        result = runner.invoke(vm.vm_group, ["security-group"], env=env)
        assert result.exit_code == 0

        # 11. ssh_config
        with StopWatch.timer("lima_cli_restart"):
            result = runner.invoke(vm.vm_group, ["start", vm_name], env=env)
        assert result.exit_code == 0, f"Lima restart failed: {result.output}"
        with StopWatch.timer("lima_cli_ssh_config"):
            result = runner.invoke(vm.vm_group, ["ssh-config"], env=env)
        assert result.exit_code == 0
        assert "Host" in result.output

    finally:
        # Cleanup: Always attempt to delete the VM
        runner.invoke(vm.vm_group, ["delete", vm_name], env=env)
        save_benchmark(tag="Lima CLI", config_path=None)

def test_lima_cli_start_with_name(runner, config):
    """
    Test starting a Lima VM with a specific name.
    """
    vm_name = "test-named-lima-vm"
    env = {"OS_CLOUD": "lima"}
    runner.invoke(vm.vm_group, ["delete", vm_name], env=env)

    try:
        result = runner.invoke(vm.vm_group, ["start", vm_name], env=env)
        if result.exit_code != 0:
            pytest.fail(f"Lima named VM start failed: {result.output}")

        assert f"Successfully started VM {vm_name}" in Text.from_ansi(result.output).plain
    finally:
        runner.invoke(vm.vm_group, ["delete", vm_name], env=env)
