import click
from cloudmesh.ai.common.io import console, path_expand
from cloudmesh.ai.common.logging_utils import get_contextual_logger
from cloudmesh.ai.common.telemetry import Telemetry

# Initialize Logger and Telemetry
logger = get_contextual_logger("vm")
telemetry = Telemetry("vm")

# Define the group for the command
@click.group(name="vm")
def vm_group():
    """vm command group."""
    pass

@vm_group.command(name="run")
def run_cmd():
    """Run the main functionality of vm."""
    logger.info("Executing vm run command")
    console.ok(f"The vm extension is running successfully!")

@vm_group.command(name="test-path")
@click.argument("path")
def test_path_cmd(path):
    """Example command showing path expansion."""
    expanded = path_expand(path)
    console.info(f"Expanded path: {expanded}")

entry_point = vm_group

def register(cli):
    """Registers the vm command group to the main CLI."""
    cli.add_command(vm_group, name="vm")
