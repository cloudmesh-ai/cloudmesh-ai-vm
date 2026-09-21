import click
from ._shared.context import console, get_active_provider, vm_options
from ._shared.exceptions import handle_errors
from ._shared.ui import render_table

@click.group(invoke_without_command=True)
@click.pass_context
@vm_options
def security_groups(ctx: click.Context):
    """Manage VM security groups."""
    if ctx.invoked_subcommand is None:
        ctx.invoke(list_sgs)

@security_groups.command(name="list")
@click.pass_context
@handle_errors
def list_sgs(ctx: click.Context):
    """List VM security groups."""
    provider = get_active_provider(ctx)
    sgs = provider.get_security_groups()
    if sgs:
        render_table("Security Groups", ["Name", "Description"], [[sg.get("name", "Unknown"), sg.get("description", "Unknown")] for sg in sgs])
    else:
        console.print("No security groups found.")

@security_groups.command(name="info")
@click.argument("name")
@click.pass_context
@handle_errors
def sg_info(ctx: click.Context, name: str):
    """Get detailed information for a specific security group."""
    provider = get_active_provider(ctx)
    try:
        info = provider.get_security_group_info(name)
        if info:
            import json
            console.print(json.dumps(info, indent=4))
        else:
            console.print(f"No information found for security group {name}.")
    except Exception as e:
        console.print(f"Error getting info for security group {name}: {e}")

cmd = security_groups
