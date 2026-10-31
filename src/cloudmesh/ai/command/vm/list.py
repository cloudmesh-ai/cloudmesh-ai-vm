import json as jsonlib

import click

from cloudmesh.ai.command._shared.context import (
    console,
    get_active_provider,
    vm_options,
)
from cloudmesh.ai.command._shared.exceptions import handle_errors
from cloudmesh.ai.command._shared.ui import render_table


@click.group(invoke_without_command=True)
@click.pass_context
@click.option("--all", is_flag=True, help="List VMs from all enabled providers")
def list_group(ctx: click.Context, all: bool):
    """List VM resources."""
    if ctx.obj is None:
        from cloudmesh.ai.command._shared.context import VMContext

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
            name = getattr(
                vm, "name", vm.get("name") if isinstance(vm, dict) else "Unknown"
            )
            status = getattr(
                vm, "status", vm.get("status") if isinstance(vm, dict) else "Unknown"
            )
            ip = getattr(vm, "ip", vm.get("ip") if isinstance(vm, dict) else "Unknown")
            image = getattr(
                vm, "image", vm.get("image") if isinstance(vm, dict) else "Unknown"
            )
            flavor = getattr(
                vm, "flavor", vm.get("flavor") if isinstance(vm, dict) else "Unknown"
            )
            ttl = getattr(vm, "ttl", vm.get("ttl") if isinstance(vm, dict) else "N/A")
            networks = getattr(
                vm,
                "networks",
                vm.get("networks") if isinstance(vm, dict) else "Unknown",
            )
            rows.append([name, status, ip, image, flavor, ttl, networks])
        render_table(
            table_title,
            ["Name", "Status", "IP", "Image", "Flavor", "TTL", "Networks"],
            rows,
        )
        return True
    return False


@list_group.command(name="vms")
@click.pass_context
@click.option("--json", is_flag=True, help="Output in JSON format")
@vm_options
@handle_errors
def list_vms(ctx: click.Context, json: bool = False, **kwargs):
    """List VMs."""
    all_flag = getattr(ctx.obj, "list_all", False)
    if all_flag:
        from cloudmesh.ai.command._shared.context import state
        from cloudmesh.ai.vm.providers import PROVIDER_MAP, get_provider

        config = state.config
        configured_clouds = config.clouds if config else {}

        any_vms = False
        all_vms_data = {}
        for cloud_name in sorted(PROVIDER_MAP.keys()):
            cloud_cfg = configured_clouds.get(cloud_name)
            is_enabled = False
            if cloud_cfg:
                if hasattr(cloud_cfg, "enabled"):
                    is_enabled = cloud_cfg.enabled
                elif isinstance(cloud_cfg, dict):
                    is_enabled = cloud_cfg.get("enabled", False)

            if not is_enabled:
                continue

            try:
                provider = get_provider(cloud_name)
                vms = provider.list()
                if vms:
                    if json:
                        all_vms_data[cloud_name] = vms
                    elif _render_vms(cloud_name, vms):
                        any_vms = True
            except Exception as e:
                console.print(f"Could not list VMs for provider {cloud_name}: {e}")

        if json:
            click.echo(jsonlib.dumps(all_vms_data, indent=4))
            return

        if not any_vms:
            console.print("No VMs found on any enabled providers.")
        return

    provider = get_active_provider(ctx)
    cloud_name = provider.cloud_name
    vms = provider.list()
    if json:
        click.echo(jsonlib.dumps({cloud_name: vms}, indent=4))
        return

    if not _render_vms(cloud_name, vms):
        console.print(f"No VMs found on {cloud_name}.")


@list_group.command(name="regions")
@click.pass_context
@vm_options
@handle_errors
def list_regions(ctx: click.Context, **kwargs):
    """List regions."""
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
