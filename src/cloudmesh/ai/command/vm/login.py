import click
from typing import Optional
from ._shared.context import get_active_provider, vm_options, resolve_vm_name
from ._shared.exceptions import handle_errors, VMCommandError

@click.command()
@click.argument("name", required=False)
@vm_options
@handle_errors
def login(ctx: click.Context, name: Optional[str] = None) -> None:
    """
    Log into a VM or get connection details.
    If name is omitted, the last started VM is used.
    """
    provider = get_active_provider(ctx)
    vm_name = resolve_vm_name(ctx, name)
    
    if not vm_name:
        raise VMCommandError("No VM specified and no last-used VM found in context.")
        
    if not provider.login(vm_name):
        raise VMCommandError(f"Failed to login to VM {vm_name}.")

cmd = login
