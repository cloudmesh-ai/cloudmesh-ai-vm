import click
from typing import Optional
from ._shared.context import console, get_active_provider, vm_options, state, resolve_vms
from ._shared.exceptions import handle_errors, VMCommandError

@click.command()
@click.pass_context
@click.argument("name", required=False)
@click.option("--count", type=int, help="Restart the last N VMs")
@click.option("--range", "vm_range", help="Restart VMs in a range (e.g. 1-5)")
@vm_options
@handle_errors
def restart(ctx: click.Context, name: Optional[str] = None, count: Optional[int] = None, vm_range: Optional[str] = None) -> None:
    """
    Restarts one or more VMs.
    
    If a name is provided, it can be a single name or a hostlist specification (e.g. 'node[1-3]').
    If --count is provided, it restarts the last N VMs created.
    If --range is provided, it restarts VMs in the specified index range (e.g. '1-5' -> username-1...username-5).
    
    Example:
        cmx vm restart my-vm
        cmx vm restart "node[1-3]"
        cmx vm restart --count 3
        cmx vm restart --range 1-5
        cmx vm restart
    """
    provider = get_active_provider(ctx)
    vms_to_restart = resolve_vms(ctx, name=name, count=count, vm_range=vm_range)
    
    restarted_count = 0
    for vm_name in vms_to_restart:
        if provider.restart(vm_name):
            console.print(f"Successfully restarted VM [bold green]{vm_name}[/bold green].")
            restarted_count += 1
        else:
            console.print(f"[red]Failed to restart VM {vm_name}.[/red]")
    
    if restarted_count == 0:
        raise VMCommandError("Failed to restart any of the requested VMs.")
    
    # Update last VM to the last one successfully restarted
    last_restarted = vms_to_restart[-1]
    state.set_last_vm(provider.cloud_name, last_restarted)

cmd = restart
