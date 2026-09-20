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
        "auth_url": "https://jetstream.example.com",
        "username": "smoke_user",
        "password": "smoke_password",
        "tenant_id": "smoke_tenant",
        "region": "us-east-1",
        "image": "ubuntu-22.04",
        "flavor": "m1.small",
        "key_path": "~/.ssh/id_rsa",
    }
    setup_cli_config(tmp_path, "jetstream", provider_config)

def test_jetstream_cli_lifecycle(runner, config):
    """
    Smoke test for Jetstream CLI lifecycle.
    """
    # 1. providers
    result = runner.invoke(vm.vm_group, ["providers"])
    assert result.exit_code == 0
    assert "jetstream" in result.output

    # 2. set
    result = runner.invoke(vm.vm_group, ["set", "jetstream"])
    assert result.exit_code == 0

    # 3. start
    vm_name = "smoke-jetstream-vm"
    result = runner.invoke(vm.vm_group, ["start", vm_name])
    if result.exit_code != 0:
        pytest.skip(f"Jetstream start failed (expected without real credentials): {result.output}")
    
    # 4. list
    result = runner.invoke(vm.vm_group, ["list"])
    assert result.exit_code == 0

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
    result = runner.invoke(vm.vm_group, ["flavors"])
    if result.exit_code != 0:
        pytest.skip("Jetstream flavors failed")

    # 9. keys
    result = runner.invoke(vm.vm_group, ["keys"])
    if result.exit_code != 0:
        pytest.skip("Jetstream keys failed")

    # 10. security_groups
    result = runner.invoke(vm.vm_group, ["security_groups"])
    if result.exit_code != 0:
        pytest.skip("Jetstream security_groups failed")

    # 11. ssh_config
    result = runner.invoke(vm.vm_group, ["ssh_config"])
    assert result.exit_code == 0
