import click
from typing import Optional
from ._shared.context import console, get_active_provider, vm_options, state, resolve_vms
from ._shared.exceptions import handle_errors, VMCommandError

@click.command()
@click.pass_context
@click.argument("name", required=False)
@click.option("--count", type=int, help="Suspend the last N VMs")
@click.option("--range", "vm_range", help="Suspend VMs in a range (e.g. 1-5)")
@vm_options
@handle_errors
def suspend(ctx: click.Context, name: Optional[str] = None, count: Optional[int] = None, vm_range: Optional[str] = None) -> None:
    """
    Suspends one or more VMs.
    
    If a name is provided, it can be a single name or a hostlist specification (e.g. 'node[1-3]').
    If --count is provided, it suspends the last N VMs created.
    If --range is provided, it suspends VMs in the specified index range (e.g. '1-5' -> username-1...username-5).
    
    Example:
        cmx vm suspend my-vm
        cmx vm suspend "node[1-3]"
        cmx vm suspend --count 3
        cmx vm suspend --range 1-5
        cmx vm suspend
    """
    provider = get_active_provider(ctx)
    vms_to_suspend = resolve_vms(ctx, name=name, count=count, vm_range=vm_range)
    
    suspended_count = 0
    for vm_name in vms_to_suspend:
        if provider.suspend(vm_name):
            console.print(f"Successfully suspended VM [bold green]{vm_name}[/bold green].")
            suspended_count += 1
        else:
            console.print(f"[red]Failed to suspend VM {vm_name}.[/red]")
    
    if suspended_count == 0:
        raise VMCommandError("Failed to suspend any of the requested VMs.")
    
    # Update last VM to the last one successfully suspended
    last_suspended = vms_to_suspend[-1]
    state.set_last_vm(provider.cloud_name, last_suspended)

cmd = suspend
