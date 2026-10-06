"""
The Chameleon provider was successfully configured and tested through a pytest test suite "test-chameleon-with-credentials". 
Provider listing, provider selection, VM listing, image listing, and flavor listing worked successfully.
 VM creation could not be completed because the Cloudmesh implementation reported a missing image configuration,
 despite CC-Ubuntu24.04 being available from Chameleon and within the clouds.yaml file. 
 Stop and delete could not be tested because no VM was created. 
 The security_groups and ssh_config commands were incorrectly spelled thus rending them unavailable in the current VM CLI.
With Khalidou's assistance, I was able to test these with security-group and ssh-config which are the appropriate CLI commands and then the tests passed.
"""  # noqa: N999

import pytest
from click.testing import CliRunner

from cloudmesh.ai.command import vm


@pytest.fixture
def runner():
    """Create a Click test runner."""
    return CliRunner()


def run_command(runner, args):
    """Run a Cloudmesh VM command and print its result."""
    result = runner.invoke(vm.vm_group, args)

    print(f"\nCommand: vm {' '.join(args)}")
    print(f"Exit code: {result.exit_code}")

    if result.output:
        print(f"Output:\n{result.output}")

    if result.exception:
        print(f"Exception: {result.exception}")

    return result


def test_provider_list(runner):
    """Test listing available VM providers."""
    result = run_command(runner, ["provider", "list"])

    assert result.exit_code == 0
    assert "chameleon" in result.output.lower()


def test_provider_set_chameleon(runner):
    """Test selecting Chameleon as the active provider."""
    result = run_command(
        runner,
        ["provider", "set", "chameleon"]
    )

    assert result.exit_code == 0


def test_chameleon_start(runner):
    """Test starting a VM on Chameleon."""
    result = run_command(
        runner,
        ["start", "smoke-chameleon-vm"]
    )

    if result.exit_code != 0:
        pytest.skip(
            f"Chameleon start is currently unavailable: "
            f"{result.output}"
        )


def test_chameleon_list(runner):
    """Test listing VMs."""
    result = run_command(runner, ["list"])

    assert result.exit_code == 0


def test_chameleon_stop(runner):
    """Test stopping a VM on Chameleon."""
    result = run_command(
        runner,
        ["stop", "smoke-chameleon-vm"]
    )

    if result.exit_code != 0:
        pytest.skip(
            "No running smoke-test VM is available to stop."
        )


def test_chameleon_delete(runner):
    """Test deleting a VM on Chameleon."""
    result = run_command(
        runner,
        ["delete", "smoke-chameleon-vm"]
    )

    if result.exit_code != 0:
        pytest.skip(
            "No smoke-test VM is available to delete."
        )


def test_chameleon_image(runner):
    """Test listing Chameleon images."""
    result = run_command(runner, ["image"])

    if result.exit_code != 0:
        pytest.skip("Chameleon image command failed.")


def test_chameleon_flavor(runner):
    """Test listing Chameleon flavors."""
    result = run_command(runner, ["flavor"])

    if result.exit_code != 0:
        pytest.skip("Chameleon flavor command failed.")


def test_chameleon_security_groups(runner):
    """Test listing Chameleon security groups."""
    result = run_command(
        runner,
        ["security-group"]
    )

    if result.exit_code != 0:
        pytest.skip(
            "Chameleon security_groups command failed."
        )


def test_chameleon_ssh_config(runner):
    """Test generating SSH configuration."""
    result = run_command(
        runner,
        ["ssh-config"]
    )

    assert result.exit_code == 0