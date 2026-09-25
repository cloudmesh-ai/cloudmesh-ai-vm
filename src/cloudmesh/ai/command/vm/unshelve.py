import click
from typing import Optional
from ._shared.context import console, get_active_provider, vm_options, state, resolve_vms
from ._shared.exceptions import handle_errors, VMCommandError

@click.command()
@click.pass_context
@click.argument("name", required=False)
@click.option("--count", type=int, help="Unshelve the last N VMs")
@click.option("--range", "vm_range", help="Unshelve VMs in a range (e.g. 1-5)")
@vm_options
@handle_errors
def unshelve(ctx: click.Context, name: Optional[str] = None, count: Optional[int] = None, vm_range: Optional[str] = None) -> None:
    """
    Unshelve one or more VMs (OpenStack only).
    
    If a name is provided, it can be a single name or a hostlist specification (e.g. 'node[1-3]').
    If --count is provided, it unshelves the last N VMs created.
    If --range is provided, it unshelves VMs in the specified index range (e.g. '1-5' -> username-1...username-5).
    
    Example:
        cmx vm unshelve my-vm
        cmx vm unshelve "node[1-3]"
        cmx vm unshelve --count 3
        cmx vm unshelve --range 1-5
        cmx vm unshelve
    """
    provider = get_active_provider(ctx)
    vms_to_unshelve = resolve_vms(ctx, name=name, count=count, vm_range=vm_range)
    
    unshelved_count = 0
    for vm_name in vms_to_unshelve:
        if provider.unshelve(vm_name):
            console.print(f"Successfully unshelved VM [bold green]{vm_name}[/bold green].")
            unshelved_count += 1
        else:
            console.print(f"[red]Failed to unshelve VM {vm_name}.[/red]")
    
    if unshelved_count == 0:
        raise VMCommandError("Failed to unshelve any of the requested VMs.")
    
    # Update last VM to the last one successfully unshelved
    last_unshelved = vms_to_unshelve[-1]
    state.set_last_vm(provider.cloud_name, last_unshelved)

cmd = unshelve
