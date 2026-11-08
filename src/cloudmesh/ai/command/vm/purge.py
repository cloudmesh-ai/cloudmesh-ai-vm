"""cmx vm purge

High‑level clean‑up command that deletes **all** virtual machines, releases
**all** floating IPs, and removes **all** reservations for a given cloud (or
for every enabled cloud when no ``--cloud`` option is supplied).

The command is intentionally destructive, so it prompts for confirmation unless
the caller supplies ``--yes`` (or ``-y``) to skip the prompt – this matches the
behaviour described in ``docs/vm_purge.md``.
"""

import click

from cloudmesh.ai.command._shared.context import (
    console,
    get_active_provider,
    vm_options,
    state,
)
from cloudmesh.ai.command._shared.exceptions import handle_errors, VMCommandError
from cloudmesh.ai.command._shared.ui import render_table


def _maybe_release_ip(provider, ip_addr):
    """Attempt to release a floating IP using the most specific method.

    Returns ``True`` if the IP was released, ``False`` otherwise.
    """
    try:
        # Prefer the IP‑address based helper if it exists.
        if hasattr(provider, "release_floating_ip_by_ip"):
            return provider.release_floating_ip_by_ip(ip_addr)
        # Fallback to the generic release method – many providers accept an IP.
        if hasattr(provider, "release_floating_ip"):
            return provider.release_floating_ip(ip_addr)
    except Exception as e:
        console.print(f"[red]Error releasing floating IP {ip_addr}: {e}[/red]")
    return False


def _maybe_delete_reservation(provider, res_id):
    """Attempt to delete a reservation/lease if supported."""
    try:
        if hasattr(provider, "delete_reservation"):
            return provider.delete_reservation(res_id)
    except Exception as e:
        console.print(f"[red]Error deleting reservation {res_id}: {e}[/red]")
    return False


@click.command()
@click.pass_context
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt")
@vm_options
@handle_errors
def purge(ctx: click.Context, yes: bool = False, **kwargs) -> None:
    """Delete all VMs, release all floating IPs, and remove all reservations.

    If ``--cloud`` is supplied, only that cloud is purged; otherwise every
    enabled cloud is processed.
    """

    # Determine whether we have a cloud override.
    cloud_override = ctx.obj.cloud_override if ctx.obj else None

    def process_provider(provider):
        cloud_name = provider.cloud_name
        # Prompt unless the user forced ``yes``.
        if not yes:
            confirmed = click.confirm(
                f"Are you sure you want to purge all resources for cloud {cloud_name}?",
                default=False,
            )
            if not confirmed:
                console.print(f"Skipping purge for cloud {cloud_name}.")
                return

        # -------------------------------------------------------
        # 1. VM Deletion
        # -------------------------------------------------------
        vms = provider.list() if hasattr(provider, "list") else []
        if vms:
            for vm in vms:
                # Normalise name extraction across dicts and objects.
                name = vm.get("name") if isinstance(vm, dict) else getattr(vm, "name", None)
                if not name:
                    continue
                try:
                    if provider.delete(name):
                        console.print(
                            f"Deleted VM [bold green]{name}[/bold green] on {cloud_name}."
                        )
                    else:
                        console.print(
                            f"[red]Failed to delete VM {name} on {cloud_name}[/red]"
                        )
                except Exception as e:
                    console.print(
                        f"[red]Error deleting VM {name} on {cloud_name}: {e}[/red]"
                    )
        else:
            console.print(f"No VMs found on {cloud_name}.")

        # -------------------------------------------------------
        # 2. Floating IP Release
        # -------------------------------------------------------
        if hasattr(provider, "list_floating_ips"):
            fips = provider.list_floating_ips()
            if fips:
                for fip in fips:
                    ip_addr = (
                        fip.get("floating_ip_address")
                        or fip.get("address")
                        or fip.get("ip")
                    )
                    if not ip_addr:
                        continue
                    released = _maybe_release_ip(provider, ip_addr)
                    if released:
                        console.print(
                            f"Released floating IP [bold green]{ip_addr}[/bold green] on {cloud_name}."
                        )
                    else:
                        console.print(
                            f"[yellow]Could not release floating IP {ip_addr} on {cloud_name}[/yellow]"
                        )
            else:
                console.print(f"No floating IPs found on {cloud_name}.")

        # -------------------------------------------------------
        # 3. Reservation / Lease Deletion
        # -------------------------------------------------------
        if hasattr(provider, "list_reservations"):
            reservations = provider.list_reservations()
            if reservations:
                for res in reservations:
                    res_id = (
                        res.get("id")
                        or res.get("lease_id")
                        or res.get("reservation_id")
                    )
                    if not res_id:
                        continue
                    deleted = _maybe_delete_reservation(provider, res_id)
                    if deleted:
                        console.print(
                            f"Deleted reservation [bold green]{res_id}[/bold green] on {cloud_name}."
                        )
                    else:
                        console.print(
                            f"[yellow]Could not delete reservation {res_id} on {cloud_name}[/yellow]"
                        )
            else:
                console.print(f"No reservations found on {cloud_name}.")

    # -----------------------------------------------------------
    # Execution entry point
    # -----------------------------------------------------------
    if cloud_override:
        provider = get_active_provider(ctx)
        process_provider(provider)
        return

    # Iterate over all enabled clouds when no override.
    from cloudmesh.ai.vm.providers import PROVIDER_MAP, get_provider

    cfg = state.config
    # Safely retrieve the cloud configuration mapping from the yaml DB.
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
        process_provider(provider)


# Export command for automatic registration.
cmd = purge