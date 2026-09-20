import os
import click
from click.testing import CliRunner
from cloudmesh.ai.command.vm import cmx

def test_dynamic_command_discovery():
    """
    Test that adding a new .py file to the vm package 
    automatically makes the command available in the CLI.
    """
    runner = CliRunner()
    
    # 1. Verify that our dummy command doesn't exist yet
    result = runner.invoke(cmx, ["vm", "dummy_cmd"])
    assert result.exit_code != 0
    assert "No such command" in result.output

    # 2. Create a dummy command file
    dummy_file_path = "src/cloudmesh/ai/command/vm/dummy_cmd.py"
    with open(dummy_file_path, "w") as f:
        f.write('''
import click
@click.command()
def dummy_cmd():
    click.echo("Dummy command executed!")
''')

    try:
        # We need to clear the cache in FlatDynamicCLI if it was already initialized
        # Since FlatDynamicCLI is a class, and the vm_group is an instance,
        # we might need to force a rescan or just use a fresh runner.
        # However, the current FlatDynamicCLI implementation uses a class instance.
        # To be safe, we can just call list_commands which triggers _scan_commands.
        
        # 3. Verify the command is now discovered
        result = runner.invoke(cmx, ["vm", "dummy_cmd"])
        assert result.exit_code == 0
        assert "Dummy command executed!" in result.output

    finally:
        # 4. Cleanup
        if os.path.exists(dummy_file_path):
            os.remove(dummy_file_path)

def test_vm_group_help():
    """
    Test that the vm group help lists the dynamic commands.
    """
    runner = CliRunner()
    result = runner.invoke(cmx, ["vm", "--help"])
    assert result.exit_code == 0
    # Check if some of our known commands are in the help output
    assert "list" in result.output
    assert "info" in result.output
    assert "providers" in result.output
