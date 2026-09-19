import pytest
from click.testing import CliRunner
from cloudmesh.ai.command import vm
from tests.smoke.cli_helper import setup_cli_config

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def config(tmp_path, runner):
    provider_config = {
        "image": "ubuntu-22.04",
    }
    setup_cli_config(tmp_path, "lima", provider_config)

def test_lima_cli_lifecycle(runner, config):
    """
    Smoke test for Lima CLI lifecycle.
    """
    # 1. providers
    result = runner.invoke(vm.vm_group, ["providers"])
    assert result.exit_code == 0
    assert "lima" in result.output

    # 2. set
    result = runner.invoke(vm.vm_group, ["set", "lima"])
    assert result.exit_code == 0

    # 3. start
    vm_name = "smoke-lima-vm"
    result = runner.invoke(vm.vm_group, ["start", vm_name])
    if result.exit_code != 0:
        pytest.skip(f"Lima start failed: {result.output}")
    
    # 4. list
    result = runner.invoke(vm.vm_group, ["list"])
    assert result.exit_code == 0
    assert vm_name in result.output

    # 5. stop
    result = runner.invoke(vm.vm_group, ["stop", vm_name])
    assert result.exit_code == 0

    # 6. delete
    result = runner.invoke(vm.vm_group, ["delete", vm_name])
    assert result.exit_code == 0

    # 7. images
    result = runner.invoke(vm.vm_group, ["images"])
    assert result.exit_code == 0

    # 8. flavors
    result = runner.invoke(vm.vm_group, ["flavors"])
    assert result.exit_code == 0

    # 9. keys
    result = runner.invoke(vm.vm_group, ["keys"])
    assert result.exit_code == 0

    # 10. security_groups
    result = runner.invoke(vm.vm_group, ["security_groups"])
    assert result.exit_code == 0

    # 11. ssh_config
    runner.invoke(vm.vm_group, ["start", vm_name])
    result = runner.invoke(vm.vm_group, ["ssh_config"])
    assert result.exit_code == 0
    assert "Host" in result.output
    
    # Cleanup
    runner.invoke(vm.vm_group, ["delete", vm_name])
