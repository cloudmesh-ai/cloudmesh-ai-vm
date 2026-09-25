import click
from typing import Optional
from ._shared.context import console, get_active_provider, vm_options, state, resolve_vms
from ._shared.exceptions import handle_errors, VMCommandError

@click.command()
@click.pass_context
@click.argument("name", required=False)
@click.option("--count", type=int, help="Delete the last N VMs (sorted by timestamp if available)")
@click.option("--range", "vm_range", help="Delete VMs in a range (e.g. 1-5)")
@vm_options
@handle_errors
def delete(ctx: click.Context, name: Optional[str] = None, count: Optional[int] = None, vm_range: Optional[str] = None) -> None:
    """
    Deletes one or more VMs.
    
    If a name is provided, it can be a single name or a hostlist specification (e.g. 'node[1-3]').
    If --count is provided, it deletes the last N VMs created.
    If --range is provided, it deletes VMs in the specified index range (e.g. '1-5' -> username-1...username-5).
    
    Example:
        cmx vm delete my-vm
        cmx vm delete "node[1-3]"
        cmx vm delete --count 3
        cmx vm delete --range 1-5
        cmx vm delete
    """
    provider = get_active_provider(ctx)
    
    # Resolve the list of VM names to delete
    vms_to_delete = resolve_vms(ctx, name=name, count=count, vm_range=vm_range)

    # Execute deletion
    deleted_count = 0
    for vm_name in vms_to_delete:
        if provider.delete(vm_name):
            console.print(f"Successfully deleted VM [bold green]{vm_name}[/bold green].")
            deleted_count += 1
        else:
            console.print(f"[red]Failed to delete VM {vm_name}.[/red]")

    if deleted_count == 0:
        raise VMCommandError("Failed to delete any of the requested VMs.")

cmd = delete
