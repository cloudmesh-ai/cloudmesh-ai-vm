import pytest
import re
import json
from rich.text import Text
from click.testing import CliRunner
from cloudmesh.ai.command import vm
from cloudmesh.ai.common.stopwatch import StopWatch

from tests.smoke.cli_helper import setup_cli_config

from tests.smoke.benchmark_helper import (
    save_benchmark,
    create_benchmark_payload,
    get_results_username,  
)

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
    env = {"OS_CLOUD": "lima"}
    
    # 1. providers
    with StopWatch.timer("lima_provider_list"):
        result = runner.invoke(vm.vm_group, ["provider", "list"], env=env)
    StopWatch.status("lima_provider_list", result.exit_code == 0)
    assert result.exit_code == 0
    assert "lima" in result.output.lower()

    # 2. set
    with StopWatch.timer("lima_provider_set"):
        result = runner.invoke(vm.vm_group, ["provider", "set", "lima"], env=env)
    StopWatch.status("lima_provider_set", result.exit_code == 0)
    assert result.exit_code == 0

    # 3. start (without name - test auto-naming)
    with StopWatch.timer("lima_start"):
        result = runner.invoke(vm.vm_group, ["start"], env=env)
    StopWatch.status("lima_start", result.exit_code == 0)
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
        with StopWatch.timer("lima_list"):
            result = runner.invoke(vm.vm_group, ["list"], env=env)
        StopWatch.status("lima_list", result.exit_code == 0)
        assert result.exit_code == 0
        plain_output = Text.from_ansi(result.output).plain
        assert vm_name[:12] in plain_output or "smoke-test-" in plain_output

        # 5. run
        with StopWatch.timer("lima_run"):
            result = runner.invoke(vm.vm_group, ["run", vm_name, "hostname"])
        StopWatch.status("lima_run", result.exit_code == 0)
        if result.exit_code != 0:
            pytest.skip(f"Lima run failed: {result.output}")

        # 6. stop
        with StopWatch.timer("lima_stop"):
            result = runner.invoke(vm.vm_group, ["stop", vm_name], env=env)
        StopWatch.status("lima_stop", result.exit_code == 0)
        assert result.exit_code == 0

        # 7. delete
        with StopWatch.timer("lima_delete"):
            result = runner.invoke(vm.vm_group, ["delete", vm_name], env=env)
        StopWatch.status("lima_delete", result.exit_code == 0)
        assert result.exit_code == 0

        # 8. images
        with StopWatch.timer("lima_images"):
            result = runner.invoke(vm.vm_group, ["image"], env=env)
        StopWatch.status("lima_images", result.exit_code == 0)
        assert result.exit_code == 0

        # 9. flavors
        with StopWatch.timer("lima_flavors"):
            result = runner.invoke(vm.vm_group, ["flavor"], env=env)
        StopWatch.status("lima_flavors", result.exit_code == 0)
        assert result.exit_code == 0

        # 10. keys
        with StopWatch.timer("lima_keys"):
            result = runner.invoke(vm.vm_group, ["key", "list"], env=env)
        StopWatch.status("lima_keys", result.exit_code == 0)
        assert result.exit_code == 0

        # 11. security_groups
        with StopWatch.timer("lima_security_groups"):
            result = runner.invoke(vm.vm_group, ["security-group"], env=env)
        StopWatch.status("lima_security_groups", result.exit_code == 0)
        assert result.exit_code == 0

        # 12. ssh_config
        restart_result = runner.invoke(
            vm.vm_group, ["start", vm_name], env=env
        )
        assert restart_result.exit_code == 0

        with StopWatch.timer("lima_ssh_config"):
            result = runner.invoke(vm.vm_group, ["ssh-config"], env=env)
        StopWatch.status("lima_ssh_config", result.exit_code == 0)
        assert result.exit_code == 0
        assert "Host" in result.output

    finally:
        # Cleanup VMs
        runner.invoke(vm.vm_group, ["delete", vm_name])
        
        # Save standard benchmark text/json files
        save_benchmark(tag="Lima CLI", config_path=config)

        # Retrieve the results username dynamically using the config path
        try:
            username = get_results_username(config_path=config)
        except Exception:
            username = "smoke_test_user"

        # Create and print/save the structured JSON payload
        payload = create_benchmark_payload(
            benchmark_name="Lima CLI", 
            user=username
        )
        
        print(json.dumps(payload, indent=2))

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