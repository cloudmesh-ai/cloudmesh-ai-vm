import csv
import io
import json
import subprocess
from unittest.mock import Mock
import pytest
import yaml
from click.testing import CliRunner
from cloudmesh.ai.command.vm import cmx
from cloudmesh.ai.command.vm._shared import context
from cloudmesh.ai.vm import providers
from cloudmesh.ai.vm.state_manager import StateManager


@pytest.fixture
def environment(tmp_path, monkeypatch):
    manager = StateManager(str(tmp_path / "clouds.yaml"))
    manager.db.set("username", "sydel_ugwu")
    manager.db.set("counter", 0)
    manager.db.set("default_cloud", "multipass")
    manager.db.set("clouds.multipass", {"enabled": True})
    previous = context.state._manager
    context.state.set_manager(manager)
    provider = Mock()
    provider.cloud_name = "multipass"
    provider.get_cloud_config.return_value = {}
    provider.start.side_effect = lambda name: name
    provider.list.return_value = []
    monkeypatch.setattr(providers, "get_provider", lambda name: provider)
    yield CliRunner(), provider, manager
    context.state.set_manager(previous)


def invoke(environment, *arguments):
    return environment[0].invoke(cmx, ["vm", *arguments])


def test_automatic_names_increment_and_persist(environment):
    runner, provider, manager = environment
    assert invoke(environment, "start").exit_code == 0
    assert invoke(environment, "start").exit_code == 0
    assert [call.kwargs["name"] for call in provider.start.call_args_list] == [
        "sydel-ugwu-1", "sydel-ugwu-2"
    ]
    assert StateManager(manager.config_path).db.get("counter") == 2
    assert manager.get_last_vm("multipass") == "sydel-ugwu-2"


@pytest.mark.parametrize("arguments,name", [
    (["start", "--name", "custom-vm"], "custom-vm"),
    (["start", "custom-vm"], "custom-vm"),
])
def test_explicit_name_does_not_increment_counter(environment, arguments, name):
    environment[2].db.set("counter", 17)
    assert invoke(environment, *arguments).exit_code == 0
    environment[1].start.assert_called_once_with(name=name)
    assert environment[2].db.get("counter") == 17


def test_count_generates_distinct_names(environment):
    assert invoke(environment, "start", "--count", "3").exit_code == 0
    assert [call.kwargs["name"] for call in environment[1].start.call_args_list] == [
        "sydel-ugwu-1", "sydel-ugwu-2", "sydel-ugwu-3"
    ]
    assert environment[2].db.get("counter") == 3


def test_automatic_name_skips_existing_instance(environment):
    environment[1].list.return_value = [{"name": "sydel-ugwu-1", "status": "Stopped"}]
    assert invoke(environment, "start").exit_code == 0
    environment[1].start.assert_called_once_with(name="sydel-ugwu-2")
    assert environment[2].db.get("counter") == 2


@pytest.mark.parametrize("arguments", [
    ["start", "one", "--name", "two"],
    ["start", "--name", "one", "--count", "2"],
    ["start", "--range", "1-2", "--count", "2"],
    ["start", "--count", "0"],
    ["start", "--count", "-1"],
    ["start", "--range", "3-1"],
])
def test_invalid_targets_do_not_start_vms(environment, arguments):
    assert invoke(environment, *arguments).exit_code != 0
    environment[1].start.assert_not_called()
    assert environment[2].db.get("counter") == 0


def test_partial_start_failure_returns_nonzero(environment):
    environment[1].start.side_effect = ["sydel-ugwu-1", False]
    assert invoke(environment, "start", "--count", "2").exit_code != 0
    assert environment[2].get_last_vm("multipass") == "sydel-ugwu-1"


@pytest.mark.parametrize("expression,expected", [
    ("node[1-3]", ["node1", "node2", "node3"]),
    ("node[01-02,04]", ["node01", "node02", "node04"]),
])
def test_hostlist_targets_each_named_vm_without_increment(environment, expression, expected):
    assert invoke(environment, "start", expression).exit_code == 0
    assert [call.kwargs["name"] for call in environment[1].start.call_args_list] == expected
    assert environment[2].db.get("counter") == 0


@pytest.mark.parametrize("format_name", ["json", "yaml", "csv", "table"])
@pytest.mark.parametrize("subcommand", [False, True])
def test_list_formats_are_parseable(environment, format_name, subcommand):
    environment[1].list.return_value = [{
        "name": "test-vm", "status": "Running", "ip": "192.0.2.1", "image": "Ubuntu 24.04 LTS"
    }]
    arguments = ["list", *(["vms"] if subcommand else []), "--" + format_name]
    result = invoke(environment, *arguments)
    assert result.exit_code == 0, result.output
    if format_name == "json":
        records = json.loads(result.output)
    elif format_name == "yaml":
        records = yaml.safe_load(result.output)
    elif format_name == "csv":
        records = list(csv.DictReader(io.StringIO(result.output)))
    else:
        assert "test-vm" in result.output
        return
    assert records[0]["name"] == "test-vm" and records[0]["cloud"] == "multipass"


def test_format_option_and_empty_inventory(environment):
    result = invoke(environment, "list", "vms", "--format", "json")
    assert result.exit_code == 0 and json.loads(result.output) == []


def test_conflicting_formats_fail(environment):
    assert invoke(environment, "list", "--json", "--csv").exit_code != 0


def test_all_lists_only_enabled_providers(environment, monkeypatch):
    environment[1].list.return_value = [{"name": "test-vm"}]
    monkeypatch.setattr(providers, "PROVIDER_MAP", {"multipass": object, "aws": object})
    result = invoke(environment, "list", "--all", "--json")
    assert result.exit_code == 0
    assert json.loads(result.output)[0]["name"] == "test-vm"
    environment[1].list.assert_called_once()


def test_cloud_override_survives_group_initialization(environment, monkeypatch):
    selected = []
    def get_provider(name):
        selected.append(name)
        return environment[1]
    monkeypatch.setattr(providers, "get_provider", get_provider)
    environment[2].db.set("default_cloud", "lima")
    assert invoke(environment, "--cloud", "multipass", "list", "--json").exit_code == 0
    assert selected == ["multipass"]


@pytest.mark.parametrize("output", ["", "[bold]literal[/bold]\n"])
def test_run_accepts_success_without_output_and_preserves_literal_text(environment, output):
    environment[1].run_command.return_value = output
    result = invoke(environment, "run", "test-vm", "true")
    assert result.exit_code == 0 and result.output == output
    assert environment[2].get_last_vm("multipass") == "test-vm"


def test_run_failure_returns_nonzero(environment):
    environment[1].run_command.side_effect = subprocess.CalledProcessError(1, ["exec"])
    assert invoke(environment, "run", "test-vm", "false").exit_code != 0


@pytest.mark.parametrize("command", ["login", "ssh"])
def test_interactive_multipass_commands_receive_context(environment, command):
    environment[1].login.return_value = True
    assert invoke(environment, command, "test-vm").exit_code == 0
    environment[1].login.assert_called_once_with("test-vm")


@pytest.mark.parametrize("key,value,expected", [
    ("counter", "0", 0), ("clouds.multipass.enabled", "false", False),
    ("clouds.multipass.cpus", "2", 2),
])
def test_config_set_preserves_types_and_get_handles_false_values(environment, key, value, expected):
    assert invoke(environment, "config", "set", key, value).exit_code == 0
    assert environment[2].db.get(key) == expected
    assert invoke(environment, "config", "get", key).exit_code == 0


def test_config_init_preserves_existing_settings(environment):
    environment[2].db.set("counter", 42)
    assert invoke(environment, "config", "init").exit_code == 0
    assert environment[2].db.get("counter") == 42
    assert environment[2].db.get("username") == "sydel_ugwu"
    assert invoke(environment, "config", "list").exit_code == 0
