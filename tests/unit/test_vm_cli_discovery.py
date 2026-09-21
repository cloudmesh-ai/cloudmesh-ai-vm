import os
import click
import importlib
from click.testing import CliRunner
from cloudmesh.ai.command.vm import cmx, vm_group, load_commands_recursively

def test_dynamic_command_discovery():
    """
    Test that adding a new .py file to the vm package 
    automatically makes the command available in the CLI.
    """
    runner = CliRunner()
    
    # 1. Verify that our dummy command doesn't exist yet
    result = runner.invoke(cmx, ["vm", "dummy"])
    assert result.exit_code != 0
    
    # 2. Create a dummy command file
    import cloudmesh.ai.command.vm as vm_pkg
    vm_dir = os.path.dirname(vm_pkg.__file__)
    dummy_file_path = os.path.join(vm_dir, "dummy.py")
    
    with open(dummy_file_path, "w") as f:
        f.write('import click\n@click.command()\ndef dummy():\n    click.echo("Dummy command executed!")\ncmd = dummy\n')
    
    try:
        # 3. Trigger re-discovery
        importlib.invalidate_caches()
        load_commands_recursively(vm_group, vm_dir, "cloudmesh.ai.command.vm")
        
        # 4. Verify the command is now discovered
        result = runner.invoke(cmx, ["vm", "dummy"])
        assert result.exit_code == 0
        assert "Dummy command executed!" in result.output
        
    finally:
        # 5. Cleanup
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
    expected_commands = {"list", "providers", "start", "stop", "delete"}
    found_commands = {cmd for cmd in expected_commands if cmd in result.output}
    assert len(found_commands) > 0, f"None of the expected commands {expected_commands} found in help output"
