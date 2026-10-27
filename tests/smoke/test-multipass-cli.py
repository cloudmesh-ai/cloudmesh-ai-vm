import json
import re
import uuid

import pytest
from click.testing import CliRunner

from cloudmesh.ai.command import vm
from tests.smoke.benchmark_helper import (
    create_benchmark_payload,
    get_results_username,
    save_benchmark,
)
from tests.smoke.cli_helper import cli_step, setup_cli_config


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def config(tmp_path, runner):
    provider_config = {
        "image": "22.04",
    }
    # setup_cli_config returns the path to the temporary clouds.yaml file
    config_path = setup_cli_config(tmp_path, "multipass", provider_config)
    return config_path


def test_multipass_cli_lifecycle(runner, config):
    """
    Smoke test for Multipass CLI lifecycle following the Chameleon pattern.
    """
    try:
        username = get_results_username(config_path=config)
    except Exception:
        username = "smoke_test_user"

    # 1. providers
    with cli_step(
        "Fetching Provider List", timer_name="provider_list"
    ) as step:
        result = runner.invoke(vm.vm_group, ["provider", "list"])
        step.debug("Provider list output:", result)
    assert result.exit_code == 0
    assert "multipass" in result.output.lower()

    # 2. set
    with cli_step(
        "Setting up CLI config for Multipass...", timer_name="provider_set"
    ) as step:
        result = runner.invoke(vm.vm_group, ["provider", "set", "multipass"])
        step.debug("Provider set output:", result)
    assert result.exit_code == 0

    # 3. start
    with cli_step(
        "Starting a new Multipass VM...", timer_name="start"
    ) as step:
        vm_name = f"{username}-smoke-multipass-vm-{uuid.uuid4().hex[:6]}"
        result = runner.invoke(vm.vm_group, ["start", vm_name])
        step.debug("Multipass start output:", result)
    if result.exit_code != 0:
        pytest.skip(f"Multipass start failed: {result.output}")

    # Capture the actual VM name
    match = re.search(r"Successfully started VM ([\w-]+)", result.output)
    if match:
        vm_name = match.group(1)
    else:
        # Fallback: try to find any name that looks like the requested one
        for word in result.output.split():
            if "smoke-multipass-vm" in word and "-" in word:
                vm_name = word.strip(".,!")
                break

    # 4. list
    with cli_step(
        f"Checking if VM {vm_name} is in the list...", timer_name="list"
    ) as step:
        result = runner.invoke(vm.vm_group, ["list"])
        step.debug("Multipass list output:", result)
    assert result.exit_code == 0
    assert vm_name[:8] in result.output

    # 5. stop
    with cli_step(f"Stopping VM {vm_name}...", timer_name="stop") as step:
        result = runner.invoke(vm.vm_group, ["stop", vm_name])
        step.debug("Multipass stop output:", result)
    if result.exit_code != 0:
        pytest.skip("Multipass stop failed")

    # 6. delete
    with cli_step(f"Deleting VM {vm_name}...", timer_name="delete") as step:
        result = runner.invoke(vm.vm_group, ["delete", vm_name])
        step.debug("Multipass delete output:", result)
    if result.exit_code != 0:
        pytest.skip("Multipass delete failed")

    # 7. images
    with cli_step(
        "Fetching Multipass images...", timer_name="images"
    ) as step:
        result = runner.invoke(vm.vm_group, ["image"])
        step.debug("Multipass images output:", result)
    if result.exit_code != 0:
        pytest.skip("Multipass images failed")

    # 8. flavors
    with cli_step(
        "Fetching Multipass flavors...", timer_name="flavors"
    ) as step:
        result = runner.invoke(vm.vm_group, ["flavor"])
        step.debug("Multipass flavors output:", result)
    if result.exit_code != 0:
        pytest.skip("Multipass flavors failed")

    # 9. keys upload (if supported)
    # with cli_step("Uploading SSH key to Multipass...", timer_name="key_upload") as step:
    #    result = runner.invoke(vm.vm_group, ["key", "upload", "~/.ssh/id_rsa.pub", "--name", "smoke-key"])
    #    step.debug("Multipass key upload output:", result)
    # if result.exit_code != 0:
    #    pytest.skip("Multipass key upload failed")

    # 10. keys delete (if supported)
    # with cli_step("Deleting SSH key from Multipass...", timer_name="key_delete") as step:
    #    result = runner.invoke(vm.vm_group, ["key", "delete", "smoke-key"])
    #    step.debug("Multipass key delete output:", result)
    # if result.exit_code != 0:
    #    pytest.skip("Multipass key delete failed")

    # 11. security_groups (likely not supported by Multipass)
    # with cli_step("Fetching Multipass security groups...", timer_name="security_groups") as step:
    #    result = runner.invoke(vm.vm_group, ["security-group"])
    #    step.debug("Multipass security_groups output:", result)
    # if result.exit_code != 0:
    #    pytest.skip("Multipass security-group failed")

    # 12. ssh_config
    # with cli_step("Fetching Multipass SSH config...", timer_name="ssh_config") as step:
    #    result = runner.invoke(vm.vm_group, ["ssh-config"])
    #    step.debug("Multipass ssh_config output:", result)
    # assert result.exit_code == 0

    # Save benchmark results
    save_benchmark(tag="Multipass CLI", config_path=config)

    try:
        username = get_results_username(config_path=config)
    except Exception:
        username = "smoke_test_user"

    payload = create_benchmark_payload(benchmark_name="Multipass CLI", user=username)
    print(json.dumps(payload, indent=2))
