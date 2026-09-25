import click
from typing import Optional
from ._shared.context import console, get_active_provider, vm_options, state, resolve_vms
from ._shared.exceptions import handle_errors, VMCommandError

@click.command()
@click.pass_context
@click.argument("name", required=False)
@click.option("--count", type=int, help="Shelve the last N VMs")
@click.option("--range", "vm_range", help="Shelve VMs in a range (e.g. 1-5)")
@vm_options
@handle_errors
def shelve(ctx: click.Context, name: Optional[str] = None, count: Optional[int] = None, vm_range: Optional[str] = None) -> None:
    """
    Shelve one or more VMs (OpenStack only).
    
    If a name is provided, it can be a single name or a hostlist specification (e.g. 'node[1-3]').
    If --count is provided, it shelves the last N VMs created.
    If --range is provided, it shelves VMs in the specified index range (e.g. '1-5' -> username-1...username-5).
    
    Example:
        cmx vm shelve my-vm
        cmx vm shelve "node[1-3]"
        cmx vm shelve --count 3
        cmx vm shelve --range 1-5
        cmx vm shelve
    """
    provider = get_active_provider(ctx)
    vms_to_shelve = resolve_vms(ctx, name=name, count=count, vm_range=vm_range)
    
    shelved_count = 0
    for vm_name in vms_to_shelve:
        if provider.shelve(vm_name):
            console.print(f"Successfully shelved VM [bold green]{vm_name}[/bold green].")
            shelved_count += 1
        else:
            console.print(f"[red]Failed to shelve VM {vm_name}.[/red]")
    
    if shelved_count == 0:
        raise VMCommandError("Failed to shelve any of the requested VMs.")
    
    # Update last VM to the last one successfully shelved
    last_shelved = vms_to_shelve[-1]
    state.set_last_vm(provider.cloud_name, last_shelved)

cmd = shelve
