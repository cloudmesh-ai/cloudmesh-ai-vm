import click
import os
from cloudmesh.ai.vm.state_manager import StateManager
from cloudmesh.ai.vm.factory import factory
from rich.console import Console

console = Console()
CONFIG_PATH = os.path.expanduser("~/.config/cloudmesh/clouds.yaml")
state = StateManager(CONFIG_PATH)

class VMContext:
    """Context object to share state and config across CLI commands."""
    def __init__(self):
        self.cloud_override: Optional[str] = None
        self.verbose: bool = False
        self.provider = None

def cloud_callback(ctx, param, value):
    if value:
        ctx.obj.cloud_override = value
    return value

def debug_callback(ctx, param, value):
    if value:
        from cloudmesh.ai.vm.logger import logger
        logger.setLevel(logging.DEBUG)
        logger.debug(f"Debug mode enabled. Using cloud: {ctx.obj.cloud_override or state.config.default_cloud}")
    return value

def verbose_callback(ctx, param, value):
    if value:
        ctx.obj.verbose = True
    return value

def get_active_provider(ctx):
    """Helper to resolve the provider based on override or default."""
    cloud_name = ctx.obj.cloud_override or state.config.default_cloud
    if not cloud_name:
        raise click.ClickException("No default cloud set. Use 'cmc vm set <cloud>' or --cloud <cloud>.")
    
    try:
        provider = factory.create(cloud_name, state.config, console=console)
        provider.cloud_name = cloud_name
        provider.verbose = ctx.obj.verbose
        return provider
    except Exception as e:
        raise click.ClickException(str(e))

def vm_options(f):
    """Custom decorator to add common VM options to commands"""
    f = click.option("--cloud", callback=cloud_callback, expose_value=False, help="Override the default cloud provider")(f)
    f = click.option("--debug", is_flag=True, callback=debug_callback, expose_value=False, help="Enable debug logging")(f)
    f = click.option("--verbose", is_flag=True, callback=verbose_callback, expose_value=False, help="Print raw subprocess/SSH commands")(f)
    f = click.pass_context(f)
    return f
