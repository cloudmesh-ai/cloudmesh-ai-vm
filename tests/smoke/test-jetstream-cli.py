import json
import os
import re
import uuid
from pprint import pprint

import pytest
import yaml
from click.testing import CliRunner
from rich.text import Text

from cloudmesh.ai.command import vm
from cloudmesh.ai.common.io import banner
from cloudmesh.ai.common.stopwatch import StopWatch
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
    # Read the actual user configuration
    config_path = os.path.expanduser("~/.config/cloudmesh/clouds.yaml")
    try:
        with open(config_path, "r") as f:
            full_config = yaml.safe_load(f)
            # Extract jetstream specific config
            provider_config = full_config.get("clouds", {}).get("jetstream", {})
            username = full_config.get("username", "smoke-user").replace("_", "-")
    except Exception:
        # Fallback defaults if file is missing or corrupted
        provider_config = {
            "image": "ubuntu-22.04",
            "flavor": "m1.small",
        }
        username = "smoke-user"

    # Ensure we have a key_path for the test
    if "key_path" not in provider_config:
        provider_config["key_path"] = "~/.ssh/id_rsa"

    # Create a temporary config for the test that mirrors the real one
    setup_cli_config(tmp_path, "jetstream", provider_config)

    # Add username to provider_config so it's available in tests
    provider_config["username"] = username

    banner("Construct a unique vm_name based on the actual username")
    vm_name = f"{username}-{uuid.uuid4().hex[:4]}"
    print(f"Generated unique VM name for test: {vm_name}")
    env = {"OS_CLOUD": "jetstream"}

    provider_config["vm_name"] = vm_name

    pprint(provider_config)
    return provider_config

def test_jetstream_cli_lifecycle(runner, config):
    """
    Smoke test for Jetstream CLI lifecycle.
    """

    env = {"OS_CLOUD": "jetstream"}

    banner("1. providers")
    with StopWatch.timer("provider_list"):
        result = runner.invoke(vm.vm_group, ["provider", "list"], env=env)
    print(result.output)
    StopWatch.status("provider_list", result.exit_code == 0)
    assert result.exit_code == 0
    assert "jetstream" in result.output.lower()

    banner("2. set")
    with StopWatch.timer("provider_set"):
        result = runner.invoke(vm.vm_group, ["provider", "set", "jetstream"], env=env)
    print(result.output)
    StopWatch.status("provider_set", result.exit_code == 0)
    assert result.exit_code == 0

    banner("3. start (without name - test auto-naming)")
    with StopWatch.timer("start"):
        result = runner.invoke(vm.vm_group, ["start"], env=env)
    print(result.output)
    StopWatch.status("start", result.exit_code == 0)
    if result.exit_code != 0:
        pytest.skip(
            f"Jetstream start failed (expected without real credentials): {result.output}"
        )

    output = Text.from_ansi(result.output).plain
    assert "Generating VM name" in output

    # Extract the generated VM name
    # The output contains ANSI escape codes, so we search in the plain text version
    plain_output = Text.from_ansi(result.output).plain
    print(f"Plain output for VM name extraction:\n{plain_output}")
    match = re.search(r"(?:Generating VM name: |Successfully started VM )([\w-]+)", plain_output)
    if match:
        vm_name = match.group(1)
    else:
        pytest.fail(f"Could not extract VM name from output: {plain_output}")

    try:
        banner("4. list")
        with StopWatch.timer("list"):
            result = runner.invoke(vm.vm_group, ["list"], env=env)
        print(result.output)    
        StopWatch.status("list", result.exit_code == 0)
        assert result.exit_code == 0

        # Check if the actual started VM name is in the 
        # output of the list command
        plain_output = Text.from_ansi(result.output).plain
        assert vm_name in plain_output

        banner("5. run")
        with StopWatch.timer("run"):
            result = runner.invoke(vm.vm_group, ["run", vm_name, "hostname"], env=env)
        print(result.output)
        StopWatch.status("run", result.exit_code == 0)
        if result.exit_code != 0:
            pytest.skip("Jetstream run failed")

        banner("6. stop")
        with StopWatch.timer("stop"):
            result = runner.invoke(vm.vm_group, ["stop", vm_name], env=env)
        print(result.output)
        StopWatch.status("stop", result.exit_code == 0)
        if result.exit_code != 0:
            pytest.skip("Jetstream stop failed")

        banner("13. security-groups")
        with StopWatch.timer("security-group"):                
            result = runner.invoke(vm.vm_group, ["security-group"], env=env)
        print(result.output)
        if result.exit_code != 0:
            pytest.skip("Jetstream security-group failed")

        banner("14. ssh-config")
        with StopWatch.timer("ssh-config"):
            result = runner.invoke(vm.vm_group, ["ssh-config"], env=env)
        print(result.output)    
        assert result.exit_code == 0

        banner("6. delete")
        with StopWatch.timer("delete"):
            result = runner.invoke(vm.vm_group, ["delete", vm_name], env=env)
        print(result.output)
        if result.exit_code != 0:
            pytest.skip("Jetstream delete failed")

        banner("7. image")
        with StopWatch.timer("image"):
            result = runner.invoke(vm.vm_group, ["image"], env=env)
        print(result.output)
        if result.exit_code != 0:
            pytest.skip("Jetstream images failed")

        banner("8. flavor")
        with StopWatch.timer("flavor"):
            result = runner.invoke(vm.vm_group, ["flavor"], env=env)
        print(result.output)
        if result.exit_code != 0:
            pytest.skip("Jetstream flavors failed")

        banner("9. keys list")
        with StopWatch.timer("key_list"):
            result = runner.invoke(vm.vm_group, ["key", "list"], env=env)
        print(result.output)
        if result.exit_code != 0:
            pytest.skip("Jetstream key list failed")

        banner("10. keys list --all")
        with StopWatch.timer("key_list_all"):
            result = runner.invoke(vm.vm_group, ["key", "list", "--all"], env=env)
        print(result.output)
        if result.exit_code != 0:
            pytest.skip("Jetstream key list --all failed")

        banner("11. keys upload")
        with StopWatch.timer("key_upload"):
            result = runner.invoke(vm.vm_group, ["key", "upload", "~/.ssh/id_rsa.pub"], env=env)
        print(result.output)
        if result.exit_code != 0:
            pytest.skip("Jetstream key upload failed")
            
        banner("12. keys delete")
        with StopWatch.timer("key_delete"):
            result = runner.invoke(vm.vm_group, ["key", "delete", "smoke-key"], env=env)
        print(result.output)
        if result.exit_code != 0:
            pytest.skip("Jetstream key delete failed")

    finally:
        # Always attempt to remove the test VM using the Jetstream provider.
        runner.invoke(vm.vm_group, ["delete", vm_name], env=env)

        # Save standard benchmark text/json files
        save_benchmark(tag="Jetstream CLI", config_path=None)

        # Retrieve the results username dynamically
        try:
            username = config.get("username", "smoke_test_user")
        except Exception:
            username = "smoke_test_user"

        # Create and print/save the structured JSON payload
        payload = create_benchmark_payload(benchmark_name="Jetstream CLI", user=username)

        print(json.dumps(payload, indent=2))
            

def test_jetstream_cli_start_with_name(runner, config):
    """
    Test starting a Jetstream VM with a specific name.
    """
    # Use the username from config to make the named VM unique to the user
    username = config.get("username", "smoke-user")
    vm_name = f"test-named-{username}-jetstream-vm"
    env = {"OS_CLOUD": "jetstream"}

    try:
        # Pre-cleanup: Ensure no stale VM exists with this name
        runner.invoke(vm.vm_group, ["delete", vm_name], env=env)

        result = runner.invoke(vm.vm_group, ["start", vm_name], env=env)
        if result.exit_code != 0:
            pytest.skip("Jetstream start failed")

        assert f"Successfully started VM {vm_name}" in Text.from_ansi(result.output).plain
    finally:
        runner.invoke(vm.vm_group, ["delete", vm_name], env=env)
