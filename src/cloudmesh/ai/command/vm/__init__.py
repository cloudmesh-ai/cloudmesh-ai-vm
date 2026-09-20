import os
import click
import importlib
import inspect
from .context import VMContext, cloud_callback, debug_callback, verbose_callback
from .providers import register_providers

# Register providers immediately so they are available to all dynamic commands
register_providers()

COMMANDS_DIR = os.path.dirname(__file__)

class FlatDynamicCLI(click.MultiCommand):
    def list_commands(self, ctx):
        """Finds all click commands across all .py files in the vm package."""
        commands = set()
        for entry in os.listdir(COMMANDS_DIR):
            if entry.endswith(".py") and entry not in ("__init__.py", "context.py"):
                module_name = entry[:-3]
                try:
                    mod = importlib.import_module(f".{module_name}", package="cloudmesh.ai.command.vm")
                    for name, obj in inspect.getmembers(mod):
                        if isinstance(obj, click.Command) or isinstance(obj, click.Group):
                            commands.add(name)
                except Exception:
                    continue
        return sorted(list(commands))

    def get_command(self, ctx, name):
        """Lazily finds the command named 'name' in any of the .py files."""
        for entry in os.listdir(COMMANDS_DIR):
            if entry.endswith(".py") and entry not in ("__init__.py", "context.py"):
                module_name = entry[:-3]
                try:
                    mod = importlib.import_module(f".{module_name}", package="cloudmesh.ai.command.vm")
                    cmd = getattr(mod, name, None)
                    if isinstance(cmd, click.Command) or isinstance(cmd, click.Group):
                        return cmd
                except Exception:
                    continue
        return None

@click.command(cls=FlatDynamicCLI)
@click.option("--cloud", callback=cloud_callback, expose_value=False, help="Override the default cloud provider")
@click.option("--debug", is_flag=True, callback=debug_callback, expose_value=False, help="Enable debug logging")
@click.option("--verbose", is_flag=True, callback=verbose_callback, expose_value=False, help="Print raw subprocess/SSH commands")
@click.pass_context
def vm_group(ctx):
    """VM management commands"""
    ctx.obj = VMContext()

@click.group()
def cmx():
    """Cloudmesh AI VM CLI"""
    pass

cmx.add_command(vm_group, name="vm")
