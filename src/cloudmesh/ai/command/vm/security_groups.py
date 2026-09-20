import click
from ._shared.context import console, get_active_provider, vm_options
from ._shared.exceptions import handle_errors
from ._shared.ui import render_table

@click.command()
@click.pass_context
@vm_options
@handle_errors
def security_groups(ctx: click.Context):
    """List VM security groups."""
    provider = get_active_provider(ctx)
    sgs = provider.get_security_groups() # Adjusted to use get_security_groups()
    if sgs:
        render_table("Security Groups", ["Name", "Description"], [[sg.get("name", "Unknown"), sg.get("description", "Unknown")] for sg in sgs])
    else:
        console.print("No security groups found.")

cmd = security_groups
