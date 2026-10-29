from unittest.mock import MagicMock, patch

import pytest

from cloudmesh.ai.vm.exceptions import VMProviderError
from cloudmesh.ai.vm.local.LimaManager import Provider


@pytest.fixture
def mock_config():
    return {"clouds": {"lima": {"template": "ubuntu"}}}


@pytest.fixture
def provider(mock_config):
    """Fixture that provides a Provider instance with _run_command mocked."""
    with patch.object(Provider, "_run_command") as mock_run:
        # Mock return value for _verify_installation in __init__
        mock_run.return_value = MagicMock(returncode=0, stdout="")
        provider = Provider(mock_config)
        # Reset mock to clear the call from __init__
        mock_run.reset_mock()
        # Assign the mock to the instance for easy access in tests
        provider._run_command = mock_run
        yield provider


def test_init_success():
    with patch.object(Provider, "_run_command") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        config = {"clouds": {}}
        Provider(config)
        mock_run.assert_called_once_with(["limactl", "--version"])


def test_init_failure():
    with patch.object(Provider, "_run_command") as mock_run:
        mock_run.side_effect = FileNotFoundError("limactl not found")
        config = {"clouds": {}}
        with pytest.raises(VMProviderError, match="limactl not found"):
            Provider(config)


def test_start_with_name(provider):
    vm_name = "test-vm"

    def side_effect(command, **kwargs):
        if command == ["limactl", "list", "-f", "json"]:
            return MagicMock(returncode=0, stdout="[]")
        return MagicMock(returncode=0, stdout="Started")

    provider._run_command.side_effect = side_effect

    result = provider.start(name=vm_name)

    assert result == vm_name
    provider._run_command.assert_called_with(
        ["limactl", "start", "--name", vm_name, "--tty=false", "template:ubuntu"],
        stream=True,
    )


def test_start_default_name(provider):
    def side_effect(command, **kwargs):
        if command == ["limactl", "list", "-f", "json"]:
            return MagicMock(returncode=0, stdout="[]")
        return MagicMock(returncode=0, stdout="Started")

    provider._run_command.side_effect = side_effect

    result = provider.start()

    assert result == "lima-vm"
    provider._run_command.assert_called_with(
        ["limactl", "start", "--name", "lima-vm", "--tty=false", "template:ubuntu"],
        stream=True,
    )


def test_stop_success(provider):
    def side_effect(command, **kwargs):
        if command == ["limactl", "list", "-f", "json"]:
            return MagicMock(
                returncode=0,
                stdout='[{"name": "test-vm", "status": "Running", "image": "ubuntu"}]',
            )
        return MagicMock(returncode=0, stdout="Stopped")

    provider._run_command.side_effect = side_effect

    assert provider.stop(name="test-vm") is True
    provider._run_command.assert_any_call(["limactl", "stop", "test-vm"])


def test_delete_success(provider):
    def side_effect(command, **kwargs):
        if command == ["limactl", "list", "-f", "json"]:
            return MagicMock(
                returncode=0,
                stdout='[{"name": "test-vm", "status": "Running", "image": "ubuntu"}]',
            )
        return MagicMock(returncode=0, stdout="Deleted")

    provider._run_command.side_effect = side_effect

    assert provider.delete(name="test-vm") is True
    provider._run_command.assert_any_call(
        ["limactl", "delete", "-f", "test-vm"], stream=True
    )


def test_list_parsing(provider):
    mock_output = (
        '[{"name": "vm-1", "status": "Running", "image": "ubuntu"}, '
        '{"name": "vm-2", "status": "Stopped", "image": "fedora"}]'
    )
    provider._run_command.return_value = MagicMock(stdout=mock_output, returncode=0)

    vms = provider.list()

    assert len(vms) == 2
    assert vms[0]["name"] == "vm-1"
    assert vms[0]["status"] == "Running"
    assert vms[1]["name"] == "vm-2"
    assert vms[1]["status"] == "Stopped"


def test_list_invalid_json_does_not_fallback(provider):
    """Invalid JSON must fail without retrying legacy table output."""
    provider._run_command.return_value = MagicMock(
        returncode=0,
        stdout="NAME STATUS IMAGE\\nvm-1 Running ubuntu\\n",
    )

    with pytest.raises(VMProviderError, match="Failed to list Lima VMs"):
        provider.list()

    provider._run_command.assert_called_once_with(
        ["limactl", "list", "-f", "json"],
        stream=False,
    )


def test_login(provider):
    def side_effect(command, **kwargs):
        if command == ["limactl", "list", "-f", "json"]:
            return MagicMock(
                returncode=0,
                stdout='[{"name": "test-vm", "status": "Running", "image": "ubuntu"}]',
            )
        return MagicMock(returncode=0, stdout="Shell")

    provider._run_command.side_effect = side_effect
    assert provider.login(name="test-vm") is True
    provider._run_command.assert_any_call(["limactl", "shell", "test-vm"])


def test_restart(provider):
    def side_effect(command, **kwargs):
        if command == ["limactl", "list", "-f", "json"]:
            return MagicMock(
                returncode=0,
                stdout='[{"name": "test-vm", "status": "Running", "image": "ubuntu"}]',
            )
        return MagicMock(returncode=0, stdout="Success")

    provider._run_command.side_effect = side_effect

    assert provider.restart(name="test-vm") is True
    provider._run_command.assert_any_call(["limactl", "stop", "test-vm"])
    provider._run_command.assert_any_call(["limactl", "start", "test-vm"])


def test_getters(provider):
    flavors = provider.get_flavors()
    assert len(flavors) > 0
    assert flavors[0]["name"] == "default"

    keys = provider.get_keys()
    assert len(keys) == 1
    assert keys[0]["name"] == "lima-ssh-key"

    sgs = provider.get_security_groups()
    assert len(sgs) == 1
    assert sgs[0]["name"] == "default"


def test_run_command(provider):
    """Verify CLI remote execution delegates to Lima correctly."""
    provider._run_command.return_value = MagicMock(returncode=0, stdout="test-vm\n")

    result = provider.run_command("test-vm", "hostname")

    assert result == "test-vm\n"
    provider._run_command.assert_called_once_with(
        ["limactl", "shell", "test-vm", "hostname"],
        stream=False,
    )


def test_get_images(provider):
    """Verify Lima templates are exposed through the image interface."""
    provider._run_command.return_value = MagicMock(
        returncode=0,
        stdout="ubuntu\ndebian-12\nexperimental/ubuntu-26.10\n",
    )

    images = provider.get_images()

    assert images == [
        {"name": "ubuntu", "id": "template:ubuntu"},
        {"name": "debian-12", "id": "template:debian-12"},
        {
            "name": "experimental/ubuntu-26.10",
            "id": "template:experimental/ubuntu-26.10",
        },
    ]
    provider._run_command.assert_called_once_with(
        ["limactl", "create", "--list-templates"],
        stream=False,
    )


def test_get_flavors(provider):
    """Verify Lima exposes its configurable resource profile."""
    flavors = provider.get_flavors()

    assert flavors == [
        {
            "name": "default",
            "cpu": "Configurable",
            "ram": "Configurable",
        }
    ]


def test_upload_key_success(provider, tmp_path):
    """Upload a public key using a safely quoted shell argument."""
    key_file = tmp_path / "test.pub"
    public_key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITestKey example"
    key_file.write_text(public_key + "\n", encoding="utf-8")

    assert provider.upload_key(str(key_file), "research-key", "test-vm") is True

    args, kwargs = provider._run_command.call_args
    assert args[0][:5] == ["limactl", "shell", "test-vm", "sh", "-c"]
    assert kwargs == {"stream": False}
    assert "authorized_keys" in args[0][5]
    assert public_key in args[0][5]


def test_delete_key_success(provider):
    """Delete a named key through the Lima shell command."""
    assert provider.delete_key("research-key", "test-vm") is True

    args, kwargs = provider._run_command.call_args
    assert args[0][:5] == ["limactl", "shell", "test-vm", "sh", "-c"]
    assert kwargs == {"stream": False}
    assert "awk" in args[0][5]
    assert "research-key" in args[0][5]


def test_delete_key_special_characters(provider):
    """Special characters in a key name remain safely shell-quoted."""
    import shlex

    name = "research.*[1]'$(touch /tmp/should-not-run)"
    assert provider.delete_key(name, "test-vm") is True

    script = provider._run_command.call_args.args[0][5]
    assert shlex.quote(f" # {name}") in script
    assert "awk -v suffix=" in script


@pytest.mark.parametrize("name", ["", "bad\nname", "bad\rname"])
def test_delete_key_rejects_invalid_names(provider, name):
    """Empty or multiline key names must not reach the shell."""
    assert provider.delete_key(name, "test-vm") is False
    provider._run_command.assert_not_called()
