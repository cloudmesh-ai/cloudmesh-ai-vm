import click
from typing import Optional
from ._shared.context import console, get_active_provider, vm_options
from ._shared.exceptions import handle_errors
from ._shared.ui import render_table

@click.group(invoke_without_command=True)
@click.pass_context
@click.option("--all", is_flag=True, help="List VMs from all enabled providers")
def list_group(ctx: click.Context, all: bool):
    """List VM resources."""
    if ctx.obj is None:
        from ._shared.context import VMContext
        ctx.obj = VMContext()
    ctx.obj.list_all = all
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_vms)

def _render_vms(cloud_name, vms):
    """Helper to render VM list table."""
    if vms:
        table_title = f"VMs on {cloud_name}"
        rows = []
        for vm in vms:
            name = getattr(vm, "name", vm.get("name") if isinstance(vm, dict) else "Unknown")
            status = getattr(vm, "status", vm.get("status") if isinstance(vm, dict) else "Unknown")
            ip = getattr(vm, "ip", vm.get("ip") if isinstance(vm, dict) else "Unknown")
            rows.append([name, status, ip])
        render_table(table_title, ["Name", "Status", "IP"], rows)
        return True
    return False

@list_group.command(name="vms")
@click.pass_context
@vm_options
@handle_errors
def list_vms(ctx: click.Context):
    """List all VMs."""
    all_flag = getattr(ctx.obj, "list_all", False)
    if all_flag:
        from cloudmesh.ai.vm.providers import PROVIDER_MAP, get_provider
        from ._shared.context import state
        
        config = state.config
        configured_clouds = config.clouds if config else {}
        
        any_vms = False
        for cloud_name in sorted(PROVIDER_MAP.keys()):
            cloud_cfg = configured_clouds.get(cloud_name)
            is_enabled = False
            if cloud_cfg:
                if hasattr(cloud_cfg, 'enabled'):
                    is_enabled = cloud_cfg.enabled
                elif isinstance(cloud_cfg, dict):
                    is_enabled = cloud_cfg.get('enabled', False)
            
            if not is_enabled:
                continue
            
            try:
                provider = get_provider(cloud_name)
                vms = provider.list()
                if _render_vms(cloud_name, vms):
                    any_vms = True
            except Exception as e:
                console.print(f"Could not list VMs for provider {cloud_name}: {e}")
        
        if not any_vms:
            console.print("No VMs found on any enabled providers.")
        return

    provider = get_active_provider(ctx)
    cloud_name = provider.cloud_name
    if not _render_vms(cloud_name, provider.list()):
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
