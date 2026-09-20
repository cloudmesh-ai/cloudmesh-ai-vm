import click
from typing import Optional
from ._shared.context import console, get_active_provider, vm_options, state, resolve_vm_name
from ._shared.exceptions import handle_errors, VMCommandError

@click.command()
@click.pass_context
@click.argument("name", required=False)
@vm_options
@handle_errors
def stop(ctx: click.Context, name: Optional[str] = None) -> None:
    """
    Stops a VM.
    
    Example:
        cmx vm stop my-vm
        cmx vm stop
    """
    vm_name = resolve_vm_name(ctx, name)
    provider = get_active_provider(ctx)
    if provider.stop(vm_name):
        state.set_last_vm(provider.cloud_name, vm_name)
        console.print(f"Successfully stopped VM [bold green]{vm_name}[/bold green].")
    else:
        raise VMCommandError(f"Failed to stop VM {vm_name}.")

cmd = stop
