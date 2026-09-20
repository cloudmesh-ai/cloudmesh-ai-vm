import click
from typing import Optional
from ._shared.context import console, get_active_provider, vm_options
from ._shared.exceptions import handle_errors
from ._shared.ui import render_table

@click.group(invoke_without_command=True)
@click.pass_context
def list_group(ctx: click.Context):
    """List VM resources."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_vms)

@list_group.command(name="vms")
@click.pass_context
@vm_options
@handle_errors
def list_vms(ctx: click.Context):
    """List all VMs."""
    provider = get_active_provider(ctx)
    
    # Use the provider's cloud_name to customize the table header
    cloud_name = provider.cloud_name
    table_title = f"VMs on {cloud_name}"
    
    # The provider implementation uses 'list()' instead of 'list_vms()'
    vms = provider.list()
    if vms:
        # Handle both object-like and dict-like VM records
        rows = []
        for vm in vms:
            name = getattr(vm, "name", vm.get("name") if isinstance(vm, dict) else "Unknown")
            status = getattr(vm, "status", vm.get("status") if isinstance(vm, dict) else "Unknown")
            ip = getattr(vm, "ip", vm.get("ip") if isinstance(vm, dict) else "Unknown")
            rows.append([name, status, ip])
        render_table(table_title, ["Name", "Status", "IP"], rows)
    else:
        console.print(f"No VMs found on {cloud_name}.")

@list_group.command(name="regions")
@click.pass_context
@vm_options
@handle_errors
def list_regions(ctx: click.Context):
    """List available regions."""
    provider = get_active_provider(ctx)
    # Check if provider has list_regions, otherwise fallback to a generic message
    if hasattr(provider, "list_regions"):
        regions = provider.list_regions()
        if regions:
            render_table("Regions", ["Region Name"], [[r] for r in regions])
        else:
            console.print("No regions found.")
    else:
        console.print("Region listing not supported by this provider.")

# To make 'cmx vm list' work, we register the group as 'cmd'
cmd = list_group
