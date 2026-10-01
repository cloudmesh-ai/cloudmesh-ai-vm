import click
from typing import Optional
from ._shared.context import console, get_active_provider, vm_options, state, resolve_vms
from ._shared.exceptions import handle_errors, VMCommandError

@click.command()
@click.pass_context
@click.argument("name", required=False)
@click.option("--name", "name_override", help="Use this exact VM name without incrementing the counter")
@click.option("--count", type=click.IntRange(min=1), help="Number of VMs to start")
@click.option("--range", "vm_range", help="Range of VM indices to start (e.g. 1-5)")
@vm_options
@handle_errors
def start(ctx: click.Context, name: Optional[str] = None, name_override: Optional[str] = None, count: Optional[int] = None, vm_range: Optional[str] = None) -> None:
    """
    Starts or launches VMs. 
    
    If a name is provided, it can be a single name or a hostlist specification (e.g. 'node[1-3]').
    If --count is provided, it starts the specified number of VMs using automatic naming.
    If --range is provided, it starts VMs in the specified index range (e.g. '1-5' -> username-1...username-5).
    
    Example:
        cmx vm start my-vm
        cmx vm start "node[1-3]"
        cmx vm start --count 3
        cmx vm start --range 1-5
        cmx vm start
    """
    provider = get_active_provider(ctx)
    if sum(value is not None for value in (name, name_override, count, vm_range)) > 1:
        raise VMCommandError("Choose only one of NAME, --name, --count, or --range.")
    
    # If count is provided, we handle automatic naming separately as it's different from resolve_vms (which targets existing VMs)
    # However, resolve_vms can be used for hostlist, range and single name.
    
    vms_to_start = []
    
    if count or not (name or name_override or vm_range):
        # Special case for start: count means "create N new VMs"
        provider_config = provider.get_cloud_config(provider.cloud_name)
        raw_username = provider_config.get("username") or state.config.db.get("username", "user")
        username = raw_username.replace("_", "-")
        existing_names = {vm["name"] for vm in provider.list()}
        for _ in range(count or 1):
            counter = state.increment_counter()
            vm_name = f"{username}-{counter}"
            while vm_name in existing_names:
                counter = state.increment_counter()
                vm_name = f"{username}-{counter}"
            existing_names.add(vm_name)
            vms_to_start.append(vm_name)
        console.print(f"Starting {count or 1} VMs ([bold blue]{', '.join(vms_to_start)}[/bold blue])")
    elif name_override:
        vms_to_start = [name_override]
    else:
        vms_to_start = resolve_vms(ctx, name=name, vm_range=vm_range)

    # Start the VMs
    started_vms = []
    failed_vms = []
    for vm_name in vms_to_start:
        result = provider.start(name=vm_name)
        if result:
            final_name = result if isinstance(result, str) else vm_name
            started_vms.append(final_name)
            console.print(f"Successfully started VM [bold green]{final_name}[/bold green].")
        else:
            failed_vms.append(vm_name)
            console.print(f"[red]Failed to start VM {vm_name}.[/red]")

    if not started_vms:
        raise VMCommandError(f"Failed to start VM {', '.join(failed_vms)}.")

    # Update state with the last started VM
    last_vm = started_vms[-1]
    state.set_last_vm(provider.cloud_name, last_vm)
    if failed_vms:
        raise VMCommandError(f"Failed to start VM {', '.join(failed_vms)}.")

cmd = start
