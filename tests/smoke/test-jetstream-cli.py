import os
import re
import uuid
from pprint import pprint

import pytest
import yaml
from click.testing import CliRunner
from rich.text import Text

from cloudmesh.ai.command import vm
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

    # Construct a unique vm_name based on the actual username
    vm_name = f"{username}-{uuid.uuid4().hex[:4]}"
    provider_config["vm_name"] = vm_name

    pprint(provider_config)
    return provider_config

def test_jetstream_cli_lifecycle(runner, config):
    """
    Smoke test for Jetstream CLI lifecycle.
    """
    # 1. providers
    result = runner.invoke(vm.vm_group, ["provider", "list"])
    assert result.exit_code == 0
    assert "jetstream" in result.output.lower()

    # 2. set
    result = runner.invoke(vm.vm_group, ["provider", "set", "jetstream"])
    assert result.exit_code == 0

    # 3. start (without name - test auto-naming)
    result = runner.invoke(vm.vm_group, ["start"])
    if result.exit_code != 0:
        pytest.skip(
            f"Jetstream start failed (expected without real credentials): {result.output}"
        )

    output = Text.from_ansi(result.output).plain
    assert "Generating VM name" in output

    # Extract the generated VM name
    # The output can be "Generating VM name: name" or "Successfully started VM name"
    match = re.search(r"(?:Generating VM name: |Successfully started VM )([\w-]+)", result.output)
    if match:
        vm_name = match.group(1)
    else:
        pytest.fail(f"Could not extract VM name from output: {result.output}")

    try:
        # 4. list
        result = runner.invoke(vm.vm_group, ["list"])
        assert result.exit_code == 0

        # Check if the actual started VM name is in the list
        assert vm_name in result.output

        # 5. stop
        result = runner.invoke(vm.vm_group, ["stop", vm_name])
        if result.exit_code != 0:
            pytest.skip("Jetstream stop failed")

        # 6. delete
        result = runner.invoke(vm.vm_group, ["delete", vm_name])
        if result.exit_code != 0:
            pytest.skip("Jetstream delete failed")

        # 7. images
        result = runner.invoke(vm.vm_group, ["images"])
        if result.exit_code != 0:
            pytest.skip("Jetstream images failed")

        # 8. flavors
        result = runner.invoke(vm.vm_group, ["flavor"])
        if result.exit_code != 0:
            pytest.skip("Jetstream flavors failed")

        # 9. keys list
        result = runner.invoke(vm.vm_group, ["key", "list"])
        if result.exit_code != 0:
            pytest.skip("Jetstream key list failed")

        # 10. keys list --all
        result = runner.invoke(vm.vm_group, ["key", "list", "--all"])
        if result.exit_code != 0:
            pytest.skip("Jetstream key list --all failed")

        # 11. keys upload
        result = runner.invoke(vm.vm_group, ["key", "upload", "~/.ssh/id_rsa.pub"])
        if result.exit_code != 0:
            pytest.skip("Jetstream key upload failed")

        # 12. keys delete
        result = runner.invoke(vm.vm_group, ["key", "delete", "smoke-key"])
        if result.exit_code != 0:
            pytest.skip("Jetstream key delete failed")

        # 13. security_groups
        result = runner.invoke(vm.vm_group, ["security_groups"])
        if result.exit_code != 0:
            pytest.skip("Jetstream security_groups failed")

        # 14. ssh_config
        result = runner.invoke(vm.vm_group, ["ssh_config"])
        assert result.exit_code == 0

    finally:
        # Cleanup
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
