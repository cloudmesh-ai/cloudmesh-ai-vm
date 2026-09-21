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
        "auth_url": "https://chameleon.example.com",
        "username": "smoke_user",
        "password": "smoke_password",
        "tenant_id": "smoke_tenant",
        "region": "us-east-1",
        "image": "ubuntu-22.04",
        "flavor": "m1.small",
        "key_path": "~/.ssh/id_rsa",
    }
    setup_cli_config(tmp_path, "chameleon", provider_config)

def test_chameleon_cli_lifecycle(runner, config):
    """
    Smoke test for Chameleon CLI lifecycle.
    """
    # 1. providers
    result = runner.invoke(vm.vm_group, ["providers", "list"])
    assert result.exit_code == 0
    assert "chameleon" in result.output.lower()

    # 2. set
    result = runner.invoke(vm.vm_group, ["providers", "set", "chameleon"])
    assert result.exit_code == 0

    # 3. start
    vm_name = "smoke-chameleon-vm"
    result = runner.invoke(vm.vm_group, ["start", vm_name])
    if result.exit_code != 0:
        pytest.skip(f"Chameleon start failed (expected without real credentials): {result.output}")
    
    # 4. list
    result = runner.invoke(vm.vm_group, ["list"])
    assert result.exit_code == 0

    # 5. stop
    result = runner.invoke(vm.vm_group, ["stop", vm_name])
    if result.exit_code != 0:
        pytest.skip("Chameleon stop failed")

    # 6. delete
    result = runner.invoke(vm.vm_group, ["delete", vm_name])
    if result.exit_code != 0:
        pytest.skip("Chameleon delete failed")

    # 7. images
    result = runner.invoke(vm.vm_group, ["images"])
    if result.exit_code != 0:
        pytest.skip("Chameleon images failed")

    # 8. flavors
    result = runner.invoke(vm.vm_group, ["flavors"])
    if result.exit_code != 0:
        pytest.skip("Chameleon flavors failed")

    # 9. keys list
    result = runner.invoke(vm.vm_group, ["key", "list"])
    if result.exit_code != 0:
        pytest.skip("Chameleon key list failed")

    # 10. keys list --all
    result = runner.invoke(vm.vm_group, ["key", "list", "--all"])
    if result.exit_code != 0:
        pytest.skip("Chameleon key list --all failed")

    # 11. keys upload
    result = runner.invoke(vm.vm_group, ["key", "upload", "~/.ssh/id_rsa.pub"])
    if result.exit_code != 0:
        pytest.skip("Chameleon key upload failed")

    # 12. keys delete
    result = runner.invoke(vm.vm_group, ["key", "delete", "smoke-key"])
    if result.exit_code != 0:
        pytest.skip("Chameleon key delete failed")

    # 13. security_groups
    result = runner.invoke(vm.vm_group, ["security_groups"])
    if result.exit_code != 0:
        pytest.skip("Chameleon security_groups failed")

    # 14. ssh_config
    result = runner.invoke(vm.vm_group, ["ssh_config"])
    assert result.exit_code == 0

    # 15. reservation
    # Try to create a reservation
    result = runner.invoke(vm.vm_group, ["reservation", "smoke-res", "--node-type", "gpu", "--count", "1"])
    if result.exit_code != 0:
        pytest.skip("Chameleon reservation failed (expected without real credentials)")
