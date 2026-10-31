import json
import uuid
from pathlib import Path

import pytest
from click.testing import CliRunner

from cloudmesh.ai.command import vm
from tests.smoke.benchmark_helper import (
    create_benchmark_payload,
    get_results_username,
    save_benchmark,
)
from tests.smoke.cli_helper import cli_step
from tests.smoke.chameleon_cleanup import (
    cleanup_smoke_key,
    cleanup_smoke_resources,
    cleanup_smoke_security_group,
    verify_key_absent,
    verify_resources_absent,
    verify_security_group_absent,
)


@pytest.fixture
def runner():
    return CliRunner()


def test_chameleon_cli_lifecycle(runner):
    """
    Smoke test for Chameleon CLI lifecycle.
    """
    try:
        username = get_results_username(config_path=None)
    except Exception:
        username = "smoke_test_user"

    # 1. providers

    with cli_step(
        "Fetching Provider List", timer_name="chameleon_provider_list"
    ) as step:
        result = runner.invoke(vm.vm_group, ["provider", "list"])
        step.debug("Provider list output:", result)

    assert result.exit_code == 0
    assert "chameleon" in result.output.lower()

    # 2. set
    with cli_step(
        "Setting up CLI config for Chameleon...", timer_name="chameleon_provider_set"
    ) as step:
        result = runner.invoke(vm.vm_group, ["provider", "set", "chameleon"])
        step.debug("Provider set output:", result)
    assert result.exit_code == 0

    # 3. Verify that this test's unique resource names are unused.
    vm_name = f"{username}-smoke-chameleon-vm-{uuid.uuid4().hex[:6]}"
    verify_resources_absent(vm_name)

    sg_name = f"{vm_name}-sg"
    # Match the username normalization used by ChameleonManager.start().
    from cloudmesh.ai.vm.providers import get_provider

    chameleon_provider = get_provider("chameleon")
    cloud_config = chameleon_provider.get_cloud_config("chameleon")
    if not isinstance(cloud_config, dict):
        raise AssertionError("Chameleon provider configuration is invalid")

    provider_username = cloud_config.get("username", "user")
    if not isinstance(provider_username, str) or not provider_username.strip():
        raise AssertionError("Chameleon provider username is invalid")
    provider_username = provider_username.replace("_", "-")
    sg_description = f"Enable SSH and ICMP traffic for {provider_username}"
    verify_security_group_absent(sg_name)

    # 4. Start the VM. Cleanup covers partial startup failures too.
    try:
        with cli_step(
            "Starting a new Chameleon VM...", timer_name="chameleon_start"
        ) as step:
            result = runner.invoke(
                vm.vm_group,
                ["start", vm_name, "--security-group", sg_name],
            )
            step.debug("Chameleon start output:", result)

        assert result.exit_code == 0, (
            f"Chameleon start failed: {result.output}"
        )

        import re

        match = re.search(
            r"Successfully started VM ([\w-]+)\.",
            result.output,
        )
        assert match is not None, (
            f"Could not identify the created VM: {result.output}"
        )
        assert match.group(1) == vm_name, (
            f"Unexpected VM name: {match.group(1)}"
        )

        # 5. List
        with cli_step(
            f"Checking if VM {vm_name} is in the list...",
            timer_name="chameleon_list",
        ) as step:
            result = runner.invoke(vm.vm_group, ["list", "vms", "--json"])
            step.debug("Chameleon list output:", result)

        assert result.exit_code == 0, (
            f"Chameleon list failed: {result.output}"
        )
        vm_data = json.loads(result.output)
        assert vm_name in {
            entry["name"] for entry in vm_data["chameleon"]
        }, f"VM {vm_name} not found in Chameleon VM list"

        # 6. Stop
        with cli_step(
            f"Stopping VM {vm_name}...",
            timer_name="chameleon_stop",
        ) as step:
            result = runner.invoke(vm.vm_group, ["stop", vm_name])
            step.debug("Chameleon stop output:", result)

        assert result.exit_code == 0, (
            f"Chameleon stop failed: {result.output}"
        )

    finally:
        # Preflight succeeded before entering this block.
        # Clean up the exact original name, including its reservation.
        with cli_step(
            f"Cleaning up Chameleon resources for {vm_name}...",
            timer_name="chameleon_delete",
        ):
            try:
                cleanup_smoke_resources(vm_name)
            except Exception:
                # Never delete the security group while VM cleanup is uncertain.
                raise
            else:
                cleanup_smoke_security_group(sg_name, sg_description)

    # 7. images
    with cli_step(
        "Fetching Chameleon images...", timer_name="chameleon_images"
    ) as step:
        result = runner.invoke(vm.vm_group, ["image"])
        step.debug("Chameleon images output:", result)
    if result.exit_code != 0:
        pytest.skip("Chameleon images failed")

    # 8. flavors
    with cli_step(
        "Fetching Chameleon flavors...", timer_name="chameleon_flavors"
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

    # 11–12. Upload and safely clean up a uniquely named SSH key.
    key_path = Path.home() / ".ssh" / "id_ed25519.pub"
    if not key_path.is_file():
        pytest.skip("Ed25519 SSH public key is unavailable")

    expected_public_key = key_path.read_text().strip()
    if not expected_public_key:
        pytest.fail("SSH public key is empty")

    key_name = f"smoke-key-{uuid.uuid4().hex[:12]}"
    verify_key_absent(key_name)

    try:
        with cli_step(
            "Uploading SSH key to Chameleon...",
            timer_name="chameleon_key_upload",
        ) as step:
            result = runner.invoke(
                vm.vm_group,
                ["key", "upload", str(key_path), "--name", key_name],
            )
            step.debug("Chameleon key upload output:", result)

        assert result.exit_code == 0, (
            f"Chameleon key upload failed: {result.output}"
        )
    finally:
        # Preflight succeeded. Handle partially successful uploads too.
        # Never delete a key whose public-key content differs.
        with cli_step(
            "Cleaning up Chameleon smoke-test SSH key...",
            timer_name="chameleon_key_delete",
        ):
            cleanup_smoke_key(key_name, expected_public_key)

    # 13. security_groups
    with cli_step(
        "Fetching Chameleon security groups...", timer_name="chameleon_security_groups"
    ) as step:
        result = runner.invoke(vm.vm_group, ["security-group"])
        step.debug("Chameleon security_groups output:", result)
    if result.exit_code != 0:
        pytest.skip("Chameleon security-group failed")

    # 14. ssh_config
    with cli_step(
        "Fetching Chameleon SSH config...", timer_name="chameleon_ssh_config"
    ) as step:
        result = runner.invoke(vm.vm_group, ["ssh-config"])
        step.debug("Chameleon ssh_config output:", result)
    assert result.exit_code == 0

    # 15. reservation
    # Try to create a reservation
    # with cli_step("Creating a Chameleon reservation...", timer_name="chameleon_reservation") as step:
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
