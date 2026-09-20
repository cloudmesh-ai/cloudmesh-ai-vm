import click
from typing import Optional
from ._shared.context import console, get_active_provider, vm_options, state, resolve_vm_name
from ._shared.exceptions import handle_errors, VMCommandError

@click.command()
@click.pass_context
@click.argument("name", required=False)
@vm_options
@handle_errors
def suspend(ctx: click.Context, name: Optional[str] = None) -> None:
    """
    Suspends a VM.
    
    Example:
        cmx vm suspend my-vm
        cmx vm suspend
    """
    vm_name = resolve_vm_name(ctx, name)
    provider = get_active_provider(ctx)
    if provider.suspend(vm_name):
        state.set_last_vm(provider.cloud_name, vm_name)
        console.print(f"Successfully suspended VM [bold green]{vm_name}[/bold green].")
    else:
        raise VMCommandError(f"Failed to suspend VM {vm_name}.")

cmd = suspend
