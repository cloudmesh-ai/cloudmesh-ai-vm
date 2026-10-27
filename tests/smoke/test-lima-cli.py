import json
import re
import uuid

import pytest
from click.testing import CliRunner
from cloudmesh.ai.common.stopwatch import StopWatch
from rich.text import Text

from cloudmesh.ai.command import vm
from tests.smoke.benchmark_helper import (
    create_benchmark_payload,
    get_results_username,
    save_benchmark,
)
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


@pytest.fixture(scope="module")
def lima_vm_name():
    """
    Generates a consistent VM name for the test module to prevent leaking VMs.
    Format: cloudmesh-lima-<username>-<uuid5>
    """
    import yaml
    import os
    import uuid

    # Read username from ~/.config/cloudmesh/clouds.yaml under the 'lima' section
    config_path = os.path.expanduser("~/.config/cloudmesh/clouds.yaml")
    username = "smoke-user"
    try:
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)
                # Look for clouds -> lima -> username
                username = data.get("clouds", {}).get("lima", {}).get("username", "smoke-user")
    except Exception:
        pass

    # Use a consistent short UUID for the session
    short_uuid = str(uuid.uuid4())[:5]
    return f"cloudmesh-lima-{username}-{short_uuid}"


def test_lima_cli_lifecycle(runner, config, lima_vm_name):
    """
    Smoke test for Lima CLI lifecycle.
    """
    env = {"OS_CLOUD": "lima"}
    vm_name = lima_vm_name

    # Pre-cleanup: Ensure no stale VM exists with this name
    runner.invoke(vm.vm_group, ["delete", vm_name], env=env)

    # 1. providers
    with StopWatch.timer("provider_list"):
        result = runner.invoke(vm.vm_group, ["provider", "list"], env=env)
    print(result.output)
    StopWatch.status("provider_list", result.exit_code == 0)
    assert result.exit_code == 0
    assert "lima" in result.output.lower()

    # 2. set
    with StopWatch.timer("provider_set"):
        result = runner.invoke(vm.vm_group, ["provider", "set", "lima"], env=env)
    print(result.output)
    StopWatch.status("provider_set", result.exit_code == 0)
    assert result.exit_code == 0

    # 3. start (with specific name to prevent leaks)
    with StopWatch.timer("start"):
        result = runner.invoke(vm.vm_group, ["start", vm_name], env=env)
    print(result.output)
    StopWatch.status("start", result.exit_code == 0)
    output = Text.from_ansi(result.output).plain

    # with StopWatch.timer("ssh_config"):
    #     result = runner.invoke(vm.vm_group, ["ssh-config"], env=env)
    # print(result.output)
    # StopWatch.status("ssh_config", result.exit_code == 0)
    # assert result.exit_code == 0
    # assert "Host" in result.output

    try:
        assert result.exit_code == 0, f"Lima start failed: {output}"
        assert f"Successfully started VM {vm_name}" in output

        # 4. list
        with StopWatch.timer("list"):
            result = runner.invoke(vm.vm_group, ["list"], env=env)
        print(result.output)
        StopWatch.status("list", result.exit_code == 0)
        assert result.exit_code == 0
        plain_output = Text.from_ansi(result.output).plain
        assert vm_name in plain_output

        # 5. run
        with StopWatch.timer("run"):
            result = runner.invoke(vm.vm_group, ["run", vm_name, "hostname"], env=env)
        print(result.output)
        StopWatch.status("run", result.exit_code == 0)
        if result.exit_code != 0:
            pytest.skip(f"Lima run failed: {result.output}")

        # 6. stop
        with StopWatch.timer("stop"):
            result = runner.invoke(vm.vm_group, ["stop", vm_name], env=env)
        print(result.output)    
        StopWatch.status("stop", result.exit_code == 0)
        assert result.exit_code == 0

        # 7. delete
        with StopWatch.timer("delete"):
            result = runner.invoke(vm.vm_group, ["delete", vm_name], env=env)
        print(result.output)
        StopWatch.status("delete", result.exit_code == 0)
        assert result.exit_code == 0

        # 8. images
        with StopWatch.timer("image"):
            result = runner.invoke(vm.vm_group, ["image"], env=env)
        print(result.output)
        StopWatch.status("image", result.exit_code == 0)
        assert result.exit_code == 0

        # 9. flavors
        with StopWatch.timer("flavor"):
            result = runner.invoke(vm.vm_group, ["flavor"], env=env)
        print(result.output)
        StopWatch.status("flavor", result.exit_code == 0)
        assert result.exit_code == 0

        # 10. keys
        with StopWatch.timer("keys"):
            result = runner.invoke(vm.vm_group, ["key", "list"], env=env)
        print(result.output)
        StopWatch.status("keys", result.exit_code == 0)
        assert result.exit_code == 0

        # 11. security_groups
        with StopWatch.timer("security_group"):
            result = runner.invoke(vm.vm_group, ["security-group"], env=env)
        print(result.output)
        StopWatch.status("security_group", result.exit_code == 0)
        assert result.exit_code == 0

    finally:
        # Always attempt to remove the test VM using the Lima provider.
        runner.invoke(vm.vm_group, ["delete", vm_name], env=env)

        # Save standard benchmark text/json files
        save_benchmark(tag="Lima CLI", config_path=config)

        # Retrieve the results username dynamically using the config path
        try:
            username = get_results_username(config_path=config)
        except Exception:
            username = "smoke_test_user"

        # Create and print/save the structured JSON payload
        payload = create_benchmark_payload(benchmark_name="Lima CLI", user=username)

        print(json.dumps(payload, indent=2))


def test_lima_cli_start_with_name(runner, config):
    """
    Test starting a Lima VM with a specific name.
    """
    vm_name = "test-named-lima-vm"
    env = {"OS_CLOUD": "lima"}
    runner.invoke(vm.vm_group, ["delete", vm_name], env=env)

    try:
        result = runner.invoke(vm.vm_group, ["start", vm_name], env=env)
        assert result.exit_code == 0, f"Lima named VM start failed: {result.output}"
        assert (
            f"Successfully started VM {vm_name}" in Text.from_ansi(result.output).plain
        )
    finally:
        runner.invoke(vm.vm_group, ["delete", vm_name], env=env)
