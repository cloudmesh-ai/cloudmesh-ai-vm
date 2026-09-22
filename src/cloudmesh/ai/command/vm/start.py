import click
from typing import Optional, List
from hostlist import Hostlist
from ._shared.context import console, get_active_provider, vm_options, state
from ._shared.exceptions import handle_errors, VMCommandError

def _parse_range(range_str: str) -> List[int]:
    """Parse a range string like '1-5' or '1' into a list of integers."""
    try:
        if '-' in range_str:
            start_str, end_str = range_str.split('-', 1)
            return list(range(int(start_str), int(end_str) + 1))
        return [int(range_str)]
    except ValueError as e:
        raise VMCommandError(f"Invalid range format '{range_str}'. Expected 'start-end' (e.g. 1-5).") from e

@click.command()
@click.pass_context
@click.argument("name", required=False)
@click.option("--count", type=int, help="Number of VMs to start")
@click.option("--range", "vm_range", help="Range of VM indices to start (e.g. 1-5)")
@vm_options
@handle_errors
def start(ctx: click.Context, name: Optional[str] = None, count: Optional[int] = None, vm_range: Optional[str] = None) -> None:
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
    
    # 1. Determine the base username for automatic naming
    provider_config = provider.get_cloud_config(provider.cloud_name)
    raw_username = provider_config.get("username") or state.config.db.get("username", "user")
    username = raw_username.replace("_", "-")

    vms_to_start: List[str] = []

    # 2. Resolve the list of VM names to start
    if vm_range:
        indices = _parse_range(vm_range)
        vms_to_start = [f"{username}-{i}" for i in indices]
        console.print(f"Starting VMs in range {vm_range} ([bold blue]{', '.join(vms_to_start)}[/bold blue])")
    
    elif count:
        for _ in range(count):
            counter = state.increment_counter()
            vms_to_start.append(f"{username}-{counter}")
        console.print(f"Starting {count} VMs ([bold blue]{', '.join(vms_to_start)}[/bold blue])")
    
    elif name:
        try:
            # Expand hostlist specification (e.g. 'node[1-3]' -> ['node1', 'node2', 'node3'])
            hl = Hostlist.expand(name)
            vms_to_start = list(hl.hosts)
            if len(vms_to_start) > 1:
                console.print(f"Expanded hostlist. Starting VMs: [bold blue]{', '.join(vms_to_start)}[/bold blue]")
        except Exception:
            # Fallback to treating 'name' as a single VM name if hostlist expansion fails
            vms_to_start = [name]
    
    else:
        # Default: Single VM with automatic naming
        counter = state.increment_counter()
        vms_to_start = [f"{username}-{counter}"]
        console.print(f"No name, count, or range provided. Generating VM name: [bold blue]{vms_to_start[0]}[/bold blue]")

    # 3. Start the VMs
    started_vms = []
    for vm_name in vms_to_start:
        result = provider.start(name=vm_name)
        if result:
            # The provider returns the final name of the VM
            final_name = result if isinstance(result, str) else vm_name
            started_vms.append(final_name)
            console.print(f"Successfully started VM [bold green]{final_name}[/bold green].")
        else:
            console.print(f"[red]Failed to start VM {vm_name}.[/red]")

    if not started_vms:
        raise VMCommandError("Failed to start any of the requested VMs.")

    # 4. Update state with the last started VM
    last_vm = started_vms[-1]
    state.set_last_vm(provider.cloud_name, last_vm)

cmd = start

