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
        "image": "22.04",
    }
    # This uses "smoke_test_user" which tests the underscore -> hyphen sanitization
    setup_cli_config(tmp_path, "multipass", provider_config)

def test_multipass_cli_lifecycle(runner, config):
    """
    Smoke test for Multipass CLI lifecycle.
    """
    # 1. providers
    result = runner.invoke(vm.vm_group, ["providers"])
    assert result.exit_code == 0
    assert "multipass" in result.output

    # 2. set
    result = runner.invoke(vm.vm_group, ["set", "multipass"])
    assert result.exit_code == 0

    # 3. start (without name)
    # Should generate a name like smoke-test-user-1
    result = runner.invoke(vm.vm_group, ["start"])
    if result.exit_code != 0:
        # Multipass might not be installed in the test env, skip if so
        pytest.skip(f"Multipass start failed: {result.output}")
    
    assert "No name provided. Generating VM name" in result.output
    # Verify the underscore was replaced by hyphen: smoke_test_user -> smoke-test-user
    assert "smoke-test-user-" in result.output
    
    # Extract the generated VM name for subsequent steps
    import re
    match = re.search(r"Generating VM name: ([\w-]+)", result.output)
    vm_name = match.group(1) if match else "smoke-test-vm"

    # 4. list
    result = runner.invoke(vm.vm_group, ["list"])
    assert result.exit_code == 0
    # Verify the new header: "VMs on multipass"
    assert "VMs on multipass" in result.output
    assert vm_name in result.output

    # 5. run
    result = runner.invoke(vm.vm_group, ["run", "hostname"])
    assert result.exit_code == 0
    
    # 6. stop
    result = runner.invoke(vm.vm_group, ["stop", vm_name])
    assert result.exit_code == 0

    # 7. delete
    result = runner.invoke(vm.vm_group, ["delete", vm_name])
    assert result.exit_code == 0

    # 8. images
    result = runner.invoke(vm.vm_group, ["images"])
    assert result.exit_code == 0

    # 9. flavors
    result = runner.invoke(vm.vm_group, ["flavors"])
    assert result.exit_code == 0

    # 10. keys
    result = runner.invoke(vm.vm_group, ["keys"])
    assert result.exit_code == 0

    # Cleanup
    runner.invoke(vm.vm_group, ["delete", vm_name])

def test_multipass_cli_start_with_name(runner, config):
    """
    Test starting a VM with a specific name.
    """
    vm_name = "test-named-vm"
    runner.invoke(vm.vm_group, ["delete", vm_name])
    
    result = runner.invoke(vm.vm_group, ["start", vm_name])
    if result.exit_code != 0:
        pytest.skip("Multipass start failed")
    
    assert f"Successfully started VM {vm_name}" in result.output
    runner.invoke(vm.vm_group, ["delete", vm_name])
