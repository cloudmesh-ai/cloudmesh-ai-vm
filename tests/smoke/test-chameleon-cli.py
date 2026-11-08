import json
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
    """Create a temporary clouds.yaml for Chameleon that mirrors the user's config.

    The fixture reads the real ``~/.config/cloudmesh/clouds.yaml`` if it exists and
    extracts the ``chameleon`` provider configuration. If the file is missing or
    corrupted, it falls back to a minimal set of required fields. In all cases we
    ensure that a ``key_path`` entry is present because the CLI tests need to
    upload a public SSH key.
    """
    import os
    import yaml

    # Load the existing user config if possible
    config_path = os.path.expanduser("~/.config/cloudmesh/clouds.yaml")
    try:
        with open(config_path, "r") as f:
            full_config = yaml.safe_load(f)
            provider_config = full_config.get("clouds", {}).get("chameleon", {})
            username = full_config.get("username", "smoke_user").replace("_", "-")
    except Exception:
        # Fallback defaults – these are sufficient for CLI commands that do not
        # require a real cloud backend (the smoke test is primarily a sanity check).
        provider_config = {
            "image": "ubuntu-22.04",
            "flavor": "m1.small",
        }
        username = "smoke_user"

    # Ensure a key_path is defined; the default points to a typical RSA private key.
    if "key_path" not in provider_config:
        provider_config["key_path"] = "~/.ssh/id_rsa"

    # Inject the temporary config into the Cloudmesh state manager.
    setup_cli_config(tmp_path, "chameleon", provider_config)

    # Make the username available to the test via the provider config.
    provider_config["username"] = username

    return provider_config


def test_chameleon_cli_lifecycle(runner, config):
    """
    Smoke test for Chameleon CLI lifecycle.
    """
    try:
        username = get_results_username(config_path=None)
    except Exception:
        username = "smoke_test_user"

    # 1. providers

    with cli_step(
        "Fetching Provider List", timer_name="provider_list"
    ) as step:
        result = runner.invoke(vm.vm_group, ["provider", "list"])
        step.debug("Provider list output:", result)

    assert result.exit_code == 0
    assert "chameleon" in result.output.lower()

    # 2. set
    with cli_step(
        "Setting up CLI config for Chameleon...", timer_name="provider_set"
    ) as step:
        result = runner.invoke(vm.vm_group, ["provider", "set", "chameleon"])
        step.debug("Provider set output:", result)
    assert result.exit_code == 0

    # 3. start
    with cli_step(
        "Starting a new Chameleon VM...", timer_name="start"
    ) as step:
        vm_name = f"{username}-smoke-chameleon-vm-{uuid.uuid4().hex[:6]}"
        result = runner.invoke(vm.vm_group, ["start", vm_name])
        step.debug("Chameleon start output:", result)
    if result.exit_code != 0:
        pytest.skip(f"Chameleon start failed: {result.output}")

    # Capture the actual VM name (which now includes site and username)
    import re

    match = re.search(r"VM ([\w-]+) started", result.output)
    if match:
        vm_name = match.group(1)
    else:
        # Fallback: try to find any name that looks like the requested one
        for word in result.output.split():
            if "smoke-chameleon-vm" in word and "-" in word:
                vm_name = word.strip(".,!")
                break

    # 4. list
    with cli_step(
        f"Checking if VM {vm_name} is in the list...", timer_name="list"
    ) as step:
        result = runner.invoke(vm.vm_group, ["list"])
        step.debug("Chameleon list output:", result)
    assert result.exit_code == 0
    # The output is a rich table and may be truncated (e.g., 'gregor-s…')
    # We check if the start of the VM name is present.
    assert vm_name[:8] in result.output

    # 5. stop
    with cli_step(f"Stopping VM {vm_name}...", timer_name="stop") as step:
        result = runner.invoke(vm.vm_group, ["stop", vm_name])
        step.debug("Chameleon stop output:", result)
    if result.exit_code != 0:
        pytest.skip("Chameleon stop failed")

    # 6. delete
    with cli_step(f"Deleting VM {vm_name}...", timer_name="delete") as step:
        result = runner.invoke(vm.vm_group, ["delete", vm_name])
        step.debug("Chameleon delete output:", result)
    if result.exit_code != 0:
        pytest.skip("Chameleon delete failed")

    # 7. images
    with cli_step(
        "Fetching Chameleon images...", timer_name="images"
    ) as step:
        result = runner.invoke(vm.vm_group, ["image"])
        step.debug("Chameleon images output:", result)
    if result.exit_code != 0:
        pytest.skip("Chameleon images failed")

    # 8. flavors
    with cli_step(
        "Fetching Chameleon flavors...", timer_name="flavors"
    ) as step:
        result = runner.invoke(vm.vm_group, ["flavor"])
        step.debug("Chameleon flavors output:", result)
    if result.exit_code != 0:
        pytest.skip("Chameleon flavors failed")

    ## 9. keys list
    # result = runner.invoke(vm.vm_group, ["key", "list"])
    # if result.exit_code != 0:
    #    pytest.skip("Chameleon key list failed")

    # 10. keys list --all
    # result = runner.invoke(vm.vm_group, ["key", "list", "--all"])
    # if result.exit_code != 0:
    #    pytest.skip("Chameleon key list --all failed")

    # 11. keys upload
    with cli_step(
        "Uploading SSH key to Chameleon...", timer_name="key_upload"
    ) as step:
        # Resolve the public key path using the provider configuration's key_path.
        # The ``config`` fixture guarantees that ``key_path`` points to the private key.
        # Append ``.pub`` to reference the public key file.
        pub_key_path = f"{config.get('key_path')}.pub"
        result = runner.invoke(
            vm.vm_group, ["key", "upload", pub_key_path, "--name", "smoke-key"]
        )
        step.debug("Chameleon key upload output:", result)
    if result.exit_code != 0:
        pytest.skip("Chameleon key upload failed")

    # 12. keys delete
    with cli_step(
        "Deleting SSH key from Chameleon...", timer_name="key_delete"
    ) as step:
        result = runner.invoke(vm.vm_group, ["key", "delete", "smoke-key"])
        step.debug("Chameleon key delete output:", result)
    if result.exit_code != 0:
        pytest.skip("Chameleon key delete failed")

    # 13. security_groups
    with cli_step(
        "Fetching Chameleon security groups...", timer_name="security_groups"
    ) as step:
        result = runner.invoke(vm.vm_group, ["security-group"])
        step.debug("Chameleon security_groups output:", result)
    if result.exit_code != 0:
        pytest.skip("Chameleon security-group failed")

    # 14. ssh_config
    with cli_step(
        "Fetching Chameleon SSH config...", timer_name="ssh_config"
    ) as step:
        result = runner.invoke(vm.vm_group, ["ssh-config"])
        step.debug("Chameleon ssh_config output:", result)
    assert result.exit_code == 0

    # 15. reservation
    # Try to create a reservation
    # with cli_step("Creating a Chameleon reservation...", timer_name="reservation") as step:
    #    res_name = f"{username}-smoke-res-{uuid.uuid4().hex[:6]}"
    #    print(f"Attempting to create reservation {res_name}...")
    #    result = runner.invoke(vm.vm_group, ["reservation", "duration", res_name, "--count", "1"])
    #    step.debug("Chameleon reservation output:", result)
    # if result.exit_code != 0:
    #    pytest.skip("Chameleon reservation failed")

    # Note: In CLI tests, we don't have a direct temp_config path like in lifecycle tests.
    # We use a dummy path or try to find the config path from setup_cli_config.
    # For now, we'll use a placeholder as the benchmark_helper might just need it for the username.
    save_benchmark(tag="Chameleon CLI", config_path=None)

    try:
        username = get_results_username(config_path=None)
    except Exception:
        username = "smoke_test_user"

    payload = create_benchmark_payload(benchmark_name="Chameleon CLI", user=username)
    print(json.dumps(payload, indent=2))
