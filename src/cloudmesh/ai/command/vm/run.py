import click
from typing import Optional
from ._shared.context import console, get_active_provider, vm_options, state, resolve_vm_name
from ._shared.exceptions import handle_errors, VMCommandError

@click.command()
@click.pass_context
@click.argument("name", required=False)
@click.argument("command", required=False)
@vm_options
@handle_errors
def run(ctx: click.Context, name: Optional[str] = None, command: Optional[str] = None) -> None:
    """
    Executes a command on a VM.
    
    Example:
        cmx vm run my-vm "ls -la /home"
        cmx vm run "ls -la /home"
    """
    if command is None:
        actual_command = name
        vm_name = resolve_vm_name(ctx, None)
    else:
        actual_command = command
        vm_name = resolve_vm_name(ctx, name)
        
    if not actual_command:
        raise VMCommandError("No command provided to run.")

    provider = get_active_provider(ctx)
    result = provider.run_command(vm_name, actual_command)
    if result:
        state.set_last_vm(provider.cloud_name, vm_name)
        console.print(result)
    else:
        raise VMCommandError(f"Failed to execute command on VM {vm_name}.")

cmd = run
