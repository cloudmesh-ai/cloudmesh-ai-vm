import os
import click
import importlib
import shlex
import logging
from typing import Optional
from ._shared.context import VMContext, cloud_callback, debug_callback, verbose_callback, console
from ._shared.providers_utils import register_providers

# Register providers immediately so they are available to all commands
register_providers()

def load_commands_recursively(group: click.Group, current_dir: str, package_path: str):
    """
    Recursively scans the directory for .py files and folders,
    adding them as commands or subgroups to the provided group.
    """
    for entry in os.listdir(current_dir):
        # Ignore internal folders, files, and __init__.py
        if entry.startswith('_') or entry == '__init__.py':
            continue
            
        full_path = os.path.join(current_dir, entry)
        
        if os.path.isdir(full_path):
            # 1. Handle Sub-groups (folders)
            group_name = entry
            module_path = f"{package_path}.{group_name}"
            try:
                mod = importlib.import_module(module_path)
                group_obj = getattr(mod, 'cmd', None)
                
                if not group_obj or not isinstance(group_obj, click.Group):
                    # Fallback: Create a generic group if 'cmd' is missing or not a Group
                    group_obj = click.Group(name=group_name)
                
                group.add_command(group_obj, name=group_name)
                
                # Recurse into the folder
                load_commands_recursively(group_obj, full_path, module_path)
                
            except Exception as e:
                logging.error(f"Failed to load group {group_name} from {module_path}: {e}")
                
        elif entry.endswith('.py'):
            # 2. Handle Commands (files)
            cmd_name = entry[:-3]
            module_path = f"{package_path}.{cmd_name}"
            try:
                mod = importlib.import_module(module_path)
                cmd_obj = getattr(mod, 'cmd', None)
                
                if cmd_obj:
                    group.add_command(cmd_obj, name=cmd_name)
                else:
                    logging.warning(f"Module {module_path} does not export a 'cmd' object.")
                    
            except Exception as e:
                logging.error(f"Failed to load command {cmd_name} from {module_path}: {e}")

@click.group()
@click.option("--cloud", callback=cloud_callback, expose_value=False, help="Override the default cloud provider")
@click.option("--debug", is_flag=True, callback=debug_callback, expose_value=False, help="Enable debug logging")
@click.option("--verbose", is_flag=True, callback=verbose_callback, expose_value=False, help="Print raw subprocess/SSH commands")
@click.option("-i", "--interactive", is_flag=True, help="Enter interactive mode")
@click.pass_context
def vm_group(ctx: click.Context, interactive: bool = False) -> None:
    """VM management commands"""
    ctx.obj = VMContext()
    
    # Determine the active provider for the header
    from ._shared.context import state
    default_cloud = "multipass"
    if state.config:
        default_cloud = getattr(state.config, "default_cloud", "multipass") or "multipass"
    
    active_p = ctx.obj.cloud_override or default_cloud
    
    if interactive:
        console.print("[bold green]Entering interactive VM shell. Type 'exit' or 'quit' to leave.[/bold green]")
        
        while True:
            try:
                prompt = f"[bold blue]({active_p}) vm>[bold blue] "
                
                user_input = console.input(prompt)
                if not user_input.strip():
                    continue
                if user_input.strip().lower() in ("exit", "quit"):
                    break
                
                args = shlex.split(user_input)
                cmd_name = args[0]
                cmd_args = args[1:]
                
                # Use the group's get_command to find the command
                cmd = vm_group.get_command(ctx, cmd_name)
                if cmd:
                    ctx.invoke(cmd, *cmd_args)
                else:
                    console.print(f"[red]Unknown command: {cmd_name}[/red]. Type 'help' for available commands.")
            except KeyboardInterrupt:
                console.print("\\n[yellow]Use 'exit' to leave the shell.[/yellow]")
            except Exception as e:
                console.print(f"[bold red]Shell Error:[/bold red] {str(e)}")
    else:
        pass

# Initialize the dynamic loading
COMMANDS_DIR = os.path.dirname(__file__)
load_commands_recursively(vm_group, COMMANDS_DIR, "cloudmesh.ai.command.vm")

@click.group()
def cmx() -> None:
    """Cloudmesh AI VM CLI"""
    pass

cmx.add_command(vm_group, name="vm")
