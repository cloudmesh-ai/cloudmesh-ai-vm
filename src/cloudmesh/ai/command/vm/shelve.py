import click
from typing import Optional
from ._shared.context import console, get_active_provider, vm_options, state, resolve_vm_name
from ._shared.exceptions import handle_errors, VMCommandError

@click.command()
@click.pass_context
@click.argument("name", required=False)
@vm_options
@handle_errors
def shelve(ctx: click.Context, name: Optional[str] = None) -> None:
    """
    Shelve the VM (OpenStack only).
    """
    vm_name = resolve_vm_name(ctx, name)
    provider = get_active_provider(ctx)
    if provider.shelve(vm_name):
        state.set_last_vm(provider.cloud_name, vm_name)
        console.print(f"Successfully shelved VM [bold green]{vm_name}[/bold green].")
    else:
        raise VMCommandError(f"Failed to shelve VM {vm_name}.")

cmd = shelve
