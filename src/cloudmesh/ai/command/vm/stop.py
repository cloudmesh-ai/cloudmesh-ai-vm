import click
from typing import Optional
from ._shared.context import console, get_active_provider, vm_options, state, resolve_vms
from ._shared.exceptions import handle_errors, VMCommandError

@click.command()
@click.pass_context
@click.argument("name", required=False)
@click.option("--count", type=int, help="Stop the last N VMs")
@click.option("--range", "vm_range", help="Stop VMs in a range (e.g. 1-5)")
@vm_options
@handle_errors
def stop(ctx: click.Context, name: Optional[str] = None, count: Optional[int] = None, vm_range: Optional[str] = None) -> None:
    """
    Stops one or more VMs.
    
    If a name is provided, it can be a single name or a hostlist specification (e.g. 'node[1-3]').
    If --count is provided, it stops the last N VMs created.
    If --range is provided, it stops VMs in the specified index range (e.g. '1-5' -> username-1...username-5).
    
    Example:
        cmx vm stop my-vm
        cmx vm stop "node[1-3]"
        cmx vm stop --count 3
        cmx vm stop --range 1-5
        cmx vm stop
    """
    provider = get_active_provider(ctx)
    vms_to_stop = resolve_vms(ctx, name=name, count=count, vm_range=vm_range)
    
    stopped_count = 0
    for vm_name in vms_to_stop:
        if provider.stop(vm_name):
            console.print(f"Successfully stopped VM [bold green]{vm_name}[/bold green].")
            stopped_count += 1
        else:
            console.print(f"[red]Failed to stop VM {vm_name}.[/red]")
    
    if stopped_count == 0:
        raise VMCommandError("Failed to stop any of the requested VMs.")
    
    # Update last VM to the last one successfully stopped
    last_stopped = vms_to_stop[-1]
    state.set_last_vm(provider.cloud_name, last_stopped)

cmd = stop
