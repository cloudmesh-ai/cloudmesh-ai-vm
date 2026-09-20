import click
from typing import Optional
from ._shared.context import console, get_active_provider, vm_options, state, resolve_vm_name
from ._shared.exceptions import handle_errors, VMCommandError

@click.command()
@click.pass_context
@click.argument("name", required=False)
@vm_options
@handle_errors
def delete(ctx: click.Context, name: Optional[str] = None) -> None:
    """
    Deletes a VM.
    
    Example:
        cmx vm delete my-vm
        cmx vm delete
    """
    vm_name = resolve_vm_name(ctx, name)
    provider = get_active_provider(ctx)
    if provider.delete(vm_name):
        # Do not update last_vm if we just deleted it
        console.print(f"Successfully deleted VM [bold green]{vm_name}[/bold green].")
    else:
        raise VMCommandError(f"Failed to delete VM {vm_name}.")

cmd = delete
