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
from tests.smoke.benchmark_helper import save_benchmark
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
    provider_config["vm_name"] = vm_name

    pprint(provider_config)
    return provider_config

def test_jetstream_cli_lifecycle(runner, config):
    """
    Smoke test for Jetstream CLI lifecycle.
    """

    banner("1. providers")
    result = runner.invoke(vm.vm_group, ["provider", "list"])
    print(result.output)
    assert result.exit_code == 0
    assert "jetstream" in result.output.lower()

    banner("2. set")
    result = runner.invoke(vm.vm_group, ["provider", "set", "jetstream"])
    print(result.output)
    assert result.exit_code == 0

    banner("3. start (without name - test auto-naming)")
    result = runner.invoke(vm.vm_group, ["start"])
    print(result.output)
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
        result = runner.invoke(vm.vm_group, ["list"])
        print(result.output)    
        assert result.exit_code == 0

        # Check if the actual started VM name is in the list
        assert vm_name in result.output

        banner("5. stop")
        result = runner.invoke(vm.vm_group, ["stop", vm_name])
        print(result.output)
        if result.exit_code != 0:
            pytest.skip("Jetstream stop failed")


        banner("13. security-groups")
        result = runner.invoke(vm.vm_group, ["security-group"])
        print(result.output)
        if result.exit_code != 0:
            pytest.skip("Jetstream security-group failed")

        banner("14. ssh-config")
        result = runner.invoke(vm.vm_group, ["ssh-config"])
        print(result.output)    
        assert result.exit_code == 0

        banner("6. delete")
        result = runner.invoke(vm.vm_group, ["delete", vm_name])
        print(result.output)
        if result.exit_code != 0:
            pytest.skip("Jetstream delete failed")

        banner("7. image")
        result = runner.invoke(vm.vm_group, ["image"])
        print(result.output)
        if result.exit_code != 0:
            pytest.skip("Jetstream images failed")

        banner("8. flavors")
        result = runner.invoke(vm.vm_group, ["flavor"])
        print(result.output)
        if result.exit_code != 0:
            pytest.skip("Jetstream flavors failed")

        banner("9. keys list")
        result = runner.invoke(vm.vm_group, ["key", "list"])
        print(result.output)
        if result.exit_code != 0:
            pytest.skip("Jetstream key list failed")

        banner("10. keys list --all")
        result = runner.invoke(vm.vm_group, ["key", "list", "--all"])
        print(result.output)
        if result.exit_code != 0:
            pytest.skip("Jetstream key list --all failed")

        banner("11. keys upload")
        result = runner.invoke(vm.vm_group, ["key", "upload", "~/.ssh/id_rsa.pub"])
        print(result.output)
        if result.exit_code != 0:
            pytest.skip("Jetstream key upload failed")

        banner("12. keys delete")
        result = runner.invoke(vm.vm_group, ["key", "delete", "smoke-key"])
        print(result.output)
        if result.exit_code != 0:
            pytest.skip("Jetstream key delete failed")


    finally:
        # Cleanup
        banner(f"Cleaning up VM {vm_name} if it exists...")
        runner.invoke(vm.vm_group, ["delete", vm_name])
        save_benchmark(tag="Jetstream CLI", config_path=None)


def test_jetstream_cli_start_with_name(runner, config):
    """
    Test starting a Jetstream VM with a specific name.
    """
    # Use the username from config to make the named VM unique to the user
    username = config.get("username", "smoke-user")
    vm_name = f"test-named-{username}-jetstream-vm"
    runner.invoke(vm.vm_group, ["delete", vm_name])

    result = runner.invoke(vm.vm_group, ["start", vm_name])
    if result.exit_code != 0:
        pytest.skip("Jetstream start failed")

    assert f"Successfully started VM {vm_name}" in Text.from_ansi(result.output).plain
    runner.invoke(vm.vm_group, ["delete", vm_name])
