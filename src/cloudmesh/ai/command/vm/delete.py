import click
from typing import Optional, List
from hostlist import Hostlist
from ._shared.context import console, get_active_provider, vm_options, state, resolve_vm_name
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
    
    # 1. Determine the base username for range-based deletion
    provider_config = provider.get_cloud_config(provider.cloud_name)
    raw_username = provider_config.get("username") or state.config.db.get("username", "user")
    username = raw_username.replace("_", "-")

    vms_to_delete: List[str] = []

    # 2. Resolve the list of VM names to delete
    if vm_range:
        indices = _parse_range(vm_range)
        vms_to_delete = [f"{username}-{i}" for i in indices]
        console.print(f"Targeting VMs in range {vm_range} ([bold blue]{', '.join(vms_to_delete)}[/bold blue])")
    
    elif count:
        # Get all VMs and sort by timestamp if possible
        all_vms = provider.list()
        if not all_vms:
            raise VMCommandError("No VMs found to delete.")
        
        # Attempt to sort by timestamp. We check common keys.
        timestamp_keys = ["created_at", "timestamp", "creation_time", "created"]
        sort_key = None
        for key in timestamp_keys:
            if all_vms and key in all_vms[0]:
                sort_key = key
                break
        
        if sort_key:
            # Sort VMs by the found timestamp key (Descending: most recent first)
            all_vms.sort(key=lambda x: x.get(sort_key) or "", reverse=True)
            console.print(f"Sorted VMs by {sort_key} (most recent first).")
        else:
            # Fallback: No timestamp found. We use the order from the provider.
            console.print("No timestamp found in VM metadata. Using provider list order.")
        
        # Pick the first 'count' VMs from the sorted (most recent first) list
        to_delete = all_vms[:count]
        vms_to_delete = [vm["name"] for vm in to_delete]
        console.print(f"Targeting last {count} VMs: [bold blue]{', '.join(vms_to_delete)}[/bold blue]")
    
    elif name:
        try:
            # Expand hostlist specification (e.g. 'node[1-3]' -> ['node1', 'node2', 'node3'])
            hl = Hostlist.expand(name)
            vms_to_delete = list(hl.hosts)
            if len(vms_to_delete) > 1:
                console.print(f"Expanded hostlist. Targeting VMs: [bold blue]{', '.join(vms_to_delete)}[/bold blue]")
        except Exception:
            # Fallback to treating 'name' as a single VM name if hostlist expansion fails
            vms_to_delete = [name]
    
    else:
        # Default: Single VM using resolve_vm_name
        vm_name = resolve_vm_name(ctx, name)
        vms_to_delete = [vm_name]

    # 3. Execute deletion
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
