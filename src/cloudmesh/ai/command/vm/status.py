"""cmx vm status

Provides a concise audit of resources for a selected cloud or, when no cloud
override is supplied, for all enabled clouds. The command reports three
sections per cloud:

1. **Running VMs** – name, status, IP, image, flavor.
2. **Floating IPs** – address, attached VM (if discoverable), status.
3. **Reservations / Leases** – id, type, status, start, end.

If ``--json`` is supplied the information is emitted as a JSON document.
"""

import json
import click

from cloudmesh.ai.command._shared.context import (
    console,
    get_active_provider,
    vm_options,
    state,
)
from cloudmesh.ai.command._shared.exceptions import handle_errors
from cloudmesh.ai.command._shared.ui import render_table


def _render_section(title: str, columns: list[str], rows: list[list]):
    """Render a table section if rows are present, otherwise print a note.

    Returns ``True`` when rows were rendered, ``False`` otherwise.
    """
    if rows:
        render_table(title, columns, rows)
        return True
    console.print(f"No {title.lower()} found.")
    return False


@click.command()
@click.pass_context
@click.option("--json", "json_flag", is_flag=True, help="Output in JSON format")
@vm_options
@handle_errors
def status(ctx: click.Context, json_flag: bool = False, **kwargs) -> None:
    """Show a status summary of VMs, floating IPs and reservations.

    When ``--cloud`` is provided (via ``vm_options``) the command operates on
    that single cloud.  When the option is omitted we iterate over all enabled
    clouds defined in the user's configuration.
    """

    # Helper that gathers data from a provider instance.
    def gather(provider):
        cloud_name = provider.cloud_name
        vms = provider.list() if hasattr(provider, "list") else []
        fips = (
            provider.list_floating_ips()
            if hasattr(provider, "list_floating_ips")
            else []
        )
        reservations = (
            provider.list_reservations()
            if hasattr(provider, "list_reservations")
            else []
        )
        return cloud_name, vms, fips, reservations

    # Determine if a cloud override was supplied.
    cloud_override = ctx.obj.cloud_override if ctx.obj else None

    json_output = {}
    any_output = False

    if cloud_override:
        # Single cloud case.
        provider = get_active_provider(ctx)
        cloud_name, vms, fips, reservations = gather(provider)
        json_output[cloud_name] = {
            "vms": vms,
            "floating_ips": fips,
            "reservations": reservations,
        }
        if json_flag:
            console.print(json.dumps(json_output, indent=4))
            return

        console.print(f"[bold underline]Cloud: {cloud_name}[/bold underline]")
        any_output = (
            _render_section(
                "Running VMs",
                ["Name", "Status", "IP", "Image", "Flavor"],
                [
                    [
                        vm.get("name"),
                        vm.get("status"),
                        vm.get("ip"),
                        vm.get("image"),
                        vm.get("flavor"),
                    ]
                    for vm in vms
                ],
            )
            or any_output
        )
        any_output = (
            _render_section(
                "Floating IPs",
                ["Address", "Attached", "Status"],
                [
                    [
                        fip.get("floating_ip_address")
                        or fip.get("address")
                        or fip.get("ip"),
                        fip.get("instance_name")
                        or fip.get("attached")
                        or fip.get("port_id")
                        or "-",
                        fip.get("status"),
                    ]
                    for fip in fips
                ],
            )
            or any_output
        )
        any_output = (
            _render_section(
                "Reservations",
                ["ID", "Type", "Status", "Start", "End"],
                [
                    [
                        res.get("id")
                        or res.get("lease_id")
                        or res.get("reservation_id"),
                        res.get("type")
                        or res.get("resource_type")
                        or "-",
                        res.get("status"),
                        res.get("start"),
                        res.get("end"),
                    ]
                    for res in reservations
                ],
            )
            or any_output
        )
        return

    # No cloud override – iterate over all enabled providers.
    from cloudmesh.ai.vm.providers import PROVIDER_MAP, get_provider

    cfg = state.config
    # Use the underlying yaml DB to fetch cloud configuration safely.
    configured_clouds = cfg.db.get("clouds", {}) if cfg else {}

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

        provider = get_provider(cloud_name)
        c_name, vms, fips, reservations = gather(provider)
        json_output[c_name] = {
            "vms": vms,
            "floating_ips": fips,
            "reservations": reservations,
        }
        if json_flag:
            any_output = True
            continue

        console.print(f"[bold underline]Cloud: {c_name}[/bold underline]")
        any_output = (
            _render_section(
                "Running VMs",
                ["Name", "Status", "IP", "Image", "Flavor"],
                [
                    [
                        vm.get("name"),
                        vm.get("status"),
                        vm.get("ip"),
                        vm.get("image"),
                        vm.get("flavor"),
                    ]
                    for vm in vms
                ],
            )
            or any_output
        )
        any_output = (
            _render_section(
                "Floating IPs",
                ["Address", "Attached", "Status"],
                [
                    [
                        fip.get("floating_ip_address")
                        or fip.get("address")
                        or fip.get("ip"),
                        fip.get("instance_name")
                        or fip.get("attached")
                        or fip.get("port_id")
                        or "-",
                        fip.get("status"),
                    ]
                    for fip in fips
                ],
            )
            or any_output
        )
        any_output = (
            _render_section(
                "Reservations",
                ["ID", "Type", "Status", "Start", "End"],
                [
                    [
                        res.get("id")
                        or res.get("lease_id")
                        or res.get("reservation_id"),
                        res.get("type")
                        or res.get("resource_type")
                        or "-",
                        res.get("status"),
                        res.get("start"),
                        res.get("end"),
                    ]
                    for res in reservations
                ],
            )
            or any_output
        )
        console.print("")

    # After processing all clouds, handle JSON output or fallback message.
    if json_flag:
        # Print the aggregated JSON document for all clouds.
        console.print(json.dumps(json_output, indent=4))
        return
    if not any_output:
        console.print("No resources found on any enabled providers.")


# Export command for automatic registration.
cmd = status