from unittest.mock import patch
import pytest
from cloudmesh.ai.vm.exceptions import VMProviderError
from cloudmesh.ai.vm.openstack.OpenstackManager import OpenstackManager

def test_openstack_cli_error_does_not_expose_credentials(caplog):
    """Sensitive values in CLI stderr must not be exposed in provider errors."""
    fake_secret = "FAKE-APP-CREDENTIAL-SECRET-12345"

    manager = OpenstackManager.__new__(OpenstackManager)
    manager.cloud_name = "test-cloud"
    manager.config = {
        "clouds": {
            "test-cloud": {}
        }
    }

    class FailedResult:
        returncode = 1
        stdout = ""
        stderr = f"Authentication failed using secret {fake_secret}"

    with patch(
        "subprocess.run",
        return_value=FailedResult(),
    ):
        with pytest.raises(VMProviderError) as exc_info:
            manager._run_cli_command(["openstack", "server", "list"])

    assert fake_secret not in str(exc_info.value)
    assert fake_secret not in caplog.text
