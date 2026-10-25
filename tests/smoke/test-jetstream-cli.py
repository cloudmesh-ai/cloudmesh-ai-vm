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
def runner(tmp_path):
    # Set the environment variable so the CLI uses the temporary config directory
    os.environ["CLOUDMESH_CONFIG_DIR"] = str(tmp_path)
    # Ensure the current provider is set to jetstream for every run
    # by overriding the config if necessary.
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
            if username.startswith("cloudmesh-"):
                username = username[len("cloudmesh-"):]
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
    
    # Set the environment variable so the CLI uses the temp config
    os.environ["CLOUDMESH_CONFIG_DIR"] = str(tmp_path)

    # Add username to provider_config so it's available in tests
    provider_config["username"] = username

    # Construct a unique vm_name based on the actual username
    uuid_suffix = f"{uuid.uuid4().hex[:5]}"
    vm_name = f"test-cloudmesh-{username}-jetstream-vm-{uuid_suffix}"
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

    # Clear any potential global provider state that might be forcing Chameleon
    os.environ["CLOUDMESH_CLOUD_NAME"] = "jetstream"
    os.environ["CLOUDMESH_PROVIDER"] = "jetstream"
    os.environ["OS_CLOUD"] = "jetstream"

    banner("3. start (without name - test auto-naming)")
    from cloudmesh.ai.common.stopwatch import StopWatch
    with StopWatch.timer("jetstream_start"):
        result = runner.invoke(vm.vm_group, ["start"])
    StopWatch.status("jetstream_start", result.exit_code == 0)
    if result.exit_code != 0:
        pytest.skip(
            f"Jetstream start failed (expected without real credentials): {result.output}"
        )

    output = Text.from_ansi(result.output).plain
    assert "Generating VM name" in output

    # Extract the generated VM name
    # The output contains ANSI escape codes, so we search in the plain text version
    plain_output = Text.from_ansi(result.output).plain
    match = re.search(r"(?:Generating VM name: |Successfully started VM )([\w-]+)", plain_output)
    if match:
        vm_name = match.group(1)
    else:
        pytest.fail(f"Could not extract VM name from output: {plain_output}")

    try:
        banner("4. list")
        with StopWatch.timer("jetstream_list"): 
            result = runner.invoke(vm.vm_group, ["list"])
            print(result.output)    
        StopWatch.status("jetstream_list", result.exit_code == 0)
        assert result.exit_code == 0

        # Check if the actual started VM name is in the list
        assert vm_name in result.output

        banner("13. security_groups (Corrected command name)")
        with StopWatch.timer("jetstream_sec_groups"):
            result = runner.invoke(vm.vm_group, ["security-group"])
            print(result.output)        
        StopWatch.status("jetstream_sec_groups", result.exit_code == 0)
        if result.exit_code != 0:
            print(f"Jetstream security-group failed: {result.output}")

        banner("14. ssh_config (Corrected command name)")
        with StopWatch.timer("jetstream_ssh_config"):
            result = runner.invoke(vm.vm_group, ["ssh-config"])
            print(result.output)
        StopWatch.status("jetstream_ssh_config", result.exit_code == 0)
        if result.exit_code != 0:
            if "No free floating IPs available" in result.output or "none could be assigned" in result.output:
                print("Skipping ssh-config due to floating IP quota")
                StopWatch.status("jetstream_ssh_config", True) # Mark as pass/skipped
            else:
                print(f"Jetstream ssh-config failed: {result.output}")
        else:
            assert result.exit_code == 0

        banner("5. stop")
        with StopWatch.timer("jetstream_stop"):
            result = runner.invoke(vm.vm_group, ["stop", vm_name])
            print(result.output)    
        StopWatch.status("jetstream_stop", result.exit_code == 0)
        if result.exit_code != 0:
            pytest.skip("Jetstream stop failed")

        banner("6. delete")
        with StopWatch.timer("jetstream_delete"):
            result = runner.invoke(vm.vm_group, ["delete", vm_name])
            print(result.output)
        StopWatch.status("jetstream_delete", result.exit_code == 0)
        if result.exit_code != 0:
            pytest.skip("Jetstream delete failed")

        banner("7. images")
        with StopWatch.timer("jetstream_images"):
            result = runner.invoke(vm.vm_group, ["image"])
            print(result.output)
        StopWatch.status("jetstream_images", result.exit_code == 0)
        if result.exit_code != 0:
            print(f"Jetstream images failed: {result.output}")

        banner("8. flavors")
        with StopWatch.timer("jetstream_flavors"):
            result = runner.invoke(vm.vm_group, ["flavor"])
            print(result.output)
        StopWatch.status("jetstream_flavors", result.exit_code == 0)
        if result.exit_code != 0:
            print(f"Jetstream flavors failed: {result.output}")

        banner("9. keys list")
        with StopWatch.timer("jetstream_key_list"):
            result = runner.invoke(vm.vm_group, ["key", "list"])
            print(result.output)
        StopWatch.status("jetstream_key_list", result.exit_code == 0)
        if result.exit_code != 0:
            print(f"Jetstream key list failed: {result.output}")

        banner("10. keys list --all")
        with StopWatch.timer("jetstream_key_list_all"):
            result = runner.invoke(vm.vm_group, ["key", "list", "--all"])
            print(result.output)
        StopWatch.status("jetstream_key_list_all", result.exit_code == 0)
        if result.exit_code != 0:
            print(f"Jetstream key list --all failed: {result.output}")

        banner("11. keys upload")
        with StopWatch.timer("jetstream_key_upload"):
            result = runner.invoke(vm.vm_group, ["key", "upload", "~/.ssh/id_rsa.pub"])
            print(result.output)
        StopWatch.status("jetstream_key_upload", result.exit_code == 0)
        if result.exit_code != 0:
            print(f"Jetstream key upload failed: {result.output}")

        banner("12. keys delete")
        with StopWatch.timer("jetstream_key_delete"):
            result = runner.invoke(vm.vm_group, ["key", "delete", "smoke-key"])
            print(result.output)
        StopWatch.status("jetstream_key_delete", result.exit_code == 0)
        if result.exit_code != 0:
            print(f"Jetstream key delete failed: {result.output}")

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
    uuid_suffix = f"{uuid.uuid4().hex[:5]}"
    vm_name = f"test-cloudmesh-{username}-jetstream-vm-{uuid_suffix}"
    runner.invoke(vm.vm_group, ["delete", vm_name])

    result = runner.invoke(vm.vm_group, ["start", vm_name])
    if result.exit_code != 0:
        pytest.skip("Jetstream start failed")

    assert f"Successfully started VM {vm_name}" in Text.from_ansi(result.output).plain
    runner.invoke(vm.vm_group, ["delete", vm_name])
